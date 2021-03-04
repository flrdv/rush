import sqlite3
from json import loads, dumps, JSONDecodeError

import lib.epollserver
from lib.msgproto import recvmsg, sendmsg


REGISTRY_DB = 'servers/resolver/registry.sqlite3'
WRITE_DATA = 0
READ_DATA = 1
DELETE_DATA = 2
ADD_STATE = 3
CLUSTER = 0
MAINSERVER = 1
CUSTOM_SERVER = 2
RESPONSE_SUCC = 2
RESPONSE_FAIL = 3
STATE_DONE = 4


"""
requesting resolver be like:
    1 byte - type of request (write/read data)
    1 byte - write/read data for which node (cluster/mainserver)
    * bytes - data
"""


def init_registry():
    queries = (
        'CREATE TABLE IF NOT EXISTS servers '
        '(typeofserver string, name string, ip string, port integer)',
    )

    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()

        for query in queries:
            cursor.execute(query)
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


def add_custom_server(typeofserver, name, addr):
    ip, port = addr

    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO servers VALUES (?, ?, ?, ?)',
                       (typeofserver, name, ip, port))
        conn.commit()


def get_custom_server(typeofserver, name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM servers WHERE typeofserver=? AND name=?',
                       (typeofserver, name))

        return cursor.fetchone() or (None, None)


def delete_custom_server(typeofserver, name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        query = 'DELETE FROM servers WHERE typeofserver=?'

        if name != '*':
            query += ' AND name=?'

        cursor.execute(query, (typeofserver, name))
        conn.commit()


def response(code: int, text: bytes):
    return code.to_bytes(1, 'little') + text


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
    elif request_to == CUSTOM_SERVER:
        typeofserver, name = parse_request_to_custom_server(name)

        add_custom_server(typeofserver, name, (ip, port))


def _handle_read_request(conn, request_to, name):
    client_ip, client_port = conn.getpeername()

    if request_to == CLUSTER:
        print(f'[RESOLVER] Getting address for cluster "{name}"...', end=' ')
        method = get_cluster_addr
    elif request_to == MAINSERVER:
        print(f'[RESOLVER] Getting address for main server "{name}"...', end=' ')
        method = get_mainserver_addr
    elif request_to == CUSTOM_SERVER:
        typeofserver, name = parse_request_to_custom_server(name)
        method = lambda nameofserver: get_custom_server(typeofserver, nameofserver)
    else:
        print('[RESOLVER] Received unknown REQUEST_TO code from '
              f'{client_ip}:{client_port} ({request_to})')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-to'))

    ip, port = method(name)

    if ip is None:
        print('fail (not found)')
        return sendmsg(conn, response(RESPONSE_FAIL, b'not-found'))

    print(f'ok ({ip}:{port})')

    encoded_json = dumps([ip, port]).encode()
    sendmsg(conn, response(RESPONSE_SUCC, encoded_json))


def _handle_delete_request(conn, request_to, name):
    ip, port = conn.getpeername()

    if request_to == CLUSTER:
        print(f'[RESOLVER] Deleting address of cluster "{name}"')
        method = delete_cluster_addr
    elif request_to == MAINSERVER:
        print(f'[RESOLVER] Deleting address of main server "{name}"...', end=' ')
        method = delete_mainserver_addr
    elif request_to == CUSTOM_SERVER:
        typeofserver, name = parse_request_to_custom_server(name)
        method = lambda nameofserver: delete_custom_server(typeofserver, nameofserver)
    else:
        print(f'[RESOLVER] Received unknown REQUEST_TO code from {ip}:{port} ({request_to})')
        return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-to'))

    method(name)


def handle_bad_request_type(conn, *args):
    sendmsg(conn, response(RESPONSE_FAIL, b'bad-request-type'))


def parse_request_to_custom_server(name):
    return map(lambda item: item.strip(), name.split(':', maxsplit=1))


class Resolver:
    def __init__(self, addr=('localhost', 11100), maxconns=0):
        self.epoll_server = lib.epollserver.EpollServer(addr, maxconns=maxconns)
        self.epoll_server.add_handler(self.conn_handler, lib.epollserver.CONNECT)
        self.epoll_server.add_handler(self.request_handler, lib.epollserver.RECEIVE)
        self.epoll_server.add_handler(self.disconnect_handler, lib.epollserver.DISCONNECT)

        # conn: (ip, addr). Using cause closed conn-obj does not contains addr of endpoint
        self.sessions = {}
        # type of server: {name of server: [*conn_objects]}
        self.states = {}

        self.requests_handlers_map = {
            WRITE_DATA: _handle_write_request,
            READ_DATA: _handle_read_request,
            DELETE_DATA: _handle_delete_request,
            ADD_STATE: self._handle_add_state,
        }

    def start(self, threaded=False):
        self.epoll_server.start(threaded=threaded)

    def conn_handler(self, _, new_conn):
        ip, port = new_conn.getpeername()
        self.sessions[new_conn] = (ip, port)
        print(f'[RESOLVER] Connected: {ip}:{port}')

    def request_handler(self, _, conn):
        packet = recvmsg(conn)
        ip, port = conn.getpeername()

        if len(packet) < 3:
            print(f'[RESOLVER] Received too short packet from {ip}:{port}: {packet}')
            return sendmsg(conn, response(RESPONSE_FAIL, b'bad-request'))

        request_type, request_to = packet[:2]
        body = packet[2:].decode()

        _request_handler = self.requests_handlers_map.get(request_type, handle_bad_request_type)
        _request_handler(conn, request_to, body)

    def disconnect_handler(self, _, conn):
        ip, port = self.sessions[conn]
        print(f'[RESOLVER] Disconnected: {ip}:{port}')

    def _handle_add_state(self, conn, request_to, name_of_server):
        if request_to not in self.states:
            self.states[request_to] = {}

        if name_of_server not in self.states[request_to]:
            self.states[request_to][name_of_server] = [conn]
        else:
            self.states[request_to][name_of_server].append(conn)

    def check_state(self, request_to, name, new_addr):
        if request_to not in self.states:
            return
        if name not in self.states[request_to]:
            return

        for conn in self.states[request_to][name]:
            sendmsg(conn, response(STATE_DONE, dumps(new_addr).encode()))

        self.states[request_to].pop(name)


init_registry()
