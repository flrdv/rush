import logging
from json import dumps

from rush.webserver import WebServer

logger = logging.getLogger('main')
server = WebServer(port=9090, processes=None)

server.add_redirect('/easter', '/egg')


@server.on_startup
def on_startup(loader):
    logger.info('Wow! I\'m on-startup event callback!')
    loader.cache_files('index.html')


@server.on_shutdown
def on_shutdown():
    logger.info('Server is shutting down')


@server.route('/')
def main_page_handler(request):
    request.response_file('index.html')


@server.route('/egg')
def egg_handler(request):
    request.response_file('fuckoff.html')


@server.route('/hello')
def say_hello(request):
    # this method call is required if you wanna work with request
    # query string. This will take a time to parse, but will not
    # take time if you don't wanna use url parameters
    request.parse_args()
    
    name = request.args.get('name', 'world')
    request.response(200, f'hello, {name}!')


@server.route('/print-request')
def print_request(request):
    major, minor = request.protocol
    formatted_headers = '\n'.join(f'{var}: {val}' for var, val in request.headers.items())
    request.response(200,
                     f"""\
{request.method} {request.path} HTTP/{major}.{minor}
{formatted_headers}

{request.body or ''}\
""")


@server.route(any_path=True)    # the simplest way to route all other paths
# also possible: @server.route(filter_=lambda request: True), but this one is better
# because calls in python are expensive enough
def any_other_file_handler(request):
    request.response_file(request.path)


server.start()
