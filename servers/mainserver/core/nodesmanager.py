import re
from threading import Thread
from time import time, sleep
from json import loads, dumps, JSONDecodeError

import lib.epollserver
import lib.periodic_events
from lib.msgproto import sendmsg, recvmsg
from servers.resolver.resolver_api import ResolverApi


ENDPOINT = 0
CLUSTER = 1
HEARTBEAT = b'\x69'
UPDATE = b'\x96'


def compare_filters(pattern: dict, source: dict):
    source_items = source.items()

    for key, value in pattern.items():
        for source_key, source_value in source_items:
            if re.fullmatch(key, source_key):
                if source_value is None or re.fullmatch(value, source_value):
                    break
        else:
            return False

    return True


class NodesManager:
    """
    Service for managing clusters
    Accept connections from clusters
    Initialization of cluster
    Handle updates distributions
    """

    def __init__(self, name='mainserver', callback=None, epollserver=None, addr=('localhost', 0),
                 heartbeat_packets_timeout=1, disconnect_unresponding_clusters=True,
                 resolver_addr=('localhost', 11100)):
        if epollserver is None:
            epollserver = lib.epollserver.EpollServer(addr=addr)

        self.name = name
        self.callback = callback
        self.epollserver = epollserver
        self.heartbeat_packets_timeout = heartbeat_packets_timeout
        self.disconnect_unresponding_clusters = disconnect_unresponding_clusters
        self.resolver_addr = resolver_addr

        self.clusters = {}   # conn: name, filter, last_heartbeat_packet_received_at
        self.endpoints = []  # contains conn objects to endpoints

        self._active = True

        epollserver.add_handler(self.conns_handler, lib.epollserver.CONNECT)
        epollserver.add_handler(self.request_handler, lib.epollserver.RECEIVE)

    def conns_handler(self, _, conn):
        """
        after handshake, we receive 1 byte from node to get know
        who is he:
            b'\x00' - endpoint
            b'\x01' - cluster

        if it's endpoint, we don't care and pass it.
        if it's cluster, we receive one more packet from client
        this packet is a json, like:
         <2 bytes: length of the name of cluster in bytes><name of cluster><filter>
        """
        ip, port = conn.getpeername()
        type_of_connected_guy = conn.recv(1)

        if type_of_connected_guy == ENDPOINT:
            print(f'[MAINSERVER] Endpoint connected: {ip}:{port}')
            self.endpoints.append(conn)
        elif type_of_connected_guy == CLUSTER:
            print(f'[MAINSERVER] Cluster connected: {ip}:{port}')

            if not self.manage_cluster_info(conn):
                return lib.epollserver.DENY_CONN
        else:
            print(f'[MAINSERVER] Received unknown identifier from {ip}:{port}: {bytes([type_of_connected_guy])}')
            conn.close()

            return lib.epollserver.DENY_CONN

    def manage_cluster_info(self, conn):
        """
        it receives json packet in format ["cluster name", "json-filter"]
        if error occurred, client receives packet:
            b'\x00<reason>'
        otherwise, client will receive just b'\x01' byte

        Heartbeat protocol & updates delivering:
            heartbeat packet is a single byte b'\x69'
            it requires any response with any length (but also single byte
            expected to avoid multiple RECEIVE events)

            when updates delivering, firstly client receives single byte b'\x96'
            after that, he receives full packet using lib.msgproto
        """

        raw = recvmsg(conn)

        if raw == b'':
            print(f'[MAINSERVER] Connection failure: disconnected while receiving initial packet')

            return

        ip, port = conn.getpeername()

        try:
            jsonified = loads(raw)
            assert len(jsonified) == 2 and all(isinstance(item, str) for item in jsonified)
        except (JSONDecodeError, ValueError, AssertionError):
            print(f'[MAINSERVER] Received bad cluster info json packet from {ip}:{port}: {raw}')
            sendmsg(conn, b'\x00invalid-init-data')
            conn.close()

            return False

        sendmsg(conn, b'\x01')

        name, requests_filter = jsonified
        requests_filter = loads(requests_filter)
        self.clusters[conn] = [name, requests_filter, time()]

        return True

    def request_handler(self, _, conn):
        ip, port = conn.getpeername()

        if conn in self.endpoints:
            # response from endpoint
            response: list = loads(recvmsg(conn))

            if len(response) != 2:
                return print('[MAINSERVER] Received bad packet from endpoint: '
                             f'{ip}:{port} as a response to {response[0]}')

            response_to, response_body = response

            print(f'[MAINSERVER] Received response for {response_to} from endpoint {ip}:{port}')

            if self.callback is None:
                return print(f'[MAINSERVER] Unable to response client: no callback function specified')

            self.callback(response_to, response_body)
        else:   # heartbeat-packet from cluster
            self.clusters[conn][2] = time()  # update cluster_last_heartbeat_received_at
            conn.send(HEARTBEAT)             # response with a heartbeat packet

    def send_request(self, request):
        for conn, (name, filter_, _) in self.clusters.items():
            if compare_filters(filter_, request):
                conn.send(UPDATE)
                sendmsg(conn, dumps(request).encode())

                return True

        return False

    def heartbeat_manager(self):
        """
        Thread-based function
        """

        while self._active:
            sleep(self.heartbeat_packets_timeout)
            current_time = time()

            for conn, (name, filter_, last_heartbeat_packet_received_at) in self.clusters.items():
                if current_time - last_heartbeat_packet_received_at > self.heartbeat_packets_timeout:
                    ip, port = conn.getpeername()
                    print(f'[MAINSERVER] Cluster {ip}:{port} does not responding (haven\'t'
                          ' received heartbeat-packets for more than'
                          f' {self.heartbeat_packets_timeout} seconds)')

                    if self.disconnect_unresponding_clusters:
                        self.disconnect_cluster(conn)

    def disconnect_cluster(self, conn):
        conn.close()
        self.clusters.pop(conn)

    def start(self, threaded=True):
        heartbeat_manager_thread = Thread(target=self.heartbeat_manager)
        heartbeat_manager_thread.start()
        print(f'[MAINSERVER] Started heartbeat manager thread ({heartbeat_manager_thread.ident})')

        with ResolverApi(self.resolver_addr) as resolver_api:
            resolver_api.add_main_server(self.name, self.epollserver.addr)

            ip, port = self.epollserver.addr
            print(f'[MAINSERVER] Registered in resolver as "{self.name}" on address {ip}:{port}')

        print('[MAINSERVER] Starting epoll server')
        self.epollserver.start(threaded=threaded)

    def stop(self):
        self._active = False
        self.epollserver.stop()

    def __del__(self):
        self.stop()
