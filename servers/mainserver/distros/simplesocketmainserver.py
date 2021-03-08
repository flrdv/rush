from json import loads
from traceback import format_exc

from lib import epollserver
from lib.msgproto import sendmsg, recvmsg
from servers.mainserver.core import nodesmanager


def _parse_request(raw):
    return loads(raw)


class SimpleSocketMainServer:
    def __init__(self):
        self.epollserver = epollserver.EpollServer(('localhost', 8080))
        self.connections = {}   # ip: conn
        self.mainserver_core = nodesmanager.NodesManager(callback=self.response_client)

        self.epollserver.add_handler(self.client_conn_handler, epollserver.CONNECT)
        self.epollserver.add_handler(self.client_request_handler, epollserver.RECEIVE)
        self.epollserver.add_handler(self.client_disconnect_handler, epollserver.DISCONNECT)
        self.epollserver.start()

    def response_client(self, response_to, response_body):
        conn = self.connections[response_to]
        sendmsg(conn, response_body)

    def client_conn_handler(self, _, conn):
        client_address = ':'.join(map(str, conn.getpeername()))
        self.connections[client_address] = conn

        print('[SimpleSocketMainServer] New connection from', client_address)

    def client_request_handler(self, _, conn):
        request = recvmsg(conn)
        self.mainserver_core.send_request(_parse_request(request))

    def client_disconnect_handler(self, _, conn):
        client_address = self._get_ip_by_conn_obj(conn)

        print('[SimpleSocketMainServer] Disconnected:', client_address)

    def _get_ip_by_conn_obj(self, conn_obj):
        for address, conn in self.connections.items():
            if conn == conn_obj:
                return address


if __name__ == '__main__':
    try:
        server = SimpleSocketMainServer()
    except Exception as exc:
        print('[SimpleSocketMainServer] An error occurred:', exc)
        print('Full traceback text:')
        print(format_exc())
