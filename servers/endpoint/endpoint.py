from sys import exit
from time import sleep, time
from socket import socket, timeout
from json import loads, JSONDecodeError

try:
    import psutil
except ImportError:
    print('[ENDPOINT] Error: psutil isn\'t installed. Try `pip install psutil` '
          'and run endpoint again')
    exit(1)

from lib.msgproto import sendmsg, recvmsg
from servers.resolver.resolver_api import ResolverApi
from lib.periodic_events import PeriodicEventsExecutor

HEARTBEAT = b'\x69'
REQUEST = b'\x96'

"""
class Endpoint:
    managing heartbeat packets, implements all the logic and methods
    for communication with cluster
    
class Handler:
    user class, using as a decorator for callable object that handles
    update. Inherited of Endpoint class

class Api:
    just a class that is connecting to a mainserver and sends responses
    to it
"""


class Endpoint:
    def __init__(self, cluster_name, heartbeat_packets_timeout=.5,
                 max_heartbeat_timeout=1, disconnect_after_heartbeat_timeout=True):
        self.cluster_name = cluster_name
        self.heartbeat_packets_timeout = .5
        self.heartbeat_packets_timeout = heartbeat_packets_timeout
        self.max_heartbeat_timeout = max_heartbeat_timeout
        self.disconnect_after_heartbeat_timeout = disconnect_after_heartbeat_timeout

        self.cluster_conn = socket()
        self.callback_on_update = lambda update: ...

        self._running = False

    def cluster_requests_manager(self):
        """
        Thread-based function, that receives heartbeat byte from
        cluster
        """
        self.cluster_conn.settimeout(self.max_heartbeat_timeout)

        try:
            while self._running:
                typeofpacket = self.cluster_conn.recv(1)

                if typeofpacket == HEARTBEAT:
                    self.cluster_conn.send(typeofpacket)
                elif typeofpacket == REQUEST:
                    request = recvmsg(self.cluster_conn)
        except timeout:
            print(f'[ENDPOINT] Cluster "{self.cluster_name}" does not '
                  f'responding for {self.max_heartbeat_timeout} seconds')

        if self.disconnect_after_heartbeat_timeout:
            print('[ENDPOINT] Disconnecting from cluster')
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

        print(f'[ENDPOINT] Emergency mode. Waiting for cluster "{self.cluster_name}"')

        with ResolverApi() as resolver_api:
            ip, port = resolver_api.wait_for_cluster(self.cluster_name)
            print(f'[ENDPOINT] Cluster "{self.cluster_name}" is online. Connecting to {ip}:{port}')
            self.start(cluster_addr=(ip, port))

    def set_callback_on_update(self, callback):
        self.callback_on_update = callback

    def start(self, cluster_addr=None):
        """
        :param cluster_addr: tuple or None. If None, address will be
        taken from resolver
        :return:
        """
        ...

    def stop(self):
        self._running = False
        self.cluster_conn.close()
