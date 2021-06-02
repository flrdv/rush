"""
Internal module for http interacting. All the functions, methods, etc. should be
proxied
"""

from queue import Queue
from select import EPOLLIN, EPOLLOUT
from http_parser.http import HttpParser

from lib import epollserver

DEFAULT_RECV_BLOCK_SIZE = 8192  # how many bytes are receiving per 1 socket read
QUEUE_SIZE = 1000


class HttpServer:
    def __init__(self, sock, max_conns):
        """
        Basic http server built on lib.epollserver

        Just receives raw bytes and puts them into the HttpServer.requests Queue object
        Puts into the Queue object such an objects: (data: bytes, conn: socket.socket,
                                                     parser: http_parser.http.HttpParser)
        """

        self.epollserver = epollserver.EpollServer(sock, maxconns=max_conns)
        self.epollserver.add_handler(self._connect_handler, epollserver.CONNECT)
        self.epollserver.add_handler(self._disconnect_handler, epollserver.DISCONNECT)
        self.epollserver.add_handler(self._receive_handler, epollserver.RECEIVE)
        self.epollserver.add_handler(self._response_handler, epollserver.RESPONSE)

        # I'm using http-parser but not parsing just to know when request has been ended
        # anyway I'm putting parser-object to the queue, so no new parsers entities
        # will be created
        self._requests_buff = {}    # conn: [parser, raw]
        self._responses_buff = {}   # conn: b'...'

        self.requests = Queue(maxsize=QUEUE_SIZE)

    def _receive_handler(self, _, conn):
        parser, previously_received_body = self._requests_buff[conn]
        received_body_part = conn.recv(DEFAULT_RECV_BLOCK_SIZE)
        parser.execute(received_body_part, len(received_body_part))

        """
        if message has been completely received, clear the buffer and send result to the queue
        elif we received part of the body
        """

        if parser.is_message_complete():
            self.requests.put((previously_received_body + parser.recv_body(), conn, parser))
            self._requests_buff[conn] = [HttpParser(decompress=True), b'']
        elif parser.is_partial_body():
            self._requests_buff[conn][1] += parser.recv_body()

    def _response_handler(self, _, conn):
        bytes_string = self._responses_buff[conn]
        bytes_sent = conn.send(bytes_string)
        new_bytes_string = bytes_string[:bytes_sent]
        self._responses_buff[conn] = new_bytes_string

        if not new_bytes_string:
            self.epollserver.direct_modify(conn, EPOLLIN)

    def _connect_handler(self, _, conn):
        # creating cell for conn once to avoid if-conditions in _receive_handler and
        # _response_handler every time receiving new event on socket read/write
        self._requests_buff[conn] = [HttpParser(decompress=True), b'']
        self._responses_buff[conn] = b''

    def _disconnect_handler(self, _, conn):
        self._requests_buff.pop(conn)
        self._responses_buff.pop(conn)

    def send(self, conn, data: bytes):
        if not self._responses_buff[conn]:
            self.epollserver.direct_modify(conn, EPOLLIN | EPOLLOUT)

        self._responses_buff[conn] += data

    def start(self):
        self.epollserver.start(threaded=False)
