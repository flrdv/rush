import abc
import socket
from typing import Callable

from ..storage.base import Storage
from ..typehints import AsyncFunction
from ..entities import CaseInsensitiveDict


class HTTPServer(abc.ABC):
    """
    Base class for HTTP server implementation

    Includes implementation of __init__ method, and abstract poll(), stop()
    """

    def __init__(self,
                 sock: socket.socket,
                 max_conns: int,
                 on_begin_serving: Callable,
                 on_message_complete: AsyncFunction,
                 storage: Storage,
                 default_headers: CaseInsensitiveDict):
        self.sock = sock
        self.max_conns = max_conns
        self.on_begin_serving = on_begin_serving
        self.on_message_complete = on_message_complete
        self.storage = storage
        self.default_headers = default_headers

    @abc.abstractmethod
    async def poll(self) -> None:
        """
        Blocking function that runs server infinity, but may be interrupted
        by exception that should be caught by webserver, processed, and
        continue polling by calling this function again
        """

    @abc.abstractmethod
    def stop(self):
        """
        Stops the server in correct way
        """
