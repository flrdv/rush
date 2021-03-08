from socket import socket
from threading import Thread
from time import time, sleep

from lib import epollserver
from lib import periodic_events
from lib.msgproto import sendmsg, recvmsg
from servers.resolver.resolver_api import ResolverApi


HEARTBEAT = b'\x69'
REQUEST = b'\x96'


class Cluster:
    def __init__(self, name='cluster', addr=('localhost', 0),
                 disconnect_endpoints_if_not_responding=True,
                 endpoint_heartbeat_packets_timeout=1, mainserver_heartbeat_packets_timeout=.5,
                 resolver_addr=('localhost', 11100), main_server_name='mainserver'):
        self.name = name
        self.disconnect_endpoints_if_not_responding = disconnect_endpoints_if_not_responding
        self.endpoint_heartbeat_packets_timeout = endpoint_heartbeat_packets_timeout
        self.mainserver_heartbeat_packets_timeout = mainserver_heartbeat_packets_timeout
        self.resolver_addr = resolver_addr
        self.mainserver_name = main_server_name

        self.endpoint_connections = {}   # conn: [addr, cpu_load, last_heartbeat_packet_received_at]
        self.mainserver_conn = socket()  # we'll connect later, in start() method
        self.endpoints_epollserver = epollserver.EpollServer(addr=addr)

        self._started = False

    def endpoints_connection_handler(self, _, conn):
        ip, port = conn.getpeername()
        self.endpoint_connections[conn] = [(ip, port), 100, time()]

        print(f'[CLUSTER] New connection from {ip}:{port}')

    def endpoints_requests_handler(self, _, conn):
        """
        Endpoint's machine load update is our heartbeat packet
        Endpoints sends to cluster single byte that is converting
        to integer and means endpoint's machine load
        """

        ip, port = conn.getpeername()
        raw_load = conn.recv(1)
        load = int.from_bytes(raw_load, 'little')
        current_time = time()
        self.endpoint_connections[conn][1:3] = [load, current_time]
        print(f'[CLUSTER] [{current_time}] {ip}:{port}: {load}%')

    def mainserver_requests_handler(self):
        """
        Thread-based function
        """

        if not self.mainserver_conn:
            # TODO: how to check whether sock object is connected to smth?
            ...

        while True:
            request_type = self.mainserver_conn.recv(1)

            if request_type == HEARTBEAT:
                # this is heartbeat packet
                # and we response with the same byte
                self.mainserver_conn.send(request_type)
            elif request_type == REQUEST:
                # and this byte means that next bytes will be a request packet
                # and now we should receive it using lib.msgproto
                request = recvmsg(self.mainserver_conn)
                self.send_update(request)

    def endpoints_heartbeat_manager(self):
        """
        Periodic-event based function

        Using it to disconnect all the endpoints for the which
        ones we haven't received heartbeat packets for
        self.heartbeat_packets_timeout seconds
        """

        current_time = time()

        for conn, (_, _, last_heartbeat_packet_received_at) in self.endpoint_connections.items():
            if current_time - last_heartbeat_packet_received_at > self.endpoint_heartbeat_packets_timeout:
                ip, port = conn.getpeername()
                print(f'[CLUSTER] Endpoint {ip}:{port} does not responding (haven\'t '
                      'received heartbeat-packets for more than '
                      f'{self.endpoint_heartbeat_packets_timeout} seconds)')

                if self.disconnect_endpoints_if_not_responding:
                    self.disconnect_endpoint(conn)

    def disconnect_endpoint(self, conn):
        self.endpoint_connections.pop(conn)
        conn.close()

    def send_update(self, request):
        endpoint_with_minimal_load = min(self.endpoint_connections,
                                         key=lambda key: self.endpoint_connections[key][1])
        endpoint_with_minimal_load.send(REQUEST)
        sendmsg(endpoint_with_minimal_load, request)

    def start(self):
        print('[CLUSTER] Getting main server address...')

        resolver_api = ResolverApi(self.resolver_addr)

        ip, port = resolver_api.get_main_server(self.mainserver_name)
        print(f'[CLUSTER] Main server address: {ip}:{port}')

        self.mainserver_conn.connect((ip, port))
        print('[CLUSTER] Connected to the main server')

        periodic_events_executor = periodic_events.PeriodicEventsExecutor()
        periodic_events_executor.add_event(self.endpoint_heartbeat_packets_timeout,
                                           self.endpoints_heartbeat_manager)
        print('[CLUSTER] Added periodic event: endpoints heartbeat manager '
              f'(timeout: {self.endpoint_heartbeat_packets_timeout})')

        mainserver_requests_handler_thread = Thread(target=self.mainserver_requests_handler)
        mainserver_requests_handler_thread.start()
        print('[CLUSTER] Started main server requests handler thread '
              f'({mainserver_requests_handler_thread.ident})')

        self.endpoints_epollserver.start(threaded=True)
        print('[CLUSTER] Started server for endpoints')

        print('[CLUSTER] Telling resolver cluster\'s address...')
        resolver_api.add_cluster(self.name, self.endpoints_epollserver.addr)
        print('[CLUSTER] Done')

        resolver_api.stop()
