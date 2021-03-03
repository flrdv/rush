from time import time
from json import dumps
from socket import socket

from lib.msgproto import sendmsg


class LogServerApi:
    def __init__(self, addr=('localhost', 11101), auto_self_reload=True):
        """
        :param addr: address of log-server
        :param auto_self_reload: should api reconnect automatically after errors
        """

        self.addr = addr
        self.ip, self.port = addr
        self.sock = socket()

        self._connected = False

    def connect(self):
        try:
            self.sock.connect(self.addr)
            self._connected = True
        except (ConnectionResetError, ConnectionRefusedError) as exc:
            print(f'[LOGSERVER-API] Failed to connect to {self.ip}:{self.port} ({exc})')

        return self

    def write(self, type_, text, date: (int, float) = None):
        if not self._connected:
            print('[LOGSERVER-API] Unable to add new log entry: not connected to log server')
            return

        if date is None or not isinstance(date, (int, float)):
            date = time()

        try:
            sendmsg(self.sock, dumps([date, type_, text]).encode())
        except (BrokenPipeError, OSError) as exc:
            print('[LOGSERVER-API] An error occurred while writing new log entry '
                  f'to log-server ({self.ip}:{self.port}): {exc}')
            self._connected = False
