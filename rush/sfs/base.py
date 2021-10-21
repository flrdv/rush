"""
SFS is a Static Files Subsystem - system for caching and sending
files to user by their path. May be used as for static content delivering,
as for anything else, including local server's filesystem watching
"""

import abc
from typing import Union, Dict

from ..typehints import Path, Connection, HttpResponseCallback


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
