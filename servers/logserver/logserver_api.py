from json import dumps
from socket import socket
from time import time, sleep

from lib.msgproto import sendmsg
from lib.epollserver import do_handshake


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
        self.thread_tasks = []  # (func, args, kwargs)
        # this buffer will contain all the log entries which were failed to send
        # they will be sent as soon as api will connect to logserver
        self.log_entries_buffer = []

    def connect(self):
        try:
            self.sock.connect(self.addr)

            if not do_handshake(self.sock, 'logserver'):
                print(f'[LOGSERVER-API] Failed to connect to {self.ip}:{self.port}: handshake failure')
                self.set_new_sock()

                return False

            self._connected = True
        except (ConnectionResetError, ConnectionRefusedError) as exc:
            print(f'[LOGSERVER-API] Failed to connect to {self.ip}:{self.port} ({exc})')

            return False

        return True

    def set_new_sock(self):
        self.sock.close()
        self.sock = socket()

    def reconnect(self):
        self.set_new_sock()
        self.connect()

    def write(self, type_, text, date: (int, float) = None):
        if not self._connected:
            print('[LOGSERVER-API] Unable to add new log entry: not connected to log server')
            print('[LOGSERVER-API] Log entry will be kept in the buffer until connection won\'t be established')

            self.log_entries_buffer.append((type_, text, date))
            self.add_worker_task(self.connect)

            return

        if date is None or not isinstance(date, (int, float)):
            date = time()

        self.add_worker_task(self.send_json, (date, type_, text))

    def send_json(self, date, type_, text):
        try:
            sendmsg(self.sock, dumps([date, type_, text]).encode())
        except (BrokenPipeError, OSError) as exc:
            print('[LOGSERVER-API] An error occurred while writing new log entry '
                  f'to log-server ({self.ip}:{self.port}): {exc}')
            self.add_worker_task(self.reconnect)

    def add_worker_task(self, func, args=(), kwargs=None):
        self.thread_tasks.append((func, args, kwargs or {}))

    def worker(self):
        """
        This is a thread to run api methods in non-blocking mode
        like re-connecting or writing to logs
        """

        while True:
            if not self.thread_tasks:
                sleep(.1)

            for (func, args, kwargs) in self.thread_tasks:
                func(*args, **kwargs)

            if self._connected and self.log_entries_buffer:
                for log_entry in self.log_entries_buffer:
                    self.write(*log_entry)
