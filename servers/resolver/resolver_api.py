import socket
from json import loads, dumps

from lib.msgproto import sendmsg, recvmsg


WRITE = b'\x00'
READ = b'\x01'
DELETE = b'\x02'
CLUSTER = b'\x00'
MAINSERVER = b'\x01'
SUCC = 2    # after receiving bytes automatically being
FAIL = 3    # converted to integer


class ResolverApi:
    def __init__(self, addr=('localhost', 11100)):
        self.addr = addr
        self.sock = socket.socket()

    def connect(self):
        self.sock.connect(self.addr)

        return 'connected'

    def request(self, request_type, request_to, data,
                wait_response=True, jsonify_resposne=True):
        sendmsg(self.sock, request_type + request_to + data)

        if wait_response:
            response = recvmsg(self.sock)
            response_code = response[0]
            response_body = response[1:]

            if response_code == SUCC and jsonify_resposne:
                response_body = loads(response_body.decode())

            return response_code, response_body

    def get_cluster(self, name):
        code, response = self.request(READ, CLUSTER, name.encode())

        if code == FAIL:
            raise ClusterNotFoundError(f'{name}: {response.decode()}')

        return response

    def add_cluster(self, name, addr):
        request_body = dumps([name, addr[0], addr[1]])
        self.request(WRITE, CLUSTER, request_body.encode(), wait_response=False)

    def get_main_server(self, name):
        code, response = self.request(READ, MAINSERVER, name.encode())

        if code == FAIL:
            raise MainServerNotFoundError(f'{name}: {response.decode()}')

        return response

    def add_main_server(self, name, addr):
        request_body = dumps([name, addr[0], addr[1]])
        self.request(WRITE, MAINSERVER, request_body.encode())

    def delete_cluster(self, name):
        self.request(DELETE, CLUSTER, name.encode(), wait_response=False)

    def delete_main_server(self, name):
        self.request(DELETE, MAINSERVER, name.encode, wait_response=False)

    def stop(self):
        self.sock.close()

    def __del__(self):
        self.stop()


class ApiError(Exception): ...


class ClusterNotFoundError(ApiError): ...


class MainServerNotFoundError(ApiError): ...
