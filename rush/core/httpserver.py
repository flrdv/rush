""""
This is a http server on epoll, that is using httptools lib for parsing
http requests. This lib is a wrapper on Cython for originally written on
C http parser "llhttp"
"""

import logging
from socket import MSG_PEEK
from traceback import format_exc
from httptools import HttpRequestParser
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLHUP
from httptools.parser.errors import HttpParserError, HttpParserCallbackError

from rush.utils.httputils import decode_url
from rush.core.entities import CaseInsensitiveDict

logger = logging.getLogger(__name__)

EPOLLIN_AND_EPOLLOUT = EPOLLIN | EPOLLOUT
DEFAULT_RECV_BLOCK_SIZE = 8192  # how many bytes are receiving per 1 socket read


class Protocol:
    """
    Initializing headers dictionary in the beginning, but individual for every
    object
    """
    headers = CaseInsensitiveDict()

    def __init__(self, call_handler, conn, send_http_response: callable):
        self.call_handler = call_handler
        self.send_http_response = send_http_response
        self.parser = None  # will be set later
        self.conn = conn
        self.path = None
        self.parameters = b''
        self.fragment = None
        self.body = b''
        self.file = False

        self.received = False

        self._on_chunk = None
        self._on_complete = None

    def on_url(self, url: bytes):
        url = decode_url(url)

        if b'?' in url:
            url, self.parameters = url.split(b'?', 1)

            if b'#' in self.parameters:
                self.parameters, self.fragment = self.parameters.split(b'#', 1)
        elif b'#' in self.parameters:
            url, self.fragment = url.split(b'#', 1)

        self.path = url.rstrip(b'/')

    def on_header(self, name: bytes, value: bytes):
        self.headers[name.decode()] = value.decode()

    def on_headers_complete(self):
        if self.headers.get('transfer-encoding') == 'chunked' or \
                self.headers.get('content-type', '').startswith('multipart/'):
            self.file = True
            request_obj = self._call_handler()

            if request_obj is None:
                # just got redirected a client
                return

            # so long ang ugly only cause variables unpacking takes
            # only 1 instruction for PVM
            self._on_chunk, self._on_complete = request_obj.on_chunk, request_obj.on_complete

    def on_body(self, body: bytes):
        if self.file:
            self._on_chunk(body)
        else:
            self.body += body

    def on_message_complete(self):
        self.received = True

        if self.file:
            self._on_complete()
        else:
            self._call_handler()

    def _call_handler(self):
        return self.call_handler(self.send_http_response,
                                 self.body,
                                 self.conn,
                                 self.parser.get_http_version(),
                                 self.parser.get_method(),
                                 self.path,
                                 self.parameters,
                                 self.fragment,
                                 self.headers,
                                 self.file)


class HttpServer:
    def __init__(self, sock, max_conns):
        self.on_message_complete = None
        self.sock = sock
        self.max_conns = max_conns
        self.epoll = None
        self._conns = {}  # fileno: conn

        # every client has only one entity of parser and protocol
        # on each request, entities are just re-initializing
        self._requests_buff = {}  # conn: (parser, protocol_instance)
        self._responses_buff = {}  # conn: b'...'

    def _receive_handler(self, conn):
        parser, protocol = self._requests_buff[conn]

        try:
            parser.feed_data(conn.recv(DEFAULT_RECV_BLOCK_SIZE))
        except HttpParserCallbackError as exc:
            logger.error(f'an error occurred in callback: {exc}')
            logger.exception(f'full error trace:\n{format_exc()}')

            return self._call_handler(self._disconnect_handler,
                                      self._conns.pop(conn.fileno()))
        except HttpParserError as exc:
            # if some error occurred, relationship won't be good in future
            logger.error(f'disconnected user due to parsing request error: {exc}')

            return self._call_handler(self._disconnect_handler,
                                      self._conns.pop(conn.fileno()))

        if protocol.received:
            protocol.__init__(self.on_message_complete,
                              conn,
                              self.send)
            parser.__init__(protocol)
            protocol.parser = parser
            self._requests_buff[conn] = (parser, protocol)

    def _response_handler(self, conn):
        current_bytestring = self._responses_buff[conn]
        bytestring_left = current_bytestring[conn.send(current_bytestring):]
        self._responses_buff[conn] = bytestring_left

        if not bytestring_left:
            self.epoll.modify(conn, EPOLLIN)

    def _connect_handler(self, conn):
        # creating cell for conn once to avoid if-conditions in _receive_handler and
        # _response_handler every time receiving new event on socket read/write
        protocol_instance = Protocol(self.on_message_complete,
                                     conn,
                                     self.send)
        new_parser = HttpRequestParser(protocol_instance)
        protocol_instance.parser = new_parser
        self._requests_buff[conn] = (new_parser, protocol_instance)
        self._responses_buff[conn] = b''

    def _disconnect_handler(self, conn):
        self._requests_buff.pop(conn)
        self._responses_buff.pop(conn)
        conn.close()

    @staticmethod
    def _call_handler(handler, conn):
        try:
            handler(conn)
        except Exception as exc:
            logger.error('Caught an unhandled exception in handler '
                         f'"{handler.__name__}": {exc}')
            logger.exception(f'detailed error trace:\n{format_exc()}')

    def send(self, conn, data: bytes):
        sent = conn.send(data)

        if sent == len(data):
            return

        if not self._responses_buff[conn]:
            self.epoll.modify(conn, EPOLLIN_AND_EPOLLOUT)

        self._responses_buff[conn] += data[sent:]

    def run(self):
        if self.on_message_complete is None:
            raise RuntimeError('no callback on message complete provided')

        self.sock.listen(self.max_conns)
        polling = epoll()
        self.epoll = polling
        polling.register(self.sock, EPOLLIN)

        # look-ups
        sock = self.sock
        serversock_fileno = sock.fileno()
        conns = self._conns
        call_handler = self._call_handler
        disconnect = self._disconnect_handler
        connect = self._connect_handler
        receive = self._receive_handler
        response = self._response_handler
        poll = polling.poll
        accept = sock.accept

        while True:
            for fileno, event in poll(1):
                if fileno == serversock_fileno:
                    conn, addr = accept()
                    call_handler(connect, conn)
                    conn.setblocking(False)
                    polling.register(conn, EPOLLIN)
                    conns[conn.fileno()] = conn
                elif event & EPOLLIN:
                    conn = conns[fileno]

                    try:
                        peek_byte = conn.recv(1, MSG_PEEK)
                    except ConnectionResetError:
                        call_handler(disconnect, conns.pop(fileno))
                        continue

                    if not peek_byte:
                        call_handler(disconnect, conns.pop(fileno))
                        continue

                    call_handler(receive, conn)
                elif event & EPOLLOUT:
                    call_handler(response, conns[fileno])
                elif event & EPOLLHUP:
                    call_handler(disconnect, conns.pop(fileno))
