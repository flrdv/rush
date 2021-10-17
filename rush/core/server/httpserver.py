import socket
import asyncio
import logging
from socket import MSG_PEEK
from threading import Thread
from traceback import format_exc
from typing import Union, Dict, List, Callable, Awaitable
from select import epoll, EPOLLIN, EPOLLOUT

from httptools import HttpRequestParser
from httptools.parser.errors import HttpParserError, HttpParserCallbackError

from rush.entities import CaseInsensitiveDict, Request
from rush.utils.httputils import decode_url

logger = logging.getLogger(__name__)

EPOLLIN_AND_EPOLLOUT = EPOLLIN | EPOLLOUT
DEFAULT_RECV_BLOCK_SIZE = 16384  # how many bytes are receiving per 1 socket read


class Protocol:
    """
    Initializing headers dictionary in the beginning, but individual for every
    object
    """
    headers = CaseInsensitiveDict()

    def __init__(self,
                 conn: socket.socket,
                 eventloop: asyncio.BaseEventLoop,
                 request_obj: Request,
                 callback: Callable[[Request], Awaitable]
                 ):
        self.conn = conn
        self.eventloop = eventloop
        self.request_obj = request_obj
        self.callback = callback

        self.path = None
        self.parameters = b''
        self.fragment = None
        self.body = b''
        self.file = False

        self.received: bool = False

        self._on_chunk: Union[Callable[[bytes], Awaitable], None] = None
        self._on_complete: Union[Callable[[], Awaitable], None] = None

    def on_url(self, url: bytes):
        if b'%' in url:
            url = decode_url(url)

        if b'?' in url:
            url, self.parameters = url.split(b'?', 1)

            if b'#' in self.parameters:
                self.parameters, self.fragment = self.parameters.split(b'#', 1)
        elif b'#' in self.parameters:
            url, self.fragment = url.split(b'#', 1)

        self.path = url.rstrip(b'/') or b'/'

    def on_header(self, name: bytes, value: bytes):
        self.headers[name.decode()] = value.decode()

    def on_headers_complete(self):
        if self.headers.get('transfer-encoding') == 'chunked' or \
                self.headers.get('content-type', '').startswith('multipart/'):
            self.file = True
            self._request_obj_task = self.eventloop.create_task(
                self.callback(
                    
                )
            )

    def on_body(self, body: bytes):
        if self._request_obj_task:
            request_obj = self._request_obj_task.result()

            # if request object is None, it means that we just got automatic
            # redirect
            if request_obj is not None:
                # so long ang ugly only cause variables unpacking takes
                # only 1 instruction for PVM
                self._on_chunk, self._on_complete = request_obj.on_chunk, request_obj.on_complete

            self._request_obj_task = None

        if self._on_chunk:
            self.eventloop.create_task(self._on_chunk(body))
        else:
            self.body += body

    def on_message_complete(self):
        self.received = True

        if self._on_complete:
            self._on_complete()


class HttpServer:
    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 callback):
        self.on_message_complete = callback
        self.sock = sock
        self.max_conns = max_conns
        self.epoll = None
        self._conns = {}  # fileno: conn

        # every client has only one entity of parser and protocol
        # on each request, entities are just re-initializing
        self._requests_buff = {}  # conn: (parser, protocol_instance)
        self._responses_buff = {}  # conn: b'...'

        self.eventloop = asyncio.new_event_loop()

    def _receive_handler(self, conn: socket.socket):
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
            protocol.__init__(conn)
            parser.__init__(protocol)
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
