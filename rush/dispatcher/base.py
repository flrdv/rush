import abc
from typing import Callable

from ..entities import Request, Response


class BaseDispatcher(abc.ABC):
    """
    A base class to be inherited of for all the dispatchers implementations
    """

    @abc.abstractmethod
    async def process_request(self,
                              request: Request,
                              response: Response,
                              http_send: Callable[[bytes], None]) -> Response:
        """
        The only method we need from dispatcher
        """
