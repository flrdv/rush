import server as webserver
from lib.entities import Request, Response


server = webserver.WebServer()

default_response = Response('HTTP/1.1', 200, 'OK', 'Hello from rush!')


@server.serve(func=lambda msg: True)
def handler(request: Request):
    request.response(default_response)


server.start()
