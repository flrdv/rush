from lib import epollserver
from mainserver.core import CoreServer
from lib.msgproto import sendmsg, recvmsg


def stringify_addr(addr):
    return addr[0] + ':' + str(addr[1])


NAME = 'sockets-demo'


class SimpleSocketServer:
    def __init__(self):
        self.clients_ids = {}   # ip:port: conn
        self.clients = {}

        self.epollserver = epollserver.EpollServer(('0.0.0.0', 9090))
        self.epollserver.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epollserver.add_handler(self.disconn_handler, epollserver.DISCONNECT)
        self.epollserver.add_handler(self.requests_handler, epollserver.RECEIVE)

        self.server_core = CoreServer(self.response, addr=('0.0.0.0', 10000),
                                      name=NAME)

    def response(self, response_to, response_body):
        conn = self.clients_ids[response_to.decode()]
        sendmsg(conn, response_body)

    def conn_handler(self, _, conn):
        ip = stringify_addr(conn.getpeername())
        print('New connection:', ip)
        self.clients_ids[ip] = conn
        self.clients[conn] = ip

    def disconn_handler(self, _, conn):
        ip = self.clients.pop(conn)
        self.clients_ids.pop(ip)
        print('Disconnected:', ip)

    def requests_handler(self, _, conn):
        msg = recvmsg(conn)
        ip = stringify_addr(conn.getpeername())
        print('New request from', ip, ':', msg)
        self.server_core.send_update(ip, msg, {'body': msg.decode()})

    def start(self):
        self.epollserver.start(threaded=True)
        self.server_core.start()


if __name__ == '__main__':
    server = SimpleSocketServer()
    server.start()
