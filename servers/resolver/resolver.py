import sqlite3
from json import loads, dumps

import lib.epollserver
from lib.msgproto import recvmsg, sendmsg


REGISTRY_DB = 'servers/resolver/registry.sqlite3'
WRITE_DATA = 0
READ_DATA = 1
CLUSTER = 0
MAINSERVER = 1
RESPONSE_SUCC = 2
RESPONSE_FAIL = 3


"""
requesting resolver be like:
    1 byte - type of request (write/read data)
    1 byte - write/read data for which node (cluster/mainserver)
    * bytes - data
"""


SESSIONS = {}   # conn: (ip, addr). Using cause closed conn-obj does not contains addr of endpoint


def init_registry():
    queries = (
        'CREATE TABLE IF NOT EXISTS clusters (name string, ip string, port integer)',
        'CREATE TABLE IF NOT EXISTS mainservers (name string, ip string, port integer)'
    )

    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()

        for query in queries:
            cursor.execute(query)
            conn.commit()


def add_cluster_addr(cluster_name, ip, port):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO clusters VALUES (?, ?, ?)', (cluster_name, ip, port))
        conn.commit()


def get_cluster_addr(cluster_name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM clusters WHERE name=?', (cluster_name,))

        return cursor.fetchone() or (None, None)


def add_mainserver_addr(mainserver_pseudo, ip, port):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO mainservers VALUES (?, ?, ?)', (mainserver_pseudo, ip, port))
        conn.commit()


def get_mainserver_addr(mainserver_pseudo):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM mainservers WHERE name=?', (mainserver_pseudo,))

        return cursor.fetchone() or (None, None)


def response(code: int, text: bytes):
    return code.to_bytes(1, 'little') + text


def conn_handler(_, server_socket):
    conn, addr = server_socket.accept()
    ip, port = addr
    SESSIONS[conn] = (ip, port)
    print(f'[RESOLVER] Connected: {ip}:{port}')

    return conn


def request_handler(_, conn):
    packet = recvmsg(conn)
    ip, port = conn.getpeername()

    if len(packet) < 3:
        print(f'[RESOLVER] Received too short packet from {ip}:{port}: {packet}')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request'))

    request_type, request_to = packet[:2]
    body = packet[2:]

    if request_type == WRITE_DATA:
        name, ip, port = loads(body)

        if request_to == CLUSTER:
            add_cluster_addr(name, ip, port)
            print(f'[RESOLVER] Added cluster "{name}" with address {ip}:{port}')
        elif request_to == MAINSERVER:
            add_mainserver_addr(name, ip, port)
            print(f'[RESOLVER] Added main server "{name}" with address {ip}:{port}')
    elif request_type == READ_DATA:
        if request_to == CLUSTER:
            print(f'[RESOLVER] Getting address for cluster "{body}"...', end=' ')
            method = get_cluster_addr
        elif request_to == MAINSERVER:
            print(f'[RESOLVER] Getting address for main server "{body}"...', end=' ')
            method = get_mainserver_addr
        else:
            print(f'[RESOLVER] Received unknown REQUEST_TO code from {ip}:{port}: {request_type}')
            return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-to'))

        ip, port = method(body.decode())

        if ip is None:
            print('fail (not found)')
            return sendmsg(conn, response(RESPONSE_FAIL, b'not-found'))

        print(f'ok ({ip}:{port})')

        encoded_json = dumps([ip, port]).encode()
        sendmsg(conn, response(RESPONSE_SUCC, encoded_json))


def disconnect_handler(_, conn):
    ip, port = SESSIONS[conn]
    print(f'[RESOLVER] Disconnected: {ip}:{port}')


class Resolver:
    def __init__(self, addr=('localhost', 11100), maxconns=0):
        self.epoll_server = lib.epollserver.EpollServer(addr, maxconns=maxconns)
        self.epoll_server.add_handler(conn_handler, lib.epollserver.CONNECT)
        self.epoll_server.add_handler(request_handler, lib.epollserver.RECEIVE)
        self.epoll_server.add_handler(disconnect_handler, lib.epollserver.DISCONNECT)

    def start(self, threaded=False):
        self.epoll_server.start(threaded=threaded)


init_registry()
