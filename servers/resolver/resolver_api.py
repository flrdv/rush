import socket
from json import loads, dumps

from lib.msgproto import sendmsg, recvmsg


WRITE = b'\x00'
READ = b'\x01'
DELETE = b'\x02'
ADD_STATE = b'\x03'
SUCC = 2    # after receiving bytes automatically being
FAIL = 3    # converted to integer
STATE_DONE = 4


class ResolverApi:
    def __init__(self, addr=('localhost', 11100)):
        self.addr = addr
        self.sock = socket.socket()

    def connect(self):
        self.sock.connect(self.addr)

        return 'connected'

    def request(self, request_type: bytes, data: bytes,
                wait_response: bool = True, jsonify_resposne: bool = True):
        sendmsg(self.sock, request_type + data)

        if wait_response:
            response = recvmsg(self.sock)
            response_code = response[0]
            response_body = response[1:]

            if response_code == SUCC and jsonify_resposne:
                response_body = loads(response_body.decode())

            return response_code, response_body

    def add_server(self, typeof, name, addr):
        self.request(WRITE, dumps([typeof, name, addr[0], addr[1]]).encode(),
                     wait_response=False)

    def get_server(self, typeof, name):
        return self.request(READ, (typeof + ':' + name).encode())

    def delete_server(self, typeof, name):
        self.request(DELETE, (typeof + ':' + name).encode(),
                     wait_response=False)

    def get_cluster(self, name):
        code, response = self.get_server('cluster', name)

        if code == FAIL:
            raise ClusterNotFoundError(f'{name}: {response.decode()}')

        return response

    def add_cluster(self, name, addr):
        self.add_server('cluster', name, addr)

    def delete_cluster(self, name):
        self.delete_server('cluster', name)

    def get_main_server(self, name):
        code, response = self.get_server('mainserver', name)

        if code == FAIL:
            raise MainServerNotFoundError(f'{name}: {response.decode()}')

        return response

    def add_main_server(self, name, addr):
        self.add_server('mainserver', name, addr)

    def delete_main_server(self, name):
        self.delete_server('mainserver', name)

    def get_log_server(self, name):
        return self.get_server('logserver', name)

    def add_log_server(self, name, addr):
        self.add_server('logserver', name, addr)

    def delete_log_server(self, name):
        self.delete_server('logserver', name)

    def stop(self):
        self.sock.close()

    def __del__(self):
        self.stop()


class ApiError(Exception): pass


class ClusterNotFoundError(ApiError): pass


class MainServerNotFoundError(ApiError): pass
