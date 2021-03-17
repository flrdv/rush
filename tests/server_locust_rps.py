from socket import socket
from random import choice

from locust import User, task, between

from lib.msgproto import sendmsg, recvmsg

PHRASES = (
    b'hello, world!',
    b'lorem ipsum, isnt it?',
    b'what are you doing?',
    b'mate, hi!'
)


class ServerClient(User):
    host = '192.168.0.102:9090'

    def __init__(self, *args, **kwargs):
        super(ServerClient, self).__init__(*args, **kwargs)
        self.sock = socket()
        self.sock.connect(('192.168.0.102', 9090))

    @task
    def send_random_phrase(self):
        sendmsg(self.sock, choice(PHRASES))
        response = recvmsg(self.sock)

    wait_time = between(.1, 1)  # try to comment and look what'll happen
