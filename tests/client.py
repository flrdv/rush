import socket

from lib.msgproto import sendmsg


with socket.socket() as sock:
    print('connecting...')
    sock.connect(('192.168.0.102', 9090))
    print('connected\nsending hello world...')
    sendmsg(sock, b'hello, world!')
    print('sent')

print('closed connection')
