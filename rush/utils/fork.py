"""
A module for forking choosing the best way that os provides

For example, Windows does not supports processes forks, but linux does
And so on
"""

from platform import system
from typing import List, Union


OS = system()


def _unix_fork(n: int) -> Union[List[int], None]:
    from os import fork as unix_fork

    children = []

    for _ in range(n):
        child_pid = unix_fork()

        if child_pid != 0:
            children.append(child_pid)
        else:
            return


if OS == 'Linux':
    fork = _unix_fork
