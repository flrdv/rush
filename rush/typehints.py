import socket
from typing import Callable, BinaryIO

Path = str
FileDescriptor = BinaryIO
URI = bytes
HTTPMethod = bytes
HTTPVersion = str
Connection = socket.socket
HttpResponseCallback = Callable
