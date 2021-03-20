import socket
from threading import Thread

from lib.msgproto import sendmsg, recvmsg


def send(msg: bytes):
    with socket.socket() as sock:
        sock.settimeout(1)
        print('connecting...')
        sock.connect(('192.168.0.102', 9090))
        print('connected\nsending hello world...')
        sendmsg(sock, msg)
        print('sent\nreceiving response')
        response = recvmsg(sock)
        print('received:', response)

    print('closed connection')


thread1 = Thread(target=send, args=(b'hello, world!',))
thread2 = Thread(target=send, args=(b'not cool, but how?',))
thread3 = Thread(target=send, args=(b'why is it? is it lorem ipsum? Yes!',))
thread1.start(), thread2.start(), thread3.start()
