import abc

from entities import Request


class Dispatcher(abc.ABC):
    """
    A base class to be inherited of for all the dispatchers implementations
    """

    async def process_request(self, request: Request):
        """
        The only method we need from dispatcher
        """
