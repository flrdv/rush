import logging

from rush.webserver import WebServer
from rush.core import loader as loaderlib, entities
from rush.utils.cache import InMemoryCache, DescriptorsCache, FileSystemCache

logger = logging.getLogger('main')
server = WebServer(port=9090,
                   processes=None,
                   cache=InMemoryCache)

server.add_redirect('/easter', '/egg')


@server.on_startup
def on_startup(loader: loaderlib.Loader):
    logger.info('Wow! I\'m on-startup event callback!')
    loader.cache_files('index.html')


@server.on_shutdown
def on_shutdown():
    logger.info('Server is shutting down')


@server.route('/')
def main_page_handler(request: entities.Request):
    request.response_file('index.html')


@server.route('/egg')
def egg_handler(request: entities.Request):
    request.response_file('fuckoff.html')


@server.route('/hello')
def say_hello(request: entities.Request):
    args = request.get_args()
    
    name = ' '.join(args.get('name', ['world']))
    request.response(f'hello, {name}!')


@server.route('/print-request')
def print_request(request: entities.Request):
    request.response(str(request))


# the simplest way to route all other paths
# also possible: @server.route(filter_=lambda request: True), but this one is better
# because calls in python are expensive enough, but also can catch all the requests
# that has to be processed in another handler
@server.route(any_path=True, methods={'GET'})
def any_other_file_handler(request: entities.Request):
    request.response_file(request.path)


@server.route('/receive-file', methods={'POST'})
def receive_form(request: entities.Request):
    print('received request:')
    print(request)

    if not request.file:
        form = request.get_form()

        if 'filename' in form:
            return request.response('error: already uploaded', 403)

        return request.response('error: no file attached', 403)

    args = request.get_args()

    if 'filename' not in args:
        return request.response('error: filename was not specified', 403)

    fd = open(args['filename'], 'wb')
    request.receive_file(lambda chunk: fd.write(chunk),                         # on_chunk callback
                         lambda: (fd.close(), request.response(b'written')))    # on_complete callback


server.start()
