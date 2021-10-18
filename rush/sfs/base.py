import abc
from typing import Union, Dict

from typehints import Path, Connection, HttpResponseCallback


class SFS(abc.ABC):
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
        Send a http response all by Static Files Subsystem.
        """
