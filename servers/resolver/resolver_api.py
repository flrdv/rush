import socket
from time import sleep
from json import loads, dumps

from lib.epollserver import do_handshake
from lib.msgproto import sendmsg, recvmsg

WRITE = b'\x00'
READ = b'\x01'
DELETE = b'\x02'
ADD_STATE = b'\x03'
SUCC = 2  # after receiving bytes automatically being
FAIL = 3  # converted to integer
STATE_DONE = 4


class ResolverApi:
    def __init__(self, addr=('localhost', 11100), wait_for_resolver=True):
        """
        :param addr: address of resolver
        :param wait_for_resolver: if resolver is unavailable, wait until it will be available
                                  blocks function
        """
        self.addr = addr
        self.wait_for_resolver = wait_for_resolver
        self.sock = socket.socket()

        self._connected = False

    def connect(self):
        while True:
            try:
                self.sock.connect(self.addr)

                if not do_handshake(self.sock, 'resolver'):
                    print('[RESOLVER-API] Failed to connect to resolver: handshake failure')
                    self.sock.close()
                    self.sock = socket.socket()

                    return False

                break
            except (ConnectionResetError, ConnectionRefusedError) as exc:
                print('[RESOLVER-API] Failed to connect to the resolver:', exc)

                if not self.wait_for_resolver:
                    return False

            sleep(1)

        self._connected = True

        return True

    def request(self, request_type: bytes, data: bytes,
                wait_response: bool = True, jsonify_resposne: bool = True):
        if not self._connected:
            raise RuntimeError('not connected to resolver')

        sendmsg(self.sock, request_type + data)

        if wait_response:
            response = recvmsg(self.sock)
            response_code = response[0]
            response_body = response[1:]

            if response_code in (SUCC, STATE_DONE) and jsonify_resposne:
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

    def wait_for(self, typeof, name):
        code, response = self.request(ADD_STATE, (typeof + ':' + name).encode(),
                                      wait_response=True)

        if code != STATE_DONE:
            raise UnexpectedResponseError('got an unexpected response on state from '
                                          'resolver: ' + str(code))

        return response

    def wait_for_cluster(self, name):
        return self.wait_for('cluster', name)

    def wait_for_mainserver(self, name):
        self.wait_for('mainserver', name)

    def wait_for_logserver(self, name):
        self.wait_for('logserver', name)

    def __enter__(self):
        self.connect()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def stop(self):
        self.sock.close()
        self._connected = False

    def __del__(self):
        self.stop()


class ApiError(Exception): pass


class ClusterNotFoundError(ApiError): pass


class MainServerNotFoundError(ApiError): pass


class UnexpectedResponseError(ApiError): pass
