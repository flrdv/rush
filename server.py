from select import EPOLLIN, EPOLLOUT, EPOLLHUP

from http_parser.http import HttpParser

from lib import epollserver
from lib.entities import Request, compare_filters

RESPONSE = 0
HEARTBEAT = 1


class CoreServer:
    def __init__(self, addr=('0.0.0.0', 9090), receive_block_size=4096,
                 response_block_size=4096):
        self.receive_block_size = receive_block_size
        self.response_block_size = response_block_size

        self.requests = {}   # conn: [HttpParser, request, headers_done]
        self.responses = {}  # conn: [requests]
        self.clients = {}    # conn: addr
        self.handlers = {}   # func: filter-entity

        self.epoll_server = epollserver.EpollServer(addr)
        self.epoll_server.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epoll_server.add_handler(self.requests_handler, epollserver.RECEIVE)
        self.epoll_server.add_handler(self.disconn_handler, epollserver.DISCONNECT)

    def conn_handler(self, _, conn):
        ip, port = conn.getpeername()
        print(f'[NEW-CONNECTION] Client: {ip}:{port}')
        self.clients[conn] = (ip, port)

    def disconn_handler(self, _, conn):
        ip, port = self.clients[conn]
        print(f'[DISCONNECTED] Client: {ip}:{port}')

    def requests_handler(self, _, conn):
        """
        TODO: add here parsing http requests using http-parser
        """

        if conn not in self.requests:
            parser = HttpParser()
            headers_done = False
            cell = [parser, None, False]
            self.requests[conn] = cell
        else:
            cell = self.requests[conn]
            parser, request, headers_done = cell

        recieved = conn.recv(self.receive_block_size)
        parser.execute(recieved, len(recieved))

        if parser.is_headers_complete() and not headers_done:
            http_version = ".".join(map(str, parser.get_version()))
            request = Request(parser.get_method(), parser.get_path(),
                              f'HTTP/{http_version}',
                              dict(parser.get_headers()), '')
            request.headers = dict(parser.get_headers())
            request.type = parser.get_method()
            request.path = parser.get_path()
            request.protocol = parser.get_version()
            cell[1] = request
            cell[2] = True

        if parser.is_partial_body():
            # we create Request object only after we receive headers
            # to avoid creating Request object with None-value attrs
            # and filling them later. That's why at this point we anyway
            # already has a request object
            request.body += parser.recv_body()  # noqa

        if parser.is_message_complete():
            print('Received full request:', request)
            # self.send_update(cell[1])
            conn.send(b'HTTP/1.1 200 OK\n\nHello World')
            self.requests.pop(conn)

    def response_handler(self, _, conn):
        """
        Sending requests to the handlers
        """

        block = self.responses[conn][0][:self.response_block_size]
        conn.send(block)

        if len(block) < self.response_block_size:
            self.responses[conn].pop(0)

            if not self.responses[conn]:
                self.responses.pop(conn)

    def add_handler(self, handler, filter_):
        self.handlers[handler] = filter_

    def send_update(self, request: Request):
        for handler, filter_ in self.handlers.items():
            if compare_filters(filter_, request):
                return handler(request)

        # TODO: I has to return 404 http error and write this case into the logs
        print('[NO-HANDLER-ATTACHED] Could not deliver request cause no '
              'attached handlers matches the request:', request)

    def start(self, threaded=True):
        ip, port = self.epoll_server.server_sock.getsockname()

        if not threaded:
            # if not threaded - server will shutdown before last print
            # but if threaded, we just call it and printing log entry
            # right below
            print(f'[INITIALIZATION] Serving on {ip}:{port}')

        self.epoll_server.start(conn_signals=(EPOLLIN | EPOLLOUT | EPOLLHUP),
                                threaded=threaded)
        print(f'[INITIALIZATION] Serving on {ip}:{port}')


class WebServer:
    def __init__(self):
        self.handlers = {}  # func: filter

    def serve(self, path=None, func=None):
        def wrapper(handler):
            if path is not None:
                self.handlers[handler] = lambda request: request.path == path
            else:
                self.handlers[handler] = func

        return wrapper

    def start(self):
        webserver = CoreServer()

        for handler, filter_ in self.handlers.items():
            webserver.add_handler(handler, filter_)

        webserver.start(threaded=False)
