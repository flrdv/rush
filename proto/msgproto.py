import socket
from struct import pack, unpack


FUTURE_MSG_LEN_BYTES = 4
READ_CHUNK_SIZE = 4096


def sendmsg(sock: socket.socket, data: bytes):
    packet_len = pack('>I', len(data))

    return sock.send(packet_len + data)


def recvmsg(sock: socket.socket):
    encoded_msglen = b''

    while len(encoded_msglen) < FUTURE_MSG_LEN_BYTES:
        encoded_msglen += sock.recv(FUTURE_MSG_LEN_BYTES - len(encoded_msglen))

    msglen, = unpack('>I', encoded_msglen)
    msg = b''

    while len(msg) < msglen:
        msg += sock.recv(READ_CHUNK_SIZE)

    return msg
