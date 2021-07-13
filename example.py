import logging

from rush.webserver import WebServer
from rush.utils.cache import InMemoryCache, FsCache, FdCache

logger = logging.getLogger('main')
server = WebServer(port=9090, processes=None,
                   cache=InMemoryCache)

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
    args = request.get_args()
    
    name = ' '.join(args.get('name', ['world']))
    request.response(200, f'hello, {name}!')


@server.route('/print-request')
def print_request(request):
    major, minor = request.protocol
    formatted_headers = '\n'.join(f'{var.decode()}: {val.decode()}' for var, val in request.headers.items())
    request.response(200,
                     f"""\
{request.method.decode()} {request.path} HTTP/{major}.{minor}
{formatted_headers}

{request.body or ''}\
""")


# the simplest way to route all other paths
# also possible: @server.route(filter_=lambda request: True), but this one is better
# because calls in python are expensive enough
@server.route(any_path=True, methods={'GET'})
def any_other_file_handler(request):
    request.response_file(request.path)


@server.route('/receive-form', methods={'POST'})
def receive_form(request):
    print('I received post-request!')
    print('post-request attached file:')
    print(request.file)
    print(request.body)


server.start()
