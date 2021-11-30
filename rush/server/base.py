import abc


class HTTPServer(abc.ABC):
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
