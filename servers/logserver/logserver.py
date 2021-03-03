import sqlite3
from datetime import datetime
from json import loads, JSONDecodeError

import lib.epollserver
from lib.msgproto import recvmsg


LOGDB = 'server/logserver/logs.sqlite3'
SESSIONS = {}   # conn: (ip, port)


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


def new_conn_handler(_, server_sock):
    conn, (ip, port) = server_sock.accept()
    SESSIONS[conn] = (ip, port)
    print(f'[LOGSERVER] New connection: {ip}:{port}')

    return conn


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


def disconnect_handler(_, conn):
    ip, port = SESSIONS.pop(conn)
    print(f'[LOGSERVER] Disconnected: {ip}:{port}')
    conn.close()


class LogServer:
    def __init__(self, **kwargs):
        self.epoll_server = lib.epollserver.EpollServer(**kwargs)
        self.epoll_server.add_handler(new_conn_handler, lib.epollserver.CONNECT)
        self.epoll_server.add_handler(request_handler, lib.epollserver.RECEIVE)
        self.epoll_server.add_handler(disconnect_handler, lib.epollserver.DISCONNECT)

    def start(self, threaded=False):
        self.epoll_server.start(threaded=threaded)


init_log_db()
