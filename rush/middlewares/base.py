import abc
from typing import Awaitable

from ..entities import Request, Response


class BaseMiddleware(abc.ABC):
    @abc.abstractmethod
    async def process(self,
                      handler: Awaitable,
                      request: Request) -> Response:
        """
        A place where handler must be called. Note: handler is not always _endpoint_ handler,
        but in case of multiple middlewares it is mostly another middlewares
        """
