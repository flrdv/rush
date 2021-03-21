import socket
from random import choice
from time import time, sleep
from threading import Thread, get_ident

from lib.msgproto import sendmsg, recvmsg


class StressTest:
    def __init__(self, clients=200, packets_per_second=10,
                 wait_response=True, test_time=10, requests_pool=None,
                 ):
        self.clients = clients
        self.packets_per_second = packets_per_second
        self.packets_maxtimeout = 1 / packets_per_second
        self.wait_response = wait_response
        self.test_time = test_time or 999999
        self.threads = []

        self.active = False
        self.total_packets_sent = 0
        self.server_cant_handle_specified_load = 0
        self.requests = requests_pool or [b"hello, world!",
                                          b'lorem ipsum, my brother!',
                                          b'it should be long request as fuck, but I\'m not sure']
        self.iterations = {}    # thread-id: iters

    def client(self):
        ident = get_ident()
        self.iterations[ident] = 0

        with socket.socket() as sock:
            sock.connect(('192.168.0.102', 9090))

            began_at = time()

            while time() <= began_at + self.test_time and self.active:
                for _ in range(self.packets_per_second):
                    sendmsg(sock, choice(self.requests))
                    self.total_packets_sent += 1

                    if self.wait_response:
                        started_waiting_at = time()

                        try:
                            recvmsg(sock, timeout=1)
                        except TimeoutError:
                            print('Server fucked up')
                        else:
                            if time() - started_waiting_at > self.packets_maxtimeout:
                                self.server_cant_handle_specified_load += 1

                        sleep(self.packets_maxtimeout)

                self.iterations[ident] += 1

        print(f'finished ({round(time() - began_at, 2)} secs)')

    def start(self):
        print('Starting', self.clients, 'clients...')
        self.active = True

        for _ in range(self.clients):
            thread = Thread(target=self.client)
            self.threads.append(thread)
            thread.start()

        print('Started. Time for stress-test estimated:', self.test_time)

        try:
            sleep(self.test_time)
        except KeyboardInterrupt:
            print('Aborting stress test before it\'s finished')

        self.active = False

        map(lambda thread_: thread_.join(), self.threads)

        rps_for_every_client = [iters / self.packets_per_second
                                for ident, iters in self.iterations.items()]
        total_rps = self.total_packets_sent / len(rps_for_every_client)

        sleep(.5)

        print('Total requests sent:', self.total_packets_sent)
        print('RPS:', total_rps)
        print('Server failed and didn\'t response with required max timeout between packets:',
              self.server_cant_handle_specified_load)


def send(msg: bytes):
    with socket.socket() as sock:
        sock.settimeout(1)
        print('connecting...')
        sock.connect(('192.168.0.102', 9090))
        print('connected')
        for _ in range(10):
            print('sending:', msg)
            sendmsg(sock, msg)
            print('sent\nreceiving response')
            response = recvmsg(sock)
            print('received:', response)

    print('closed connection')


# thread1 = Thread(target=send, args=(b'hello, world!',))
# thread2 = Thread(target=send, args=(b'not cool, but how?',))
# thread3 = Thread(target=send, args=(b'why is it? is it lorem ipsum? Yes!',))
# thread1.start(), thread2.start(), thread3.start()

if __name__ == '__main__':
    stress_test = StressTest(clients=1000,
                             packets_per_second=7)
    stress_test.start()
