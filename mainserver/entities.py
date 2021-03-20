import re
from json import loads, JSONDecodeError

from lib.msgproto import sendmsg

INITIAL_BYTES_SEQUENCE = b'\x69\x04\x02\x00'


def compare_filters(pattern: dict, source: dict):
    source_items = source.items()

    for key, value in pattern.items():
        for source_key, source_value in source_items:
            if re.fullmatch(key, source_key):
                if source_value is None or re.fullmatch(value, source_value):
                    break
        else:
            return False

    return True


class Filter:
    """
    Contains dict-sample and checks incoming request with dict-sample
    """

    def __init__(self, sample):
        self.sample = sample

    def __call__(self, request):
        return compare_filters(self.sample, request)


class Handler:
    """
    Contains handler filter (group), address, conn-object
    """

    def __init__(self, conn, filter_):
        self.conn = conn
        self.addr = conn.getpeername()
        self.ip, self.port = self.addr
        self.filter = filter_

        self.load = 100

    def get_conn(self):
        return self.conn

    def get_filter(self):
        return self.filter

    def set_filter(self, new_filter):
        self.filter = new_filter

    def get_addr(self):
        return self.addr

    def get_load(self):
        return self.load

    def set_load(self, value):
        self.load = value

    def send(self, data: bytes):
        self.conn.send(data)

    def recv(self, bytescount):
        return self.conn.recv(bytescount)


class HandlerInitializer:
    def __init__(self, conn):
        self.conn = conn

        self.current_step = 0

    def next_step(self, core_server, msg):
        if self.current_step > 2:
            raise RuntimeError('handler has been already initialized')

        response = self.steps[self.current_step](self, core_server, msg)
        self.current_step += 1

        return response

    def step1(self, core_server, msg):
        """
        Step 1: receive b'\x69\x04\x02\x00' and send reversed back
        """

        if msg != b'\x69\x04\x02\x00':
            return False

        self.conn.send(INITIAL_BYTES_SEQUENCE[::-1])

        return True

    def step2(self, core_server, msg):
        """
        Step 2: receive \x01 byte and send server's name
        """

        if msg != b'\x01':
            return False

        sendmsg(self.conn, core_server.name.encode())

        return True

    def step3(self, core_server, msg):
        """
        Step 3: receive handler's filter and response with
        """

        try:
            return loads(msg)
        except (ValueError, JSONDecodeError):
            return False

    steps = {
        0: step1,
        1: step2,
        2: step3
    }
