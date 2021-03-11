import epollserver

"""
this file is a good example (or even demo) of the work of the epollserver lib
"""

epoll_server = epollserver.EpollServer(('localhost', 8801))


@epoll_server.handler(on_event=epollserver.CONNECT)
def handle_conn(_, server):
    conn, addr = server.accept()
    print('new conn from', addr)

    return conn


@epoll_server.handler(epollserver.RECEIVE)
def handle_recvmsg(_, conn: epollserver.socket):
    print(f'received data from {conn.getpeername()}: {conn.recv(10)}')
    conn.send(b'hello!')


@epoll_server.handler(epollserver.DISCONNECT)
def handle_disconnect(_, conn):
    print('disconnected:', conn.getpeername())


epoll_server.start()
