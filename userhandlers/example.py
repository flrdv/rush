import server as webserver
from utils.entities import Request, Response, Loader

"""
This example is not just example: this is a preview of how
webserver should be used. Like best usage practises
"""


server = webserver.WebServer(debug_mode=False)
loader = Loader(caching=True)
# shitcode just to avoid using loader inside webserver
server.set_404_page(loader.load('404.html'))

loader.cache_files(
    '/index.html',
    '/404.html',
)


"""
These 2 handlers below are demonstrating 2 different ways
of solving the same problem. Just a demo
"""

static_response = Response('HTTP/1.1', 200, 'You found an easter-egg!')


@server.route('/easter')
def routing_handler(request: Request):
    request.static_response(static_response)


@server.filter(func=lambda request: request.path == '/egg')
def handler_with_filter(request: Request):
    request.static_response(static_response)


@server.filter(func=lambda request: True)
def all_other_pages_handler(request: Request):
    request.response(request.protocol, 200, loader.load(request.path, cache=False))


server.start()
