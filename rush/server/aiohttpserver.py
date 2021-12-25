import socket
import asyncio
import warnings
from typing import Optional, Callable, NoReturn

from httptools import HttpRequestParser

try:
    from uvloop import install as install_uvloop
    from uvloop.loop import TCPTransport
except ImportError as exc:
    from asyncio.transports import BaseTransport as TCPTransport

    warnings.warn(f'failed to apply uvloop: {exc}')

    def install_uvloop():
        pass

from . import base
from ..storage.base import Storage
from ..typehints import AsyncFunction
from ..entities import Request, Response, CaseInsensitiveDict
from ..parser.httptools_protocol import Protocol as LLHttpProtocol


install_uvloop()
CLIENT_DISCONNECTED = 'constant for client runners tasks to stop themselves silently'


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

        # TODO: add limit for pending requests count
        # TODO: maybe move this to connection_made()?
        self.requests_queue = asyncio.Queue()

    def connection_made(self, transport: TCPTransport) -> None:
        self.transport = transport
        asyncio.create_task(client_runner(
            requests_queue=self.requests_queue,
            callback=self.on_message_complete,
            parser=self.parser,
            protocol=self.protocol,
            # I really don't know why linter thinks that TCPTransport
            # doesn't provide `write()` method but I haven't tried this
            # without uvloop, so don't know whether this will work for
            # vanilla asyncio transport
            response_client=transport.write,  # noqa
            request=self.request_obj,
            response=self.response_obj
        ))

    def data_received(self, data: bytes) -> None:
        asyncio.create_task(self.requests_queue.put(data))

    def connection_lost(self, _) -> None:
        # connection_lost callback receives one positional argument - Exception
        # object. But we actually don't need it, as we anyway doesn't care,
        # it's client's problem
        asyncio.create_task(self.requests_queue.put(CLIENT_DISCONNECTED))


class AioHTTPServer(base.HTTPServer):
    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 on_begin_serving: Callable,
                 on_message_complete: AsyncFunction,
                 storage: Storage,
                 default_headers: CaseInsensitiveDict):
        super(AioHTTPServer, self).__init__(
            sock=sock,
            max_conns=max_conns,
            on_begin_serving=on_begin_serving,
            on_message_complete=on_message_complete,
            storage=storage,
            default_headers=default_headers
        )

        self.server: Optional[asyncio.AbstractServer] = None
        sock.listen(max_conns)

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
        self.on_begin_serving()

        await server.serve_forever()

    def stop(self):
        self.server.close()


async def client_runner(requests_queue: asyncio.Queue,
                        callback: AsyncFunction,
                        parser: HttpRequestParser,
                        protocol: LLHttpProtocol,
                        response_client: Callable[[bytes], None],
                        request: Request,
                        response: Response) -> NoReturn:
    while True:
        data = await requests_queue.get()

        if data == CLIENT_DISCONNECTED:
            return

        parser.feed_data(data)

        if protocol.received:
            await callback(
                request,
                response,
                response_client
            )
            request.wipe()
            response.wipe()
            protocol.__init__(request)
            parser.__init__(protocol)
            protocol.parser = parser
