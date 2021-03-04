from socket import socket

from lib.epollserver import do_handshake


with socket() as sock:
    sock.connect(('192.168.0.102', 11102))

    if do_handshake(sock, 'server'):
        print('it\'s our boy!')
    else:
        print('I don\'t know who is this motherfucker.')

print('The end')
