import sqlite3
from json import loads, dumps, JSONDecodeError

import lib.epollserver
from lib.msgproto import recvmsg, sendmsg


REGISTRY_DB = 'servers/resolver/registry.sqlite3'
WRITE_DATA = 0
READ_DATA = 1
DELETE_DATA = 2
ADD_STATE = 3
RESPONSE_SUCC = 2
RESPONSE_FAIL = 3
STATE_DONE = 4


"""
requesting resolver be like:
    1 byte - type of request (write/read data)
    * bytes - data
    
    to specify name of server, you need to write it in format:
        type-of-server:name-of-server
    for example:
        cluster:upload-data
        mainserver:http-webserver
        logserver:my-project-logserver
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


def add_server(typeofserver, name, addr):
    ip, port = addr

    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO servers VALUES (?, ?, ?, ?)',
                       (typeofserver, name, ip, port))
        conn.commit()


def get_server(typeofserver, name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ip, port FROM servers WHERE typeofserver=? AND name=?',
                       (typeofserver, name))

        return cursor.fetchone() or (None, None)


def delete_server(typeofserver, name):
    with sqlite3.connect(REGISTRY_DB) as conn:
        cursor = conn.cursor()
        query = 'DELETE FROM servers WHERE typeofserver=?'

        if name != '*':
            query += ' AND name=?'

        cursor.execute(query, (typeofserver, name))
        conn.commit()


def response(code: int, text: bytes):
    return code.to_bytes(1, 'little') + text


def _handle_read_request(conn, name):
    typeofserver, name = parse_request_to_custom_server(name)

    print(f'[RESOLVER] Getting address for {typeofserver} "{name}"...', end=' ')

    ip, port = get_server(typeofserver, name)

    if ip is None:
        print('fail (not found)')

        return sendmsg(conn, response(RESPONSE_FAIL, b'not-found'))

    print(f'ok ({ip}:{port})')

    encoded_json = dumps([ip, port]).encode()
    sendmsg(conn, response(RESPONSE_SUCC, encoded_json))


def _handle_delete_request(conn, name):
    ip, port = conn.getpeername()
    typeofserver, name = parse_request_to_custom_server(name)

    print(f'[RESOLVER] Deleting {typeofserver} "{name}" (by {ip}:{port})')

    delete_server(typeofserver, name)


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
            WRITE_DATA: self._handle_write_request,
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

        request_type = packet[0]
        body = packet[1:].decode()

        _request_handler = self.requests_handlers_map.get(request_type, handle_bad_request_type)
        _request_handler(conn, body)

    def disconnect_handler(self, _, conn):
        ip, port = self.sessions[conn]

        print(f'[RESOLVER] Disconnected: {ip}:{port}')

    def _handle_write_request(self, conn, body):
        client_ip, client_port = conn.getpeername()

        try:
            typeofserver, name, ip, port = loads(body)
        except (ValueError, JSONDecodeError):
            print(f'[RESOLVER] Received corrupted json body from {client_ip}:{client_port}: {body}')
            return

        print(f'[RESOLVER] Added {typeofserver} "{name}" with address {ip}:{port} '
              f'(by {client_ip}:{client_port})')

        add_server(typeofserver, name, (ip, port))

        self.check_state(typeofserver, name, (ip, port))

    def _handle_add_state(self, conn, name_of_server):
        typeofserver, name = parse_request_to_custom_server(name_of_server)

        if typeofserver not in self.states:
            self.states[typeofserver] = {}

        if name not in self.states[typeofserver]:
            self.states[typeofserver][name] = [conn]
        else:
            self.states[typeofserver][name].append(conn)

    def check_state(self, typeofserver, name, new_addr):
        if typeofserver not in self.states:
            self.states[typeofserver] = {}
        if name not in self.states[typeofserver]:
            return

        for conn in self.states[typeofserver][name]:
            sendmsg(conn, response(STATE_DONE, dumps(new_addr).encode()))

        self.states[typeofserver].pop(name)


init_registry()
