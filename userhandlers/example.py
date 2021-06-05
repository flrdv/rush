import logging

from webserver import WebServer

logger = logging.getLogger('main')
server = WebServer(port=9090)

server.add_redirect('/easter', '/egg')


@server.on_startup
def on_startup(loader):
    logger.info('Wow! I\'m on-startup event callback!')
    loader.cache_files('index.html')


@server.on_shutdown
def on_shutdown():
    logger.info('Server is dying :(')


@server.route('/')
def main_page_handler(request):
    print('watcha!')
    request.response_file('index.html', headers={'Connection': 'close'})


@server.route('*')
def any_other_file_handler(request):
    request.response_file(request.path, headers={'Connection': 'close'})


server.start()
