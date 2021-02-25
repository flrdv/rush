import socket


try:
    sock = socket.socket()
    sock.connect(('localhost', 8801))
    sock.send(b'hello!')
    print(sock.recv(10))
    sock.close()
except Exception as exc:
    print('an error occurred:', exc)
