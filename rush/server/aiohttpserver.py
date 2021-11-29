import socket
import asyncio
from typing import Optional

import uvloop
from uvloop.loop import TCPTransport

from httptools import HttpRequestParser

from . import base
from ..storage.base import Storage
from ..entities import Request
from ..typehints import Coroutine
from ..parser.httptools_protocol import Protocol as LLHttpProtocol

uvloop.install()


def server_protocol_factory(
        on_message_complete: Coroutine,
        storage: Storage
) -> 'AsyncioServerProtocol':
    request_obj = Request(
        lambda data: 'will be set later',
        storage
    )
    protocol = LLHttpProtocol(request_obj)
    parser = HttpRequestParser(protocol)
    protocol.parser = parser

    return AsyncioServerProtocol(
        on_message_complete,
        protocol,
        parser,
        request_obj,
        storage
    )


class AsyncioServerProtocol(asyncio.Protocol):
    def __init__(self,
                 on_message_complete: Coroutine,
                 protocol: LLHttpProtocol,
                 parser: HttpRequestParser,
                 request_obj: Request,
                 storage: Storage):
        self.on_message_complete = on_message_complete
        self.transport: Optional[TCPTransport] = None
        self.protocol = protocol
        self.parser = parser
        self.request_obj = request_obj
        self.storage = storage

        self.first_time: bool = True

    def connection_made(self, transport: TCPTransport) -> None:
        self.transport = transport
        self.request_obj.set_http_callback(transport.write)

    def data_received(self, data: bytes) -> None:
        self.parser.feed_data(data)

        if self.protocol.received:
            asyncio.create_task(
                self.on_message_complete(self.request_obj)
            )
            self.protocol.__init__(
                self.request_obj
            )
            self.parser.__init__(
                self.protocol
            )
            self.protocol.parser = self.parser


class AioHTTPServer(base.HTTPServer):
    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 on_message_complete: Coroutine,
                 storage: Storage,
                 **kwargs):
        sock.listen(max_conns)

        self.sock = sock
        self.on_message_complete = on_message_complete
        self.storage = storage
        self.server: Optional[asyncio.AbstractServer] = None

    async def poll(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: server_protocol_factory(
                self.on_message_complete,
                self.storage
            ),
            sock=self.sock,
            start_serving=False
        )
        self.server = server

        await server.serve_forever()

    def stop(self):
        self.server.close()
