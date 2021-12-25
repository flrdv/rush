"""
Storage is a storage with static (not only static, any is available but only
static is available by default) - system for caching and sending
files to user by their path. May be used as for static content delivering,
as for anything else, including local server's filesystem watching
"""

import abc
from typing import Union, Dict

from ..typehints import Path, Connection, HttpResponseCallback


class Storage(abc.ABC):
    @abc.abstractmethod
    def add_file(self, path: Path) -> None:
        """
        Add file by it's path
        """

    @abc.abstractmethod
    def remove_file(self, path: Path) -> None:
        """
        Remove file by it's path
        """

    @abc.abstractmethod
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
