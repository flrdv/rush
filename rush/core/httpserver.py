"""
THIS IS AN EXPERIMENTAL IMPLEMENTATION OF HTTP SERVER, BUT MERGED WITH EPOLLSERVER
"""

from queue import Queue
from socket import MSG_PEEK
from http_parser.http import HttpParser
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLHUP

EPOLLIN_AND_EPOLLOUT = EPOLLIN | EPOLLOUT
DEFAULT_RECV_BLOCK_SIZE = 8192  # how many bytes are receiving per 1 socket read
QUEUE_SIZE = 10000


class HttpServer:
    def __init__(self, sock, max_conns):
        self.on_message_complete_callback = None

        self.sock = sock
        self.max_conns = max_conns
        self.epoll = None
        self._conns = {}    # fileno: conn

        # I'm using http-parser but not parsing just to know when request has been ended
        # anyway I'm putting parser-object to the queue, so no new parsers entities
        # will be created
        self._requests_buff = {}  # conn: [parser, raw]
        self._responses_buff = {}  # conn: b'...'

        self.requests = Queue(maxsize=QUEUE_SIZE)

    def _receive_handler(self, conn):
        parser, previously_received_body = self._requests_buff[conn]
        received_body_part = conn.recv(DEFAULT_RECV_BLOCK_SIZE)
        parser.execute(received_body_part, len(received_body_part))

        if parser.is_partial_body():
            self._requests_buff[conn][1] += parser.recv_body()

        if parser.is_message_complete():
            body = self._requests_buff[conn][1]
            self.on_message_complete_callback(body, conn, parser.get_version(),
                                              parser.get_method(), parser.get_path(),
                                              parser.get_query_string(), parser.get_headers())
            self._requests_buff[conn] = [HttpParser(decompress=True), b'']

    def _response_handler(self, conn):
        bytes_string = self._responses_buff[conn]
        bytes_sent = conn.send(bytes_string)
        new_bytes_string = bytes_string[bytes_sent:]
        self._responses_buff[conn] = new_bytes_string

        if not new_bytes_string:
            self.epoll.modify(conn, EPOLLIN)

    def _connect_handler(self, conn):
        # creating cell for conn once to avoid if-conditions in _receive_handler and
        # _response_handler every time receiving new event on socket read/write
        self._requests_buff[conn] = [HttpParser(decompress=True), b'']
        self._responses_buff[conn] = b''

    def _disconnect_handler(self, conn):
        self._requests_buff.pop(conn)
        self._responses_buff.pop(conn)
        conn.close()

    def send(self, conn, data: bytes):
        if not self._responses_buff[conn]:
            self.epoll.modify(conn, EPOLLIN_AND_EPOLLOUT)

        self._responses_buff[conn] += data

    def run(self):
        if self.on_message_complete_callback is None:
            raise RuntimeError('no callback on message complete provided')

        self.sock.listen(self.max_conns)
        polling = epoll()
        self.epoll = polling
        polling.register(self.sock, EPOLLIN)

        while True:
            events = polling.poll(1)

            for fileno, event in events:
                if fileno == self.sock.fileno():
                    conn, addr = self.sock.accept()
                    self._connect_handler(conn)
                    conn.setblocking(False)
                    polling.register(conn, EPOLLIN)
                    self._conns[conn.fileno()] = conn
                elif event & EPOLLIN:
                    conn = self._conns[fileno]

                    try:
                        peek_byte = conn.recv(1, MSG_PEEK)
                    except ConnectionResetError:
                        self._disconnect_handler(self._conns.pop(fileno))
                        continue

                    if not peek_byte:
                        self._disconnect_handler(self._conns.pop(fileno))
                        continue

                    self._receive_handler(conn)
                elif event & EPOLLOUT:
                    self._response_handler(self._conns[fileno])
                elif event & EPOLLHUP:
                    self._disconnect_handler(self._conns.pop(fileno))
