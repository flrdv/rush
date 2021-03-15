from lib import epollserver


class Server:
    def __init__(self, receive_block_size=4096):
        self.receive_block_size = receive_block_size

        self.requests = {}  # conn: [msg_len_received, left_to_receive, received]
        self.responses = {}

        self.epoll_server = epollserver.EpollServer(('0.0.0.0', 9090))
        self.epoll_server.add_handler(self.conn_handler, epollserver.CONNECT)
        self.epoll_server.add_handler(self.requests_handler, epollserver.RECEIVE)
        self.epoll_server.add_handler(self.disconn_handler, epollserver.DISCONNECT)

    def conn_handler(self, _, conn):
        print('new conn from', conn.getpeername())

    def disconn_handler(self, _, conn):
        print('disconnected:', conn.getpeername())

    def requests_handler(self, _, conn):
        if conn not in self.requests:
            future_msg_len = conn.recv(4)

            if len(future_msg_len) == 4:
                self.requests[conn] = [True, int.from_bytes(future_msg_len, 'little'), b'']
            else:
                self.requests[conn] = [False, 4 - len(future_msg_len), future_msg_len]
        else:
            request_cell = self.requests[conn]
            left_to_receive = request_cell[1]

            if not request_cell[0]:  # msg len haven't been received fully yet
                # you may ask me, why did I do such a work for simple 4 bytes receiving
                # If I won't do this, there is a possibility that some asshole
                # with slow internet will send me a byte per second, and this can raise
                # an UB
                left_to_receive = request_cell[1]
                received = conn.recv(left_to_receive)

                if left_to_receive - len(received) <= 0:
                    self.requests[conn] = [True, int.from_bytes(request_cell[2], 'little') +
                                           received, b'']
                else:
                    request_cell[2] += received
                    request_cell[1] -= len(received)
            else:
                request = conn.recv(left_to_receive if left_to_receive <= self.receive_block_size
                                    else self.receive_block_size)
                request_cell[2] += request
                request_cell[1] -= len(request)

                if request_cell[1] <= 0:
                    self.distribute_update(request_cell[2])
                    self.requests.pop(conn)

    def distribute_update(self, request):
        print('received new request:', request)

    def start(self):
        self.epoll_server.start()


if __name__ == '__main__':
    server = Server()
    print('server is running')
    server.start()
