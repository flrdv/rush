import socket
from struct import pack, unpack


FUTURE_MSG_LEN_BYTES = 4
READ_CHUNK_SIZE = 4096


def sendmsg(sock: socket.socket, data: bytes):
    packet_len = pack('>I', len(data))

    return sock.send(packet_len + data)


def recvmsg(sock: socket.socket):
    encoded_msg_len = b''

    while len(encoded_msg_len) < FUTURE_MSG_LEN_BYTES:
        encoded_msg_len += sock.recv(FUTURE_MSG_LEN_BYTES - len(encoded_msg_len))

    msg_len, = unpack('>I', encoded_msg_len)
    msg = b''

    while len(msg) < msg_len:
        msg += sock.recv(READ_CHUNK_SIZE)

    return msg
