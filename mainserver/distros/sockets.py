from lib import epollserver
from mainserver.core import CoreServer
from lib.msgproto import sendmsg, recvmsg


def stringify_addr(addr):
    return addr[0] + str(addr[1])


class SimpleSocketServer:
    def __init__(self):
        self.clients = {}   # ip:port: conn

        self.epollserver = epollserver.EpollServer(('0.0.0.0', 9090))

        self.server_core = CoreServer(self.response, addr=('0.0.0.0', 10000))

    def response(self, response_to, response_body):
        conn = self.clients[response_to]
        sendmsg(conn, response_body)

    def conn_handler(self, _, conn):
        print('New connection:', stringify_addr(conn.getpeername()))

    def disconn_handler(self, _, conn):
        print('Disconnected:', stringify_addr(conn.getpeername()))

    def requests_handler(self, _, conn):
        msg = recvmsg(conn)
        ip = stringify_addr(conn.getpeername())
        print('New request from', ip, ':', msg)
        self.server_core.send_update([ip, msg])

    def start(self):
        self.server_core.start()


if __name__ == '__main__':
    server = SimpleSocketServer()
    server.start()
