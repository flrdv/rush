from .typehints import Path, Connection, HttpResponseCallback


class Cache:
    def add_file(self, path: Path) -> None:
        """
        Add file by it's path
        """

    def remove_file(self, path: Path) -> None:
        """
        Remove file by it's path
        """

    def response_with_file(self,
                           conn: Connection,
                           http_response: HttpResponseCallback,
                           path: Path
                           ) -> None:
        """
        Send a http response all by cache.


        """


class SimpleInMemoryCache:
    ...
