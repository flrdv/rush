"""
    SFS is a Static Files Subsystem - system for caching and sending
    files to user by their path. May be used as for static content delivering,
    as for anything else, including local server's filesystem watching
    """

from typing import Dict, Union

from .typehints import Path, Connection, HttpResponseCallback, FileDescriptor


class SFS:
    def add_file(self, path: Path) -> None:
        """
        Add file by it's path
        """

    def remove_file(self, path: Path) -> None:
        """
        Remove file by it's path
        """

    def send_file(self,
                  path: Path,
                  conn: Connection,
                  http_response: HttpResponseCallback,
                  code: int,
                  status: Union[str, bytes, None],
                  headers: Union[Dict, None]
                  ) -> None:
        """
        Send a http response all by cache.


        """


class SimpleDevSFS(SFS):
    """
    A simple cache based on socket.socket.sendfile() and no security
    and fool checks
    """

    files: Dict[Path, FileDescriptor] = {}

    def add_file(self, path: Path) -> None:
        self.files[path] = open(path, 'rb')

    def remove_file(self, path: Path) -> None:
        self.files.pop(path).close()

    def send_file(self,
                  path: Path,
                  conn: Connection,
                  http_response: HttpResponseCallback,
                  code: int,
                  status: Union[str, bytes, None],
                  headers: Union[Dict, None]
                  ) -> None:
        ...
