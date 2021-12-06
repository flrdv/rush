import socket
from typing import Callable, Awaitable, BinaryIO, Union, NewType, Protocol

AsyncFunction = Callable[..., Awaitable]
Path = str
RoutePath = Union[str, bytes]
FileDescriptor = BinaryIO
URI = bytes
URIParameters = bytes
URIFragment = bytes
HTTPMethod = bytes
HTTPMethods = set
HTTPVersion = str
Connection = socket.socket
HttpResponseCallback = Callable
Nothing = NewType('Nothing', None)


class Logger(Protocol):
    def debug(self, text: str) -> None:
        ...

    def info(self, text: str) -> None:
        ...

    def warning(self, text: str) -> None:
        ...

    def error(self, text: str) -> None:
        ...

    def critical(self, text: str) -> None:
        ...

    def exception(self, text: str) -> None:
        ...
