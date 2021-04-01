import server as webserver
from lib.entities import Request


server = webserver.WebServer()


@server.serve(func=lambda msg: True)
def handler(request: Request):
    request.response(b'HTTP/1.1 200 OK\n\nHello, World!\n')


server.start()
