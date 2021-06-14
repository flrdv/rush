import logging

from webserver import WebServer

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


@server.route('*')
def any_other_file_handler(request):
    request.response_file(request.path)


server.start()
