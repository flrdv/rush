import uvloop
import asyncio
from functools import partial
from typing import Optional
from uvloop.loop import TCPTransport
from multiprocessing import Process, cpu_count


class SimpleAsyncioServer(asyncio.Protocol):
    def __init__(self, callback, *args, **kwargs):
        self.transport: Optional[TCPTransport] = None
        self.callback = callback
        super(SimpleAsyncioServer, self).__init__(*args, **kwargs)

    def connection_made(self, transport: TCPTransport):
        self.transport = transport

    def data_received(self, data: bytes):
        asyncio.create_task(self.callback(self.transport, data))


async def process_request(transport, data: bytes):
    transport.write(
        b"HTTP/1.1 200 OK\r\nContent-Length:13\r\n\r\nHello, world!"
    )


def run_main(host, port):
    asyncio.run(main(host, port))


async def main(host, port):
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: SimpleAsyncioServer(process_request),
        host, port,
        reuse_port=True
    )

    await server.serve_forever()


children = []
uvloop.install()

if __name__ == '__main__':
    for i in range(cpu_count() - 1):
        process = Process(target=run_main, args=('127.0.0.1', 9092,))
        process.start()
        children.append(process)

try:
    run_main('127.0.0.1', 9092)
except KeyboardInterrupt:
    for child in children:
        child.kill()
