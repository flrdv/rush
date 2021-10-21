import socket
import asyncio
from typing import Optional
from uvloop.loop import TCPTransport

from httptools import HttpRequestParser

from . import base
from ..sfs.base import SFS
from ..entities import Request
from ..typehints import Coroutine
from .httpserver import Protocol as LLHttpProtocol


class AsyncioServerProtocol(asyncio.Protocol):
    def __init__(self, on_message_complete: Coroutine, *args, **kwargs):
        self.transport: Optional[TCPTransport] = None
        self.protocol: Optional[LLHttpProtocol] = None
        self.parser: Optional[HttpRequestParser] = None
        self.request_obj: Optional[Request] = None
        self.on_message_complete = on_message_complete

        super(AsyncioServerProtocol, self).__init__(*args, **kwargs)

    def connection_made(self, transport: TCPTransport) -> None:
        self.transport = transport
        self.request_obj = Request(
            transport.write,
            SFS()
        )

        if not self.protocol:
            self.protocol = LLHttpProtocol(
                conn=self.transport.get_extra_info('socket'),
                request_obj=self.request_obj
            )

        if self.protocol.received:
            """
            HOW THE FUCK SHOULD I AWAIT HANDLER HERE
            """

    def data_received(self, data: bytes) -> None:
        ...


class AioHTTPServer(base.HTTPServer):
    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 on_message_complete: Coroutine,
                 sfs: SFS,
                 write_logs: bool = True):
        loop = asyncio.get_running_loop()
        self.server = await loop.create_server(
            AsyncioServerProtocol,
            sock=sock,
            start_serving=False
        )

        self.on_message_complete = on_message_complete
        self.sfs = sfs

    async def poll(self):
        await self.server.serve_forever()
