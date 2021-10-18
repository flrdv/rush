import abc


class HTTPServer(abc.ABC):
    def poll(self) -> None:
        """
        Blocking function that runs server infinity, but may be interrupted
        by exception that should be caught by webserver, processed, and
        continue polling by calling this function again
        """
