from socket import socket
from traceback import format_exc
from subprocess import check_output

from http_parser.http import HttpParser

from utils import sockutils
from lib import epollserver, simplelogger
from utils.entities import Request, get_handler

DEFAULT_404 = """\
<html>
    <head>
        <title>404 NOT FOUND</title>
    </head>
    <body>
        <h6 align="center">404 REQUESTING PAGE NOT FOUND</h6>
    </body>
</html>
"""


class WebServerCore:
    def __init__(self, addr=('0.0.0.0', 9090), receive_block_size=4096,
                 response_block_size=4096, max_conns=100000, debug_mode=False,
                 max_conns_from_ulimit=False):
        self.receive_block_size = receive_block_size
        self.response_block_size = response_block_size
        self.debug_mode = debug_mode
        # if not debug mode, nothing will be printed
        self.logger = simplelogger.Logger('webserver', files=('logs/webserver.log',),
                                          also_stdout=debug_mode)

        self.requests = {}   # conn: [HttpParser, request, headers_done]
        self.responses = {}  # conn: [responses]
        self.clients = {}    # conn: addr
        self.filter_handlers = {}   # func: filter (callable)
        self.routes_handlers = {}   # path (string): func
        self.paths_aliases = {}
        self.default_404_page = DEFAULT_404

        serversock = socket()
        self.logger.write(simplelogger.INFO, f'[INIT] Trying to bind on {addr[0]}:{addr[1]}...',
                          to_stdout=True)
        sockutils.wait_for_bind(serversock, addr)
        self.logger.write(simplelogger.INFO, '[INIT] Done', to_stdout=True)
        
        if max_conns_from_ulimit:
            max_conns = int(check_output('ulimit -n', shell=True))
            self.logger.write(simplelogger.INFO, '[INIT] Setting max connections to value '
                                                 f'from "ulimit -n" ({max_conns})',
                              to_stdout=True)
        else:
            self.logger.write(simplelogger.INFO, f'[INIT] Setting max connections to value {max_conns}',
                              to_stdout=True)
        
        self.epoll_server = epollserver.EpollServer(serversock, maxconns=max_conns)
        self.epoll_server.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epoll_server.add_handler(self.requests_handler, epollserver.RECEIVE)
        self.epoll_server.add_handler(self.response_handler, epollserver.RESPONSE)
        self.epoll_server.add_handler(self.disconn_handler, epollserver.DISCONNECT)

    def conn_handler(self, _, conn):
        ip, port = conn.getpeername()
        self.logger.write(simplelogger.INFO, f'[CONNECTED] Client: {ip}:{port}')

        self.clients[conn] = (ip, port)
        self.responses[conn] = []

    def disconn_handler(self, _, conn):
        ip, port = self.clients.pop(conn)
        self.logger.write(simplelogger.INFO, f'[DISCONNECTED] Client: {ip}:{port}')

        self.responses.pop(conn)

        if conn in self.requests:
            self.requests.pop(conn)

    def requests_handler(self, _, conn):
        if conn not in self.requests:
            parser = HttpParser()
            headers_done = False
            cell = [parser, None, False]
            self.requests[conn] = cell
        else:
            cell = self.requests[conn]
            parser, request, headers_done = cell

        received = conn.recv(self.receive_block_size)
        parser.execute(received, len(received))

        if parser.is_headers_complete() and not headers_done:
            http_version = ".".join(map(str, parser.get_version()))
            request = Request(self, conn,
                              parser.get_method(), parser.get_path(),
                              f'HTTP/{http_version}',
                              dict(parser.get_headers()), '')
            cell[1:3] = [request, True]

        if parser.is_partial_body():
            # we create Request object only after we receive headers
            # to avoid creating Request object with None-value attrs
            # and filling them later. That's why at this point we anyway
            # already has a request object
            request.body += parser.recv_body()  # noqa

        if parser.is_message_complete():
            self.send_update(request)
            self.requests.pop(conn)

    def send_response(self, conn, response):
        if not self.responses[conn]:
            self.epoll_server.modify(conn, epollserver.RESPONSE)

        self.add_response(conn, response)

    def add_response(self, conn, response):
        self.responses[conn].append(response)

    def response_handler(self, _, conn):
        block = self.responses[conn][0]
        bytes_sent = conn.send(block)

        if len(block) == bytes_sent:
            self.responses[conn].pop(0)
        else:
            self.responses[conn][0] = block[bytes_sent:]

        if not self.responses[conn]:
            self.epoll_server.modify(conn, epollserver.RECEIVE)

    def add_handler(self, handler, filter_):
        self.filter_handlers[handler] = filter_

    def add_route(self, handler, path):
        self.routes_handlers[path] = handler

    def set_404_page(self, new_content):
        self.default_404_page = new_content

    def path_alias(self, old_path, new_alias):
        self.paths_aliases[old_path] = new_alias

    def send_update(self, request: Request):
        # https://www.youtube.com/watch?v=TUMzEo0a0ek
        # https://www.youtube.com/watch?v=YQZX0ams8dc
        # these songs are wonderful. Listen to them

        if request.path in self.paths_aliases:
            request.path = self.paths_aliases[request.path]

        if request.path in self.routes_handlers:
            return self.routes_handlers[request.path](request)

        handler = get_handler(self.filter_handlers, request)

        if handler is None:
            self.logger.write(simplelogger.DEBUG, '[NO-HANDLER-ATTACHED] Could not deliver request cause no '
                              'attached handlers matches the request:\n' + str(request).rstrip('\n'))

            return request.response('HTTP/1.1', 404, self.default_404_page)

        self.safe_call(handler, request)

    def safe_call(self, handler, request):
        try:
            handler(request)
        except Exception as exc:
            self.logger.write(simplelogger.DEBUG, '[HANDLER-ERROR] Caught an unhandled exception in handler '
                                                  f'"{handler.__name__}:\n{format_exc()}')

    def start(self, threaded=True):
        ip, port = self.epoll_server.addr

        if not threaded:
            # if not threaded - server will shutdown before last print
            # but if threaded, we just call it and printing log entry
            # right below
            self.logger.write(simplelogger.INFO, f'[INIT] Serving on {ip}:{port}',
                              to_stdout=True)

        try:
            self.epoll_server.start(threaded=threaded)
            self.logger.write(simplelogger.INFO, f'[INIT] Serving on {ip}:{port}',
                              to_stdout=True)
        except KeyboardInterrupt:
            self.logger.write(simplelogger.INFO, '[STOPPING] Stopping web-server...',
                              to_stdout=True)
        except OSError as oserror_exc:
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] OSError occurred during server work, '
                                                     'stopping webserver silently',
                              to_stdout=True)

            if oserror_exc.errno == 24:
                self.logger.write(simplelogger.WARNING, '[STOPPING] Tip: OSError errno is 24. This means '
                                                        'your os does not allows too much opened files '
                                                        'descriptors. To see how much descriptors can be '
                                                        'opened at the same time, run command "ulimit -a" '
                                                        '("open files"). To increase the value, enter command '
                                                        '"ulimit -Sn <value>". You also can just type unlimited '
                                                        'instead of number, the maximal value will be set',
                                  to_stdout=True)
        except Exception as exc:
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] An unhandled exception occurred:',
                              to_stdout=True)
            self.logger.write(simplelogger.CRITICAL, format_exc(),
                              to_stdout=True, time_format='')
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] Open an issue on '
                                                     'https://github.com/floordiv/rush/issues '
                                                     'if you think it\'s a bug',
                              to_stdout=True)

        self.stop()

    def stop(self):
        self.epoll_server.stop()
        self.logger.stop()

    def __del__(self):
        self.stop()


class WebServer:
    def __init__(self, addr=('0.0.0.0', 9090), maxconns_from_ulimit=True,
                 threadpool_workers=None, debug_mode=True):
        self.addr = addr
        self.maxconns_from_ulimit = maxconns_from_ulimit
        self.threadpool_workers = threadpool_workers
        self.handlers = {}  # func: filter
        self.routes = {}    # path: func
        self.debug_mode = debug_mode
        self.default_404_page = None

    def filter(self, func):
        def wrapper(handler):
            self.handlers[handler] = func

            return handler

        return wrapper

    def route(self, path='/'):
        def wrapper(handler):
            self.routes[path] = handler

            return handler

        return wrapper

    def set_404_page(self, content):
        self.default_404_page = content

    def start(self):        
        webserver = WebServerCore(addr=self.addr, debug_mode=self.debug_mode,
                                  max_conns_from_ulimit=self.maxconns_from_ulimit)

        for handler, filter_ in self.handlers.items():
            webserver.add_handler(handler, filter_)

        for path, handler in self.routes.items():
            webserver.add_route(handler, path)

        if self.default_404_page:
            webserver.set_404_page(self.default_404_page)

        webserver.start(threaded=False)
