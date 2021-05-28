from socket import socket
from traceback import format_exc
from subprocess import check_output
from typing import List

from http_parser.http import HttpParser

from utils import sockutils
from utils.loader import Loader
from lib import epollserver, simplelogger
from utils.entities import (Request, Handler,
                            default_not_found_handler, default_internal_error_handler)


class WebServerCore:
    def __init__(self, addr=('0.0.0.0', 9090), receive_block_size=4096,
                 response_block_size=4096, max_conns=100000, debug_mode=False,
                 max_conns_from_ulimit=False, files_cache=True):
        self.receive_block_size = receive_block_size
        self.response_block_size = response_block_size
        self.debug_mode = debug_mode
        # if not debug mode, nothing will be printed
        self.logger = simplelogger.Logger('webserver', files=('logs/webserver.log',),
                                          also_stdout=debug_mode)
        self.loader = Loader(caching=files_cache)

        self.requests = {}   # conn: [HttpParser, request, headers_done]
        self.responses = {}  # conn: [responses]

        self.clients = {}    # conn: addr

        self.handlers: List[Handler] = []
        self.extra_actions_handlers = {
            'not-found': default_not_found_handler,
            'internal-error': default_internal_error_handler,
        }
        self.redirects = {}

        serversock = socket()
        self.logger.write(simplelogger.INFO, f'[INIT] Trying to bind on {addr[0]}:{addr[1]}...')
        sockutils.wait_for_bind(serversock, addr)
        self.logger.write(simplelogger.INFO, '[INIT] Done')
        
        if max_conns_from_ulimit:
            max_conns = int(check_output('ulimit -n', shell=True))
            self.logger.write(simplelogger.INFO, '[INIT] Setting max connections to value '
                                                 f'from "ulimit -n" ({max_conns})')
        else:
            self.logger.write(simplelogger.INFO, '[INIT] Setting max connections to value ' +
                                                 str(max_conns))
        
        self.epoll_server = epollserver.EpollServer(serversock, maxconns=max_conns)
        self.epoll_server.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epoll_server.add_handler(self.requests_handler, epollserver.RECEIVE)
        self.epoll_server.add_handler(self.response_handler, epollserver.RESPONSE)
        self.epoll_server.add_handler(self.disconn_handler, epollserver.DISCONNECT)

    def conn_handler(self, _, conn):
        ip, port = conn.getpeername()
        self.logger.write(simplelogger.INFO, f'[CONNECTED] Client: {ip}:{port}',
                          to_stdout=self.debug_mode)

        self.clients[conn] = (ip, port)
        self.responses[conn] = []

    def disconn_handler(self, _, conn):
        ip, port = self.clients.pop(conn)
        self.logger.write(simplelogger.INFO, f'[DISCONNECTED] Client: {ip}:{port}',
                          to_stdout=self.debug_mode)

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
                              dict(parser.get_headers()), b'')
            cell[1:3] = [request, True]

        if parser.is_partial_body():
            # we create Request object only after we receive headers
            # to avoid creating Request object with None-value attrs
            # and filling them later. That's why at this point we anyway
            # already has a request object
            body_fragment = parser.recv_body()

            try:
                request.body += body_fragment  # noqa
            except TypeError:
                request.body += body_fragment.encode()

        if parser.is_message_complete():
            self.send_update(request)
            self.requests.pop(conn)

    def send_response(self, conn, response):
        if not self.responses[conn]:
            self.epoll_server.modify(conn, epollserver.RESPONSE)

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

    def add_handler(self, handler: Handler):
        self.handlers.append(handler)

    def get_handler(self, request: Request):
        for handler in self.handlers:
            if handler.route == request.path:
                if handler.filter is not None and not handler.filter(request):
                    continue
                if '*' not in handler.methods and request.method not in handler.methods:
                    continue

                return handler.func

        return self.extra_actions_handlers['not-found']

    def add_redirect(self, from_url, to_url):
        self.redirects[from_url] = to_url

    def send_update(self, request: Request):
        # https://www.youtube.com/watch?v=TUMzEo0a0ek
        # https://www.youtube.com/watch?v=YQZX0ams8dc
        # these songs are wonderful. Listen to them

        if request.path in self.redirects:
            return request.response(request.protocol, 308, headers={
                'Location': self.redirects[request.path]
            })

        self.safe_call(self.get_handler(request), request)

    def safe_call(self, handler, request):
        try:
            handler(self.loader, request)
        except Exception as exc:
            self.logger.write(simplelogger.DEBUG, '[HANDLER-ERROR] Caught an unhandled exception '
                                                  f'in handler "{handler.__name__}:\n{format_exc()}'
                              )
            self.extra_actions_handlers['internal-error'](self.loader, request)

    def start(self, threaded=True):
        ip, port = self.epoll_server.addr

        if not threaded:
            # if not threaded - server will shutdown before last print
            # but if threaded, we just call it and printing log entry
            # right below
            self.logger.write(simplelogger.INFO, f'[INIT] Serving on {ip}:{port}')

        try:
            self.epoll_server.start(threaded=threaded)
            self.logger.write(simplelogger.INFO, f'[INIT] Serving on {ip}:{port}')
        except KeyboardInterrupt:
            self.logger.write(simplelogger.INFO, '[STOPPING] Stopping web-server...')
        except OSError as oserror_exc:
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] OSError occurred during server '
                                                     'work, stopping webserver silently')

            if oserror_exc.errno == 24:
                self.logger.write(simplelogger.WARNING, '[STOPPING] Problem was caused by lack of '
                                                        'descriptors. Try to set more available '
                                                        'opened files using "ulimit -Sn <value>", '
                                                        'where value is integer or "unlimited"')
        except Exception as exc:
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] An unhandled exception occurred:')
            self.logger.write(simplelogger.CRITICAL, format_exc(), time_format='')
            self.logger.write(simplelogger.CRITICAL, '[STOPPING] Open an issue on '
                                                     'https://github.com/floordiv/rush/issues '
                                                     'if you think it\'s a bug')

        self.stop()

    def stop(self):
        self.epoll_server.stop()
        self.logger.stop()

    def __del__(self):
        self.stop()


class WebServer:
    def __init__(self, addr=('0.0.0.0', 9090), maxconns_from_ulimit=True, debug_mode=True):
        self.webserver = WebServerCore(addr=addr, debug_mode=debug_mode,
                                       max_conns_from_ulimit=maxconns_from_ulimit)
        self.loader = self.webserver.loader

    def route(self, path='/', func=None, methods=None):
        def wrapper(handler):
            handler_entity = Handler(handler, path, methods or ['*'], func)
            self.webserver.add_handler(handler_entity)

            return handler

        return wrapper

    def not_found_handler(self, methods=None):
        def wrapper(func):
            self.webserver.extra_actions_handlers['not-found'] = func

            return func

        return wrapper

    def add_redirect(self, old, new):
        self.webserver.add_redirect(old, new)

    def start(self):
        self.webserver.start(threaded=False)
