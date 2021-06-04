import logging

from webserver import WebServer

logger = logging.getLogger(__name__)
server = WebServer(port=9090)


@server.on_startup
def on_startup(loader):
    logger.info('Wow! I\'m on-startup event callback!')
    loader.cache('index.html')


@server.on_shutdown
def on_shutdown():
    logger.info('Server is dying :(')


@server.route('/')
def main_page_handler(request):
    request.response_file('index.html', headers={'Connection': 'close'})


@server.route('*')
def any_other_file_handler(request):
    request.response_file(request.path, headers={'Connection': 'close'})
