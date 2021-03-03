import sqlite3
from json import loads, dumps, JSONDecodeError

import lib.epollserver
from lib.msgproto import recvmsg, sendmsg


REGISTRY_DB = 'servers/resolver/registry.sqlite3'
WRITE_DATA = 0
READ_DATA = 1
DELETE_DATA = 2
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
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS servers '
                       '(typeofserver string, name string, ip string, port integer)')
        conn.commit()


def add_cluster_addr(name, ip, port):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO servers VALUES ("cluster", ?, ?, ?)', (name, ip, port))
        conn.commit()


def get_cluster_addr(name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM servers WHERE name=? AND typeofserver="cluster"', (name,))

        return cursor.fetchone() or (None, None)


def delete_cluster_addr(name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()

        query = 'DELETE FROM servers WHERE typeofserver="cluster"'

        if name != '*':
            query += ' AND name=?'

        cursor.execute(query, (name,))
        conn.commit()


def add_mainserver_addr(name, ip, port):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO servers VALUES ("mainserver", ?, ?, ?)', (name, ip, port))
        conn.commit()


def get_mainserver_addr(name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM servers WHERE name=? AND typeofserver="mainserver"', (name,))

        return cursor.fetchone() or (None, None)


def delete_mainserver_addr(name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()

        query = 'DELETE FROM servers WHERE typeofserver="mainserver"'

        if name != '*':
            query += ' AND name=?'

        cursor.execute(query, (name,))
        conn.commit()


def response(code: int, text: bytes):
    return code.to_bytes(1, 'little') + text


def conn_handler(_, new_conn):
    ip, port = new_conn.getpeername()
    SESSIONS[new_conn] = (ip, port)
    print(f'[RESOLVER] Connected: {ip}:{port}')


def _handle_write_request(conn, request_to, body):
    client_ip, client_port = conn.getpeername()

    try:
        name, ip, port = loads(body)
    except (ValueError, JSONDecodeError):
        print(f'[RESOLVER] Received corrupted json body from {client_ip}:{client_port}: {body}')
        return sendmsg(conn, response(RESPONSE_FAIL, b'invalid-request-body'))

    if request_to == CLUSTER:
        add_cluster_addr(name, ip, port)
        print(f'[RESOLVER] Added cluster "{name}" with address {ip}:{port} '
              f'(by {client_ip}:{client_port})')
    elif request_to == MAINSERVER:
        add_mainserver_addr(name, ip, port)
        print(f'[RESOLVER] Added main server "{name}" with address {ip}:{port} '
              f'(by {client_ip}:{client_port})')


def _handle_read_request(conn, request_to, body):
    client_ip, client_port = conn.getpeername()

    if request_to == CLUSTER:
        print(f'[RESOLVER] Getting address for cluster "{body}"...', end=' ')
        method = get_cluster_addr
    elif request_to == MAINSERVER:
        print(f'[RESOLVER] Getting address for main server "{body}"...', end=' ')
        method = get_mainserver_addr
    else:
        print('[RESOLVER] Received unknown REQUEST_TO code from '
              f'{client_ip}:{client_port} ({request_to})')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-to'))

    ip, port = method(body)

    if ip is None:
        print('fail (not found)')
        return sendmsg(conn, response(RESPONSE_FAIL, b'not-found'))

    print(f'ok ({ip}:{port})')

    encoded_json = dumps([ip, port]).encode()
    sendmsg(conn, response(RESPONSE_SUCC, encoded_json))


def _handle_delete_request(conn, request_to, body):
    ip, port = conn.getpeername()

    if request_to == CLUSTER:
        print(f'[RESOLVER] Deleting address of cluster "{body}"')
        method = delete_cluster_addr
    elif request_to == MAINSERVER:
        print(f'[RESOLVER] Deleting address of main server "{body}"...', end=' ')
        method = get_mainserver_addr
    else:
        print(f'[RESOLVER] Received unknown REQUEST_TO code from {ip}:{port} ({request_to})')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-to'))

    method(body)


def handle_bad_request_type(conn, *args):
    sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-type'))


def request_handler(_, conn):
    packet = recvmsg(conn)
    ip, port = conn.getpeername()

    if len(packet) < 3:
        print(f'[RESOLVER] Received too short packet from {ip}:{port}: {packet}')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request'))

    request_type, request_to = packet[:2]
    body = packet[2:].decode()
    requests_handlers_map = {
        WRITE_DATA: _handle_write_request,
        READ_DATA: _handle_read_request,
        DELETE_DATA: _handle_delete_request,
    }

    _request_handler = requests_handlers_map.get(request_type, handle_bad_request_type)
    _request_handler(conn, request_to, body)


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
