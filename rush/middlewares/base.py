import abc

from ..typehints import Coroutine
from ..entities import Request, Response


class BaseMiddleware(abc.ABC):
    @abc.abstractmethod
    async def process(self,
                      handler: Coroutine,
                      request: Request,
                      response: Response) -> Coroutine:
        """
        A place where handler must be called. Note: handler is not always _endpoint_ handler,
        but in case of multiple middlewares it is mostly another middlewares
        """
