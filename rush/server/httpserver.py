import socket
import asyncio
import logging
from socket import MSG_PEEK
from traceback import format_exc
from typing import Union, Dict, Tuple
from select import epoll, EPOLLIN, EPOLLOUT

from httptools import HttpRequestParser
from httptools.parser.errors import HttpParserError, HttpParserCallbackError

from rush import exceptions
from .base import HTTPServer
from rush.sfs.base import SFS
from rush.utils.httputils import decode_url
from rush.entities import Request
from rush.typehints import Connection, Coroutine, Nothing

logger = logging.getLogger(__name__)

EPOLLIN_AND_EPOLLOUT = EPOLLIN | EPOLLOUT
RECV_BLOCK_SIZE = 16384  # how many bytes are receiving per 1 socket read


class Protocol:
    def __init__(self,
                 request_obj: Request,
                 ):
        self.request_obj = request_obj

        self.body = b''
        self.file = False

        self.received: bool = False

        self._on_chunk: Union[Coroutine, None] = None
        self._on_complete: Union[Coroutine[Nothing], None] = None

        self.parser: Union[HttpRequestParser, None] = None

    def on_url(self, url: bytes):
        if b'%' in url:
            url = decode_url(url)

        parameters = fragment = None

        if b'?' in url:
            url, parameters = url.split(b'?', 1)

            if b'#' in parameters:
                parameters, fragment = parameters.split(b'#', 1)
        elif b'#' in url:
            url, fragment = url.split(b'#', 1)

        self.request_obj.set_protocol(self.parser.get_http_version())
        self.request_obj.set_path(url)
        self.request_obj.set_params(parameters)
        self.request_obj.set_fragment(fragment)

    def on_header(self, name: bytes, value: bytes):
        self.request_obj.set_header(name.decode(), value.decode())

    def on_headers_complete(self):
        request_headers = self.request_obj.headers()

        if request_headers.get('transfer-encoding') == 'chunked' or \
                request_headers.get('content-type', '').startswith('multipart/'):
            self.file = True
            self._on_chunk, self._on_complete = \
                self.request_obj.get_on_chunk(), self.request_obj.get_on_complete()

    def on_body(self, body: bytes):
        if self._on_chunk:
            self._on_chunk(body)
        else:
            self.body += body

    def on_body_complete(self):
        self.request_obj.set_body(self.body)

    def on_message_complete(self):
        self.received = True

        if self._on_complete:
            self._on_complete()


class EpollHttpServer(HTTPServer):
    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 on_message_complete: Coroutine,
                 sfs: SFS,
                 write_logs: bool = True):
        self.on_message_complete = on_message_complete
        self.sock: Connection = sock
        self.max_conns: int = max_conns
        self.epoll: Union[epoll, None] = None
        self._conns: Dict[int, Connection] = {}  # fileno: conn
        self.sfs = sfs

        logger.disabled = not write_logs

        # every client has only one entity of parser and protocol
        # on each request, entities are just re-initializing
        self._requests_buff: Dict[Connection, Tuple[HttpRequestParser, Protocol]] = {}
        self._responses_buff: Dict[Connection, bytes] = {}  # conn: b'...'

    async def _receive_handler(self, conn: socket.socket):
        parser, protocol = self._requests_buff[conn]

        try:
            parser.feed_data(conn.recv(RECV_BLOCK_SIZE))
        except HttpParserCallbackError as exc:
            logger.error(f'an error occurred in callback: {exc}')
            logger.exception(f'full error trace:\n{format_exc()}')

            return await self._call_handler(self._disconnect_handler,
                                            self._conns.pop(conn.fileno()))
        except HttpParserError as exc:
            # if some error occurred, relationship won't be good in future
            logger.error(f'disconnected user due to parsing request error: {exc}')

            return await self._call_handler(self._disconnect_handler,
                                            self._conns.pop(conn.fileno()))

        if protocol.received:
            protocol.__init__(
                protocol.request_obj,
            )
            parser.__init__(protocol)
            self._requests_buff[conn] = (parser, protocol)

    async def _response_handler(self, conn):
        current_bytestring = self._responses_buff[conn]
        bytestring_left = current_bytestring[conn.send(current_bytestring):]
        self._responses_buff[conn] = bytestring_left

        if not bytestring_left:
            self.epoll.modify(conn, EPOLLIN)

    async def _connect_handler(self, conn):
        # creating cell for conn once to avoid if-conditions in _receive_handler and
        # _response_handler every time receiving new event on socket read/write
        protocol_instance = Protocol(
            Request(self.send, self.sfs),
        )
        new_parser = HttpRequestParser(protocol_instance)
        protocol_instance.parser = new_parser
        self._requests_buff[conn] = (new_parser, protocol_instance)
        self._responses_buff[conn] = b''

    async def _disconnect_handler(self, conn):
        self._requests_buff.pop(conn)
        self._responses_buff.pop(conn)
        conn.close()

    @staticmethod
    async def _call_handler(handler, conn):
        try:
            await handler(conn)
        except Exception as exc:
            raise exceptions.WebServerError(format_exc())

    def send(self, conn, data: bytes):
        sent = conn.send(data)

        if sent == len(data):
            return

        if not self._responses_buff[conn]:
            self.epoll.modify(conn, EPOLLIN_AND_EPOLLOUT)

        self._responses_buff[conn] += data[sent:]

    async def poll(self):
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
                    await call_handler(connect, conn)
                    conn.setblocking(False)
                    polling.register(conn, EPOLLIN)
                    conns[conn.fileno()] = conn
                elif event & EPOLLIN:
                    conn = conns[fileno]

                    try:
                        peek_byte = conn.recv(1, MSG_PEEK)
                    except ConnectionResetError:
                        await call_handler(disconnect, conns.pop(fileno))
                        continue

                    if not peek_byte:
                        await call_handler(disconnect, conns.pop(fileno))
                        continue

                    await call_handler(receive, conn)
                elif event & EPOLLOUT:
                    await call_handler(response, conns[fileno])
                else:
                    raise NotImplementedError(f'unknown epoll event: {event}')

    def stop(self):
        for conn in self._conns.values():
            conn.close()

        self.epoll.close()
        self._responses_buff.clear()
        self._requests_buff.clear()

    def __del__(self):
        self.stop()
