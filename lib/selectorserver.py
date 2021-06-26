"""
EpollServer(sock, maxconns: int = 0)

sock object should be already bind, EpollServer will automatically
call sock.listen() and make it non-blocking

there are 4 types of events:
    CONNECT - on connect to server
    DISCONNECT - on disconnect of server
    RECEIVE - on receiving some data
    RESPONSE - on sending data

to handle the events, you need to have a function that
receives only 1 argument - client's connection

if handler handles CONNECT event, to deny connection it has to return False

example:
```
import epollserver

epoll_server = epollserver.EpollServer(('localhost', 8080))


@epoll_server.handler(on_event=epollserver.CONNECT)
def connect_handler(conn):
    ip, port = conn.getpeername()
    print('new conn:', ip, port)

    # return False - if connection shouldn't be processed and
    # registered in epoll. Use it if you deny connection


# OR
epoll_server.add_handler(connect_handler, on_event=epollserver.CONNECT)

# and run it (in blocking mode, if option "threaded"
# is set to False (by default))
epoll_server.start()
```
"""

import logging
import selectors
from threading import Thread
from traceback import format_exc
from socket import socket, MSG_PEEK

logger = logging.getLogger(__name__)

CONNECT = 0
DISCONNECT = 1
RECEIVE = 2
RESPONSE = 3
EPOLLSERVER_EVENTS2STR = {
    CONNECT: 'CONNECT',
    DISCONNECT: 'DISCONNECT',
    RECEIVE: 'RECEIVE',
    RESPONSE: 'RESPONSE'
}


class EpollServer:
    def __init__(self, addr_or_sock, maxconns=0):
        self.polling = selectors.DefaultSelector()
        self.handlers = {}  # epoll event: callable

        if isinstance(addr_or_sock, (tuple, list)):
            self.server_sock = socket()
            self.server_sock.bind(addr_or_sock)
            self.server_sock.listen(maxconns)
            self.server_sock.setblocking(False)
        else:
            addr_or_sock.listen(maxconns)
            addr_or_sock.setblocking(False)
            self.server_sock = addr_or_sock

        self.addr = self.server_sock.getsockname()

        self._running = False
        self.conns = []

    def add_handler(self, handler, on_event=all):
        self.handlers[on_event] = handler

    def modify(self, fd, eventmask):
        self.polling.modify(fd, eventmask)

    def start(self, threaded=False, eventsmask=selectors.EVENT_READ):
        if self._running:
            raise RuntimeError('server already started')

        if threaded:
            server_thread = Thread(target=self.start)
            server_thread.start()

            return server_thread

        self._running = True
        self.polling.register(self.server_sock, eventsmask)

        # _running is also a flag. Server will stop after _running will be set to False
        while self._running:
            for key, mask in self.polling.select(timeout=.5):
                fd = key.fileobj
                event_type = self.get_event_type(fd, mask)
                handler = self.handlers.get(event_type)

                if handler is None:
                    # no attached handlers registered
                    continue

                if event_type == CONNECT:
                    conn, addr = self.server_sock.accept()

                    if self.call_handler(handler, conn) is False:
                        # connection hasn't been accepted or exception occurred
                        # nothing will happen if we'll close closed socket
                        conn.close()
                        continue

                    conn.setblocking(False)
                    self.conns.append(fd)
                    self.polling.register(fd, eventsmask)
                elif event_type == DISCONNECT:
                    self.call_handler(handler, fd)
                    # socket will be automatically unregistered from polling (I hope)
                    fd.close()  # noqa
                    self.conns.remove(fd)
                else:
                    self.call_handler(handler, fd)

    def call_handler(self, handler, conn):
        """
        A safe way to call handler (and catch unhandled exceptions)
        """

        try:
            return handler(conn)
        except Exception as exc:
            logger.exception(f'Caught an unhandled exception in handler "{handler.__name__}":\n' +
                             format_exc())

            return False

    def get_event_type(self, fd, event):
        if fd not in self.conns:
            return CONNECT
        elif event & selectors.EVENT_READ:
            try:
                peek_byte = fd.recv(1, MSG_PEEK)
            except ConnectionResetError:
                return DISCONNECT

            if not peek_byte:
                return DISCONNECT

            return RECEIVE
        elif event & selectors.EVENT_WRITE:
            return RESPONSE
        else:
            raise NotImplementedError('unsupported epoll signal: ' + str(event))

    def handler(self, on_event=all):
        def decorator(func):
            self.handlers[on_event] = func

            return func

        return decorator

    def stop(self):
        # max server alive-time after stopping is 1 second
        self._running = False

        for conn in self.conns:
            conn.close()

        self.polling.close()
        self.server_sock.close()

    def __del__(self):
        self.stop()
