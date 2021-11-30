import socket
import asyncio
import warnings
from typing import Optional

try:
    from uvloop import install as install_uvloop
    from uvloop.loop import TCPTransport
except ImportError as exc:
    from asyncio.transports import BaseTransport as TCPTransport

    def install_uvloop():
        warnings.warn(f'failed to apply uvloop ({exc}), performance will be decreased')


from httptools import HttpRequestParser

from . import base
from ..storage.base import Storage
from ..typehints import AsyncFunction
from ..entities import Request, Response, CaseInsensitiveDict
from ..parser.httptools_protocol import Protocol as LLHttpProtocol

install_uvloop()


def server_protocol_factory(
        on_message_complete: AsyncFunction,
        storage: Storage,
        default_headers: CaseInsensitiveDict
) -> 'AsyncioServerProtocol':

    request_obj = Request(storage)
    response_obj = Response(default_headers)
    protocol = LLHttpProtocol(request_obj)
    parser = HttpRequestParser(protocol)
    protocol.parser = parser

    return AsyncioServerProtocol(
        on_message_complete,
        protocol,
        parser,
        request_obj,
        response_obj,
        storage
    )


class AsyncioServerProtocol(asyncio.Protocol):
    def __init__(self,
                 on_message_complete: AsyncFunction,
                 protocol: LLHttpProtocol,
                 parser: HttpRequestParser,
                 request_obj: Request,
                 response_obj: Response,
                 storage: Storage):
        self.on_message_complete = on_message_complete
        self.transport: Optional[TCPTransport] = None
        self.protocol = protocol
        self.parser = parser
        self.request_obj = request_obj
        self.response_obj = response_obj
        self.storage = storage

    def connection_made(self, transport: TCPTransport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        self.parser.feed_data(data)

        if self.protocol.received:
            asyncio.create_task(
                # I really don't know why linter thinks that TCPTransport doesn't provide `write()` method
                # but I haven't tried this without uvloop, so don't know whether this will work for
                # vanilla asyncio transport
                self.on_message_complete(
                    self.request_obj,
                    self.response_obj,
                    self.transport.write    # noqa
                )
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
                 on_message_complete: AsyncFunction,
                 storage: Storage,
                 default_headers: CaseInsensitiveDict,
                 **kwargs):
        sock.listen(max_conns)

        self.sock = sock
        self.on_message_complete = on_message_complete
        self.storage = storage
        self.server: Optional[asyncio.AbstractServer] = None
        self.default_headers = default_headers

    async def poll(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: server_protocol_factory(
                self.on_message_complete,
                self.storage,
                self.default_headers
            ),
            sock=self.sock,
            start_serving=False
        )
        self.server = server

        await server.serve_forever()

    def stop(self):
        self.server.close()
