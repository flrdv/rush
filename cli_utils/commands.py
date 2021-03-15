from threading import Thread
from importlib import import_module


def _parse_addr(addr):
    ip, port = addr.split(':')

    return ip, int(port)


aliases = {
}
