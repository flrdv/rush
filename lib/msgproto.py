import socket


FUTURE_MSG_LEN_BYTES = 4
READ_CHUNK_SIZE = 4096


def sendmsg(sock: socket.socket, data: bytes, msg_len_bytes=FUTURE_MSG_LEN_BYTES):
    packet_len = len(data).to_bytes(msg_len_bytes, 'little')

    return sock.send(packet_len + data)


def recvmsg(sock: socket.socket, msg_len_bytes=FUTURE_MSG_LEN_BYTES,
            timeout=None):
    encoded_msg_len = b''

    while len(encoded_msg_len) < msg_len_bytes:
        encoded_msg_len += sock.recv(msg_len_bytes - len(encoded_msg_len))

    msg_len = int.from_bytes(encoded_msg_len, 'little')

    return recvbytes(sock, msg_len, timeout)


def recvbytes(sock, bytescount, timeout=None):
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    source = b''
    bytes_received = 0

    try:
        while bytes_received < bytescount:
            received = sock.recv(bytescount - len(source))
            bytes_received += len(received)

            source += received
    except socket.timeout:
        source = None

    sock.settimeout(old_timeout)

    return source


def fmt_packet(data):
    return len(data).to_bytes(4, 'little') + data


"""
Here starts rush-specific protocol functions
"""


def send_request(conn, request_to: bytes, request: bytes):
    main_packet = len(request_to).to_bytes(1, 'little') + request_to + request
    sendmsg(conn, main_packet)


def recv_request(conn):
    msg = recvmsg(conn)

    len_of_client_id = msg[0]
    response_to = msg[1:len_of_client_id]
    request = msg[len_of_client_id:]

    return response_to, request
