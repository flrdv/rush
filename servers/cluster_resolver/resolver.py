import socket
import sqlite3
from typing import List
from json import loads, dumps
from select import epoll, EPOLLIN, EPOLLHUP

from rush.proto.msgproto import sendmsg, recvmsg


REGISTRY_DB = 'clusters-registry.sqlite3'
DEFAULT_ADDR = ('localhost', 11100)
PACKETS_CHUNK = 4096
WRITE_DATA = b'\x00'
READ_DATA = b'\x01'
RESPONSE_SUCC = b'\x02'
RESPONSE_FAIL = b'\x03'


def add_cluster_addr(cluster_name, ip, port):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO clusters VALUES (?, ?, ?)', (cluster_name, ip, port))
        conn.commit()


def get_cluster_addr(cluster_name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM clusters WHERE name=?', (cluster_name,))

        return cursor.fetchone()


class Resolver:
    def __init__(self, addr=DEFAULT_ADDR, maxconns=0):
        self.sock = socket.socket()
        self.sock.bind(addr)
        self.sock.listen(maxconns)

    def run_blocking_handler(self):
        poll = epoll()
        poll.register(self.sock.fileno(), EPOLLIN)

        try:
            conns = {}
            requests = {}

            while True:
                events = poll.poll(1)

                for fileno, event in events:
                    if fileno == self.sock.fileno():
                        conn, addr = self.sock.accept()
                        conn.setblocking(False)
                        conn_fileno = conn.fileno()
                        poll.register(conn_fileno, EPOLLIN)
                        conns[conn_fileno] = conn
                        requests[conn_fileno] = b''
                    elif event == EPOLLIN:
                        conn = conns[fileno]
                        full_packet = recvmsg(conn)

                        if len(full_packet) < 2:
                            sendmsg(conn, RESPONSE_FAIL + b'bad-request')
                            continue

                        decoded_full_packet = full_packet[1:].decode()

                        if full_packet.startswith(WRITE_DATA):
                            jsonified: List[str, str, int] = loads(decoded_full_packet)
                            add_cluster_addr(*jsonified)

                            print('[RESOLVER] Added cluster "{}" with addr {}:{}'.format(*jsonified))
                        elif full_packet.startswith(READ_DATA):
                            ip, port = get_cluster_addr(decoded_full_packet)
                            decoded_jsonified = dumps([ip, port]).encode()
                            sendmsg(conn, RESPONSE_SUCC + decoded_jsonified)

                            print(f'[RESOLVER] Getting cluster "{decoded_full_packet}" (cluster\'s addr is '
                                  f'{ip}:{port})')
                        else:
                            sendmsg(conn, RESPONSE_FAIL + b'bad-request-type')
                    elif event == EPOLLHUP:
                        poll.unregister(fileno)
                        conn = conns.pop(fileno)
                        conn.close()
                        requests.pop(fileno)

                        ip, port = conn.getpeername()
                        print('[RESOLVER] Disconnected: ', ip, ':', port, sep='')
        finally:
            poll.unregister(self.sock.fileno())
            poll.close()
            self.sock.close()


if __name__ == '__main__':
    resolver = Resolver()
    resolver.run_blocking_handler()
