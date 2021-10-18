import socket
from typing import Callable, BinaryIO

Path = str
FileDescriptor = BinaryIO
URI = bytes
URIParameters = bytes
URIFragment = bytes
HTTPMethod = bytes
HTTPVersion = str
Connection = socket.socket
HttpResponseCallback = Callable
