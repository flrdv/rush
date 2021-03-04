import lib.epollserver


epollserver = lib.epollserver.EpollServer(('192.168.0.102', 11102))


@epollserver.handler(lib.epollserver.CONNECT)
@lib.epollserver.handshake('server')
def connhandler(_, conn):
    ip, port = conn.getpeername()
    print('New connection:', ip, port)


@epollserver.handler(lib.epollserver.DISCONNECT)
def disconnect_handler(_, conn):
    conn.close()
    print('Disconnected')


epollserver.start()
