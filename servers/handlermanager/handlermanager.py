from sys import exit
from threading import Thread
from socket import socket, timeout
from json import loads, dumps, JSONDecodeError

try:
    import psutil
except ImportError:
    print('[HANDLER] Error: psutil isn\'t installed. Try `pip install psutil` '
          'and run handler again')
    exit(1)

from lib import epollserver
from lib.msgproto import sendmsg, recvmsg
from servers.resolver.resolver_api import ResolverApi
from lib.periodic_events import PeriodicEventsExecutor

HEARTBEAT = b'\x69'
REQUEST = b'\x96'

""" 
class Handler:
    user class, using as a decorator for callable object that handles
    update. Also implements protocol and handles cluster connection

class Api:
    just a class that is connecting to a mainserver and sends responses
    to it
"""


class Packet:
    def __init__(self, **kwargs):
        self.values = kwargs

    def set(self, **kwargs):
        self.values = {**self.values, **kwargs}

    def get(self, value):
        return self.values[value]

    def copy(self):
        return Packet(**self.values)

    def get_attrs(self):
        return self.values

    def __setattr__(self, key, value):
        self.values[key] = value

    __setitem__ = __setattr__

    def __getattr__(self, item):
        return self.values[item]

    def __getitem__(self, item):
        return object.__getattribute__(self, item)[item]

    def __delattr__(self, item):
        del self.values[item]

    __delitem__ = __delattr__

    def __str__(self):
        return str(self.values)

    __repr__ = __str__


class Handler:
    def __init__(self, cluster_name, heartbeat_packets_timeout=.5,
                 max_heartbeat_timeout=1, disconnect_after_heartbeat_timeout=True):
        self.cluster_name = cluster_name
        self.heartbeat_packets_timeout = heartbeat_packets_timeout
        self.max_heartbeat_timeout = max_heartbeat_timeout
        self.disconnect_after_heartbeat_timeout = disconnect_after_heartbeat_timeout

        self.cluster_conn = socket()
        self.handler = None

        self._running = False

    def cluster_requests_manager(self):
        """
        Thread-based function, that handles cluster requests & heartbeat
        packets
        """
        self.cluster_conn.settimeout(self.max_heartbeat_timeout)

        try:
            while self._running:
                typeofpacket = self.cluster_conn.recv(1)

                if typeofpacket == HEARTBEAT:
                    self.cluster_conn.send(typeofpacket)
                elif typeofpacket == REQUEST:
                    request = recvmsg(self.cluster_conn)

                    try:
                        processed_request = loads(request)
                    except (ValueError, JSONDecodeError):
                        print('[HANDLER] Received corrupted request from cluster')
                        continue

                    self.send_request(Packet(**processed_request))
        except timeout:
            print(f'[HANDLER] Cluster "{self.cluster_name}" does not '
                  f'responding for {self.max_heartbeat_timeout} seconds')

        if self.disconnect_after_heartbeat_timeout:
            print('[HANDLER] Disconnecting from cluster')
            self.stop()

    def send_heartbeat_packet(self):
        cpu_load: int = round(psutil.cpu_percent())
        self.cluster_conn.send(cpu_load.to_bytes(1, 'little'))

    def wait_for_cluster(self):
        """
        Emergency mode if cluster has been disconnected for some reason
        If resolver is offline, ResolverApi class already implemented
        emergency system of waiting resolver to be online back on the
        same address. Quite convenient
        """

        print(f'[HANDLER] Emergency mode. Waiting for cluster "{self.cluster_name}"')

        with ResolverApi() as resolver_api:
            ip, port = resolver_api.wait_for_cluster(self.cluster_name)
            print(f'[HANDLER] Cluster "{self.cluster_name}" is online. Connecting to {ip}:{port}')
            self.start(cluster_addr=(ip, port))

    def send_request(self, request):
        if self.handler is None:
            print('[HANDLER] Received request, but it cannot be handled '
                  '(no handler function attached)')

            return

        self.handler(request)

    def handle(self, func):
        """
        This is a decorator for callable object

        The object has to receive 1 positional argument
        This argument is a json (or anything you want, depends on implementation)
        """

        self.handler = func

        return func

    def start(self, cluster_addr=None):
        """
        :param cluster_addr: tuple or None. If None, address will be
        taken from resolver
        :return:

        Initialization:
            1) run thread with cluster_requests_handler
            2) run periodic event send_heartbeat_packet
        """

        if cluster_addr is None:
            print('[HANDLER] Cluster address hasn\'t been providing, so requesting resolver for it')

            with ResolverApi() as resolver_api:
                cluster_addr = resolver_api.get_cluster(self.cluster_name)
                ip, port = cluster_addr

        print(f'[HANDLER] Connecting to cluster: {ip}:{port}')
        self.cluster_conn.connect(cluster_addr)

        if not epollserver.do_handshake(self.cluster_conn, self.cluster_name):
            print(f'[HANDLER] Failed to connect to cluster: handshake failure')

            return

        print('[HANDLER] Handshake with cluster succeeded')

        self._running = True
        cluster_requests_handler_thread = Thread(target=self.cluster_requests_manager)
        cluster_requests_handler_thread.start()
        print('[HANDLER] Started thread with cluster_requests_manager '
              f'({cluster_requests_handler_thread.ident})')

        periodic_events_executor = PeriodicEventsExecutor()
        periodic_events_executor.add_event(self.heartbeat_packets_timeout, self.send_heartbeat_packet)
        periodic_events_executor.start()
        print('[HANDLER] Started heartbeat manager')

    def stop(self):
        self._running = False
        self.cluster_conn.close()


class Api:
    def __init__(self, mainserver_name='mainserver', autoconnect=True):
        self.mainserver_name = mainserver_name
        self.sock = None

        if autoconnect:
            self.connect()

    def connect(self):
        self.sock = socket()

        with ResolverApi() as resolver_api:
            print('[MAINSERVER-API] Getting address of main server...')
            ip, port = resolver_api.get_main_server(self.mainserver_name)
            print(f'[MAINSERVER-API] Main server address: {ip}:{port}')

        self.sock.connect((ip, port))

        if not epollserver.do_handshake(self.sock, self.mainserver_name):
            print('[MAINSERVER-API] Connection failed: handshake failure')
            exit(1)

        print('[MAINSERVER-API] Handshake succeeded')

    def response(self, packet: Packet):
        """
        TODO: I need to implement Packet class, that will serialize
              JSON to python object. Handler also should return Packet
              object. All this is needed to let user abstract away
              from interacting with such a fields like response_to

        Looks like TODO is done
        """

        if self.sock is None:
            raise RuntimeError('not connected to mainserver')

        packet_attrs = packet.get_attrs()
        response_to = packet_attrs.pop('response-to')
        encoded_packet = dumps([response_to, packet_attrs]).encode()

        return sendmsg(self.sock, encoded_packet)

    def stop(self):
        if self.sock is not None:
            self.sock.close()

    def __del__(self):
        self.stop()
