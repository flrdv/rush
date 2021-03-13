from socket import socket
from time import time, sleep
from threading import Thread
from json import load, JSONDecodeError

from lib import epollserver
from lib import periodic_events
from lib.msgproto import sendmsg, recvmsg
from servers.resolver.resolver_api import ResolverApi

HEARTBEAT = b'\x69'
REQUEST = b'\x96'


class Cluster:
    def __init__(self, profile=None, name='cluster', addr=('localhost', 0),
                 filter_=None, disconnect_handlers_if_not_responding=True,
                 handler_heartbeat_packets_timeout=1, mainserver_heartbeat_packets_timeout=.5,
                 resolver_addr=('localhost', 11100), main_server_name='mainserver'):
        self.profile = profile
        self.name = name
        self.filter = filter_ or {}
        self.disconnect_handlers_if_not_responding = disconnect_handlers_if_not_responding
        self.handler_heartbeat_packets_timeout = handler_heartbeat_packets_timeout
        self.mainserver_heartbeat_packets_timeout = mainserver_heartbeat_packets_timeout
        self.resolver_addr = resolver_addr
        self.mainserver_name = main_server_name

        self.handler_connections = {}  # conn: [addr, cpu_load, last_heartbeat_packet_received_at]
        self.mainserver_conn = socket()  # we'll connect later, in start() method
        self.handlers_epollserver = epollserver.EpollServer(addr=addr)

        self.handlers_connection_handler = epollserver.handshake(name) \
            (self.handlers_connection_handler)

        self.handlers_epollserver.add_handler(self.handlers_connection_handler,
                                              epollserver.CONNECT)
        self.handlers_epollserver.add_handler(self.handlers_requests_handler,
                                              epollserver.RECEIVE)
        self.handlers_epollserver.add_handler(self.handlers_disconnect_handler,
                                              epollserver.DISCONNECT)

        self._started = False

    def handlers_connection_handler(self, _, conn):
        ip, port = conn.getpeername()
        self.handler_connections[conn] = [(ip, port), 100, time()]

        print(f'[CLUSTER] New connection from {ip}:{port}')

    def handlers_requests_handler(self, _, conn):
        """
        handler's machine load update is our heartbeat packet
        handlers sends to cluster single byte that is converting
        to integer and means handler's machine load
        """

        ip, port = conn.getpeername()
        raw_load = conn.recv(1)
        cpu_load = int.from_bytes(raw_load, 'little')
        current_time = time()
        self.handler_connections[conn][1:3] = [cpu_load, current_time]
        print(f'[CLUSTER] [{current_time}] {ip}:{port}: {cpu_load}%')

    def handlers_disconnect_handler(self, _, conn):
        self.disconnect_handler(conn)

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

    def handlers_heartbeat_manager(self):
        """
        Periodic-event based function

        Using it to disconnect all the handlers for the which
        ones we haven't received heartbeat packets for
        self.heartbeat_packets_timeout seconds
        """

        current_time = time()

        for conn, (_, _, last_heartbeat_packet_received_at) in self.handler_connections.items():
            if current_time - last_heartbeat_packet_received_at > self.handler_heartbeat_packets_timeout:
                ip, port = conn.getpeername()
                print(f'[CLUSTER] handler {ip}:{port} does not responding (haven\'t '
                      'received heartbeat-packets for more than '
                      f'{self.handler_heartbeat_packets_timeout} seconds)')

                if self.disconnect_handlers_if_not_responding:
                    self.disconnect_handler(conn)

    def disconnect_handler(self, conn):
        ip, port = self.handler_connections[conn][0]

        self.handler_connections.pop(conn)
        conn.close()

        print(f'[CLUSTER] Disconnected handler: {ip}:{port}')

    def send_update(self, request):
        handler_with_minimal_load = min(self.handler_connections,
                                        key=lambda key: self.handler_connections[key][1])
        handler_with_minimal_load.send(REQUEST)
        sendmsg(handler_with_minimal_load, request)

    def load_profile(self):
        try:
            with open(self.profile) as fd:
                variables = load(fd)
        except (ValueError, JSONDecodeError, FileNotFoundError):
            print(f'[CLUSTER] Failed to load profile: {self.profile} (it doesn\'t '
                  'exists or corrupted)')

            return

        if not isinstance(variables, dict):
            return print(f'[CLUSTER] Failed to load profile: {self.profile} (bad configuration)')

        print(f'[CLUSTER] Applying profile: {self.profile}')
        for var, val in variables.items():
            print(f'[CLUSTER] Setting: {var}={repr(val)}')
            setattr(self, var, val)

    def start(self):
        if self.profile:
            self.load_profile()

        print('[CLUSTER] Getting main server address...')
        resolver_api = ResolverApi(self.resolver_addr)
        ip, port = resolver_api.get_main_server(self.mainserver_name)
        print(f'[CLUSTER] Main server address: {ip}:{port}')

        self.mainserver_conn.connect((ip, port))
        epollserver.do_handshake(self.mainserver_conn, self.mainserver_name)
        print('[CLUSTER] Connected to the main server')

        mainserver_requests_handler_thread = Thread(target=self.mainserver_requests_handler)
        mainserver_requests_handler_thread.start()
        print('[CLUSTER] Started main server requests handler thread '
              f'({mainserver_requests_handler_thread.ident})')

        periodic_events_executor = periodic_events.PeriodicEventsExecutor()
        periodic_events_executor.add_event(self.handler_heartbeat_packets_timeout,
                                           self.handlers_heartbeat_manager)
        periodic_events_executor.start()
        print('[CLUSTER] Added periodic event: handlers heartbeat manager '
              f'(timeout: {self.handler_heartbeat_packets_timeout})')

        self.handlers_epollserver.start(threaded=True)
        print('[CLUSTER] Started server for handlers')

        print('[CLUSTER] Telling resolver cluster\'s address...')
        resolver_api.add_cluster(self.name, self.handlers_epollserver.addr)
        print('[CLUSTER] Done')

        resolver_api.stop()
