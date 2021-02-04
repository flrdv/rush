import socket
from traceback import format_exc

import proto.msgproto as proto


try:
    sock = socket.socket()
    sock.connect(('localhost', 11100))
    proto.sendmsg(sock, b'\x00my-cluster')

    proto.sendmsg(sock, b'\x01my-cluster')
    print(proto.recvmsg(sock))

    proto.sendmsg(sock, b'\x01my-nonexisting-cluster')
    print(proto.recvmsg(sock))
finally:
    print('An error occurred:')
    print(format_exc())
