import socket
from typing import Callable, Any, Awaitable, BinaryIO, Union, NewType

Coroutine = Callable[[Any], Awaitable]
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
