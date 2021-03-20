from socket import socket
from threading import Thread
from json import loads, dumps
from psutil import cpu_percent

from lib.msgproto import sendmsg, recvmsg
from handler.entities import Filter, HandshakeManager
from lib.periodic_events import PeriodicEventsExecutor

RESPONSE = b'\x00'
HEARTBEAT = b'\x01'

HEARTBEAT_PERIODICITY = .5  # seconds between heartbeat packets


"""
Handler - class that is used for decorating and running handler clients.
Client - class that implements mainserver communication & handler functions
         calls
         
you should initialize somewhere a Handler object for decorating your functions
after that. Example:

```
handler = Handler()


@handler()  # empty filter means that this handler will catch all requests
def handle(client: Client, msg: dict):
    client.response('you said: ' + msg.decode())
    
    
handler.start()
```
"""


class Handler:
    def __init__(self, addr=('localhost', 10000)):
        self.addr = addr
        self.sock = socket()
        self.clients = []

    def __call__(self, filter_=None, **fields):
        """
        Decorator for a handler function. It can receive Filter entity
        (mainserever.entities), or just dict as kwargs
        """

        if filter_ is None:
            filter_ = Filter(fields)

        def wrapper(func):
            self.clients.append(Client(self.addr, filter_, func))

            return func

        return wrapper

    def start(self):
        for client in self.clients:
            Thread(target=client.start).start()


class Client:
    def __init__(self, addr, filter_, callback):
        self.addr = addr
        self.filter = filter_
        self.callback = callback

        self.sock = socket()
        self.response_to = None  # tmp var

    def listener(self):
        while True:
            raw_request = recvmsg(self.sock)
            self.response_to, request = loads(raw_request)
            self.callback(self, request)

    def heartbeat_manager(self):
        """
        Periodic-event-based function
        """

        sendmsg(self.sock, HEARTBEAT + round(cpu_percent()).to_bytes(1, 'little'))

    # USER API STARTS HERE

    def response(self, response):
        sendmsg(self.sock, RESPONSE + dumps([self.response_to, response]).encode())

    def start(self):
        ip, port = self.addr
        print(f'[HANDLER-CLIENT] Connecting to {ip}:{port}')
        self.sock.connect(self.addr)

        handshake_manager = HandshakeManager(self.sock)
        succeeded, description = handshake_manager.do_handshake(self.filter)

        if not succeeded:
            print('[HANDLER-CLIENT] Failed to handshake with mainserver:', description)
            return

        print('[HANDLER-CLIENT] Handshake with mainserver succeeded: '
              'mainserver-name is', description)

        periodic_events_executor = PeriodicEventsExecutor()
        periodic_events_executor.add_event(HEARTBEAT_PERIODICITY, self.heartbeat_manager)
        periodic_events_executor.start()

        print('[HANDLER-CLIENT] Started heartbeat manager')
        print('[HANDLER-CLIENT] Starting listener')
        self.listener()
