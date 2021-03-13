import sqlite3
from datetime import datetime
from json import loads, JSONDecodeError

import lib.epollserver
from lib.msgproto import recvmsg


LOGDB = 'servers/logserver/logs.sqlite3'


def init_log_db():
    with sqlite3.connect(LOGDB) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS journal (id INTEGER NOT NULL PRIMARY KEY,'
                       'datetime FLOAT, log_type VARCHAR(30), log_entry TEXT)')
        conn.commit()


def add_log_entry(log_datetime, log_type, log_entry):
    with sqlite3.connect(LOGDB) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO journal VALUES (?, ?, ?)',
                       (log_datetime, log_type, log_entry))
        conn.commit()


def request_handler(_, conn):
    ip, port = conn.getpeername()
    log_entry = recvmsg(conn).decode()

    try:
        # log_datetime: unix-time
        log_datetime, log_type, log_text = loads(log_entry)

        assert isinstance(log_datetime, (int, float)) and\
               isinstance(log_type, str) and len(log_type) <= 30
    except (JSONDecodeError, ValueError):
        # this catches not only corrupted json, but also if it
        # contains less or more than 3 variables
        print(f'[LOGSERVER] Received corrupted json from {ip}:{port}: {log_entry}')
        return
    except AssertionError:
        print(f'[LOGSERVER] Received bad log-entry from {ip}:{port} ({", ".join(log_entry)})'
              ' (some types are mismatching)')
        return

    # long line as fuck
    human_readable_log_datetime = datetime.utcfromtimestamp(log_datetime).strftime('%Y-%m-%d %H:%M:%S.%f')[:3]

    print(f'[LOGSERVER-NEW-ENTRY] [{human_readable_log_datetime}] [{log_type}] {log_text}')

    add_log_entry(log_datetime, log_type, log_text)


class LogServer:
    def __init__(self, name='logserver', **kwargs):
        self.epoll_server = lib.epollserver.EpollServer(**kwargs)

        self.new_conn_handler = lib.epollserver.handshake(name)(self.new_conn_handler)

        self.epoll_server.add_handler(self.new_conn_handler, lib.epollserver.CONNECT)
        self.epoll_server.add_handler(request_handler, lib.epollserver.RECEIVE)
        self.epoll_server.add_handler(self.disconnect_handler, lib.epollserver.DISCONNECT)

        self.sessions = {}  # conn: addr

    def new_conn_handler(self, _, new_conn):
        ip, port = new_conn.getpeername()
        self.sessions[new_conn] = (ip, port)
        print(f'[LOGSERVER] New connection: {ip}:{port}')

    def disconnect_handler(self, _, conn):
        ip, port = self.sessions.pop(conn)
        print(f'[LOGSERVER] Disconnected: {ip}:{port}')
        conn.close()

    def start(self, threaded=False):
        self.epoll_server.start(threaded=threaded)


init_log_db()
