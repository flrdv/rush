import socket
from typing import List
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
        self.threads: List[Thread] = []

        self.active = False
        self.total_packets_sent = 0
        self.server_cant_handle_specified_load = 0
        self.requests = requests_pool or [b"hello, world!",
                                          b'lorem ipsum, my brother!',
                                          b'it should be long request as fuck, but I\'m not sure']
        self.iterations = {}    # thread-id: [iters, livetime]
        self.response_time = []
        self.clients_disconnected = 0

    def client(self):
        ident = get_ident()
        self.iterations[ident] = [0, 0]

        with socket.socket() as sock:
            sock.connect(('192.168.0.102', 9090))

            began_at = time()

            try:
                while time() <= began_at + self.test_time and self.active:
                    for _ in range(self.packets_per_second):
                        sendmsg(sock, choice(self.requests))
                        self.total_packets_sent += 1

                        if self.wait_response:
                            started_waiting_at = time()

                            try:
                                assert recvmsg(sock, timeout=1) is not None
                            except (TimeoutError, AssertionError):
                                print('Server fucked up')
                            else:
                                self.response_time.append(time() - started_waiting_at)

                    self.iterations[ident][0] += 1
            except ConnectionResetError:
                print('Server has disconnected this client')
                self.clients_disconnected += 1

        alive_time = round(time() - began_at, 2)
        print(f'finished ({alive_time} secs)')
        self.iterations[ident][1] = alive_time

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

        for thread in self.threads:
            thread.join()

        rps_for_every_client = [(iters * self.packets_per_second) / alivetime
                                for ident, (iters, alivetime) in self.iterations.items()]
        average_rps = sum(rps_for_every_client) / len(rps_for_every_client)
        average_response_time = sum(self.response_time) / len(self.response_time)

        sleep(.5)

        print('Total requests sent:', self.total_packets_sent)
        print('Average RPS:', average_rps)
        print('Average response time:', average_response_time * 1000, 'ms')
        print('Clients were disconnected:', self.clients_disconnected)


def time_request(msg: bytes, retries=3):
    with socket.socket() as sock:
        sock.settimeout(1)
        print('connecting...')
        sock.connect(('192.168.0.102', 9090))
        print('connected')

        results = []

        for _ in range(retries):
            began_at = time()

            print('sending:', msg)
            sendmsg(sock, msg)
            print('sent\nreceiving response')
            response = recvmsg(sock)
            ended_at = time()
            time_went = ended_at - began_at
            print('received:', response)
            print('time elapsed:', time_went * 1000, 'ms')
            results.append(time_went)

        print('Finished. Average response time:', (sum(results) / len(results)) * 1000, 'ms')

    print('closed connection')


# thread1 = Thread(target=send, args=(b'hello, world!',))
# thread2 = Thread(target=send, args=(b'not cool, but how?',))
# thread3 = Thread(target=send, args=(b'why is it? is it lorem ipsum? Yes!',))
# thread1.start(), thread2.start(), thread3.start()

if __name__ == '__main__':
    stress_test = StressTest(clients=1,
                             packets_per_second=1000)
    stress_test.start()
    # time_request(b'hello, world!', 10)
