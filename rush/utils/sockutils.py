import socket
from time import sleep
from typing import Tuple, Union


def bind_sock(
        sock: socket.socket,
        addr: Tuple[str, Union[int, str]],
        max_retries: int = 99999,
        retries_timeout: Union[int, float] = 3
):
    for retry_num in range(1, max_retries + 1):
        try:
            sock.bind(addr)

            return True, retry_num
        except OSError:
            sleep(retries_timeout)

    return False, max_retries
