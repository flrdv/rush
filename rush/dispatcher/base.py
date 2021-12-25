import abc
from typing import Callable

from ..entities import Request, Response


class BaseDispatcher(abc.ABC):
    """
    A base class to be inherited of for all the dispatchers implementations
    """

    def on_begin_serving(self):
        """
        Just a callback after server starts working. May be useful
        in cases when something needs to be processed after initialization
        phase will be finished

        This method is optional
        """

    @abc.abstractmethod
    async def process_request(self,
                              request: Request,
                              response: Response,
                              http_send: Callable[[bytes], None]) -> Response:
        """
        The only method we need from dispatcher
        """
