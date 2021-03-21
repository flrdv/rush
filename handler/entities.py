from json import dumps

from lib.msgproto import recvbytes, sendmsg, recvmsg

INITIAL_BYTES_SEQUENCE = b'\x69\x04\x02\x00'

_filters = {}


class Filter:
    def __new__(cls, values):
        dumped_values = dumps(values)

        if dumped_values in _filters:
            return _filters[dumped_values]

        instance = object.__new__(cls)
        _filters[dumped_values] = instance

        return instance

    def __init__(self, values: dict):
        self.filter = values


class HandshakeManager:
    """
    class that implements handshaking with mainserver

    do_handshake() returns 2 values: bool (whether
    handshake succeeded) and str (reason or mainserver
    name)
    """

    def __init__(self, conn):
        self.conn = conn

    def do_handshake(self, filter_: dict) -> [bool, str]:
        sendmsg(self.conn, INITIAL_BYTES_SEQUENCE)
        response = recvbytes(self.conn, len(INITIAL_BYTES_SEQUENCE), timeout=1)

        if response is None:
            return False, 'server is not responding'
        elif response != INITIAL_BYTES_SEQUENCE[::-1]:
            return False, 'received invalid bytes sequence'

        sendmsg(self.conn, b'\x01')
        mainserver_name = recvmsg(self.conn)

        sendmsg(self.conn, dumps(filter_).encode())

        return True, mainserver_name


class Packet:
    def __init__(self, values):
        self.values = values

    def get_values(self):
        return self.values

    def __getattr__(self, item):
        return self.values[item]
