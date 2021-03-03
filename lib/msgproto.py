import socket


FUTURE_MSG_LEN_BYTES = 4
READ_CHUNK_SIZE = 4096


def sendmsg(sock: socket.socket, data: bytes):
    packet_len = len(data).to_bytes(4, 'little')

    return sock.send(packet_len + data)


def recvmsg(sock: socket.socket):
    encoded_msg_len = b''

    while len(encoded_msg_len) < FUTURE_MSG_LEN_BYTES:
        encoded_msg_len += sock.recv(FUTURE_MSG_LEN_BYTES - len(encoded_msg_len))

    msg_len = int.from_bytes(encoded_msg_len, 'little')

    return recvbytes(sock, msg_len)


def recvbytes(sock, bytescount):
    source = b''

    while len(source) < bytescount:
        source += sock.recv(bytescount - len(source))

    return source
