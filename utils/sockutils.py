from time import sleep


def wait_for_bind(sock, addr, bind_retries_timeout=1) -> None:
    while True:
        try:
            return sock.bind(addr)
        except OSError:
            sleep(bind_retries_timeout)
