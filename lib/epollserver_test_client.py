import socket


try:
    sock = socket.socket()
    sock.connect(('192.168.0.102', 8801))
    print('connected!')
    sock.send(b'hello!')
    print('sent!')
    print('received:', sock.recv(10))
    sock.close()
except Exception as exc:
    print('an error occurred:', exc)
