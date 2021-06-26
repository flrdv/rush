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

import select
import logging
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

EPOLLSERVEREVENTS2EPOLLEVENTS = {
    CONNECT: select.EPOLLIN,
    DISCONNECT: select.EPOLLHUP,
    RECEIVE: select.EPOLLIN,
    RESPONSE: select.EPOLLOUT
}


class EpollServer:
    def __init__(self, addr_or_sock, maxconns=0):
        self.epoll = select.epoll()
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
        self.conns = {}

    def add_handler(self, handler, on_event=all):
        self.handlers[on_event] = handler

    def modify(self, fd, for_event):
        self.epoll.modify(fd, EPOLLSERVEREVENTS2EPOLLEVENTS[for_event])

    def direct_modify(self, fd, event):
        """
        Same as EpollServer.modify(), but instead of using internal epollserver.<EVENT>,
        using directly select.<EVENT>
        """

        self.epoll.modify(fd, event)

    def start(self, threaded=False, epoll_events_mask=select.EPOLLIN):
        if self._running:
            raise RuntimeError('server already started')

        if threaded:
            server_thread = Thread(target=self.start)
            server_thread.start()

            return server_thread

        self._running = True
        self.epoll.register(self.server_sock.fileno(), epoll_events_mask)

        # _running is also a flag. Server will stop after _running will be set to False
        while self._running:
            events = self.epoll.poll(1)

            for fileno, event in events:
                event_type = self.get_event_type(fileno, event)
                handler = self.handlers.get(event_type)

                if handler is None:
                    # no attached handlers registered
                    continue

                if event_type == CONNECT:
                    conn, addr = self.server_sock.accept()

                    if self.call_handler(handler, CONNECT, conn) is False:
                        # connection hasn't been accepted or exception occurred
                        # nothing will happen if we'll close closed socket
                        conn.close()
                        continue

                    conn.setblocking(False)
                    conn_fileno = conn.fileno()
                    self.conns[conn_fileno] = conn
                    self.epoll.register(conn_fileno, epoll_events_mask)
                elif event_type == DISCONNECT:
                    conn = self.conns.pop(fileno)
                    self.call_handler(handler, DISCONNECT, conn)
                    conn.close()  # socket will be automatically unregistered from epoll
                else:
                    self.call_handler(handler, event_type, self.conns[fileno])

    def call_handler(self, handler, event_type, conn):
        """
        A safe way to call handler (and catch unhandled exceptions)
        """

        try:
            return handler(conn)
        except Exception as exc:
            event_type_stringified = EPOLLSERVER_EVENTS2STR[event_type]
            logger.exception(f'Caught an unhandled exception in handler "{handler.__name__}" while '
                             f'handling {event_type_stringified}-event:\n{format_exc()}')

            return False

    def get_event_type(self, fileno, event):
        if fileno == self.server_sock.fileno():
            return CONNECT
        elif event & select.EPOLLIN:
            try:
                peek_byte = self.conns[fileno].recv(1, MSG_PEEK)
            except ConnectionResetError:
                return DISCONNECT

            if not peek_byte:
                return DISCONNECT

            return RECEIVE
        elif event & select.EPOLLOUT:
            return RESPONSE
        elif event & select.EPOLLHUP:
            return DISCONNECT
        else:
            raise NotImplementedError('unavailable epoll signal: ' + str(event))

    def handler(self, on_event):
        def decorator(func):
            self.handlers[on_event] = func

            return func

        return decorator

    def stop(self):
        # max server alive-time after stopping is 1 second
        self._running = False
        self.epoll.close()
        self.server_sock.close()

    def __del__(self):
        self.stop()
