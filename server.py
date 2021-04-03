from traceback import format_exc

from http_parser.http import HttpParser

from lib import epollserver
from lib.entities import Request, Response, get_handler


class WebServerCore:
    def __init__(self, addr=('0.0.0.0', 9090), receive_block_size=4096,
                 response_block_size=4096, max_conns=100000):
        self.receive_block_size = receive_block_size
        self.response_block_size = response_block_size

        self.requests = {}   # conn: [HttpParser, request, headers_done]
        self.responses = {}  # conn: [responses]
        self.clients = {}    # conn: addr
        self.handlers = {}   # func: filter

        self.epoll_server = epollserver.EpollServer(addr, maxconns=max_conns)
        self.epoll_server.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epoll_server.add_handler(self.requests_handler, epollserver.RECEIVE)
        self.epoll_server.add_handler(self.response_handler, epollserver.RESPONSE)
        self.epoll_server.add_handler(self.disconn_handler, epollserver.DISCONNECT)

    def conn_handler(self, _, conn):
        ip, port = conn.getpeername()
        print(f'[NEW-CONNECTION] Client: {ip}:{port}')
        self.clients[conn] = (ip, port)
        self.responses[conn] = []

    def disconn_handler(self, _, conn):
        ip, port = self.clients.pop(conn)
        print(f'[DISCONNECTED] Client: {ip}:{port}')

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
            # conn.send(b'HTTP/1.1 200 OK\n\nHello, World!\n')
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
        self.handlers[handler] = filter_

    def send_update(self, request: Request):
        handler = get_handler(self.handlers, request)

        if handler is None:
            # TODO: I has to return 404 http error and write this case into the logs
            print('[NO-HANDLER-ATTACHED] Could not deliver request cause no '
                  'attached handlers matches the request:', request)
            return request.response(Response('HTTP/1.1', 404, 'NOT FOUND',
                                             '<br><p align="center">No handlers attached</p>'))

        try:
            handler(request)
        except Exception as exc:
            print(f'[HANDLER-ERROR] Caught an unhandled exception in handler "{handler.__name__}:')
            print(format_exc())

    def start(self, threaded=True):
        ip, port = self.epoll_server.addr

        if not threaded:
            # if not threaded - server will shutdown before last print
            # but if threaded, we just call it and printing log entry
            # right below
            print(f'[INITIALIZATION] Serving on {ip}:{port}')

        try:
            self.epoll_server.start(threaded=threaded)
            print(f'[INITIALIZATION] Serving on {ip}:{port}')
        except KeyboardInterrupt:
            print('\n[STOPPING] Stopping web-server...')
        except Exception as exc:
            print('[STOPPING] An unhandled exception occurred:')
            print(format_exc())
            print('[STOPPING] Open an issue on https://github.com/floordiv/rush/issues '
                  'if you think it\'s a bug')

        self.stop()

    def stop(self):
        self.epoll_server.stop()

    def __del__(self):
        self.stop()


class WebServer:
    def __init__(self, addr=('0.0.0.0', 9090),
                 threadpool_workers=None):
        self.addr = addr
        self.threadpool_workers = threadpool_workers
        self.handlers = {}  # func: filter

    def serve(self, path=None, func=None):
        def wrapper(handler):
            if path is not None:
                self.handlers[handler] = lambda request: request.path == path
            else:
                self.handlers[handler] = func

        return wrapper

    def start(self):
        webserver = WebServerCore(addr=self.addr)

        for handler, filter_ in self.handlers.items():
            webserver.add_handler(handler, filter_)

        webserver.start(threaded=False)
