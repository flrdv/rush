from socket import socket
from threading import Thread
from psutil import cpu_percent
from traceback import format_exc

from handler.entities import HandshakeManager
from lib.periodic_events import PeriodicEventsExecutor
from lib.msgproto import sendmsg, recv_request, send_request

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

        if filter_ is not None:
            fields = filter_.values

        def wrapper(func):
            self.clients.append(Client(self.addr, fields, func))

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

    def listener(self):
        while True:
            request_from, request = recv_request(self.sock)

            try:
                self.callback(self, request_from, request)
            except Exception as exc:
                print('[HANDLER-CLIENT] Unhandled error occurred while processing request:',
                      f'{exc.__class__.__name__}: {exc}')
                print('[HANDLER-CLIENT] Full error text:')
                print(format_exc())

    def heartbeat_manager(self):
        """
        Periodic-event-based function
        """

        sendmsg(self.sock, HEARTBEAT + round(cpu_percent()).to_bytes(1, 'little'))

    # USER API STARTS HERE

    def response(self, response_to, response):
        send_request(self.sock, response_to, response)

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
