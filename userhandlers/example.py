import server as webserver
from lib.entities import Request, Response


server = webserver.WebServer(debug_mode=True)

default_response = Response('HTTP/1.1', 200, 'You found an easter-egg!')
wellcum_html_template = """
<html>
    <head>
        <title>Welcome!</title>
    </head>
    <body>
        <h1><tt>Welcome to Rush-webserver!</tt></h1>
        <br><br>
        <h3>If you see this page, Rush-webserver works correct</h3>
    </body>
</html>
"""


@server.filter(func=lambda request: request.path == '/egg')
def handler_with_filter(request: Request):
    request.response(default_response)


@server.route('/easter')
def routing_handler(request: Request):
    request.response(default_response)


@server.route('/')
def mainpage_handler(request: Request):
    request.response(Response(request.protocol, 200, wellcum_html_template))


server.start()
