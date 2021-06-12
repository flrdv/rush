from os import abort
from socket import socket
import logging as _logging
from threading import Thread

from typing import List, Dict
from traceback import format_exc
from multiprocessing import Process

import core.server
import core.handlers
import core.entities
import core.utils.loader
import core.utils.termutils
import core.utils.sockutils
import core.utils.default_err_handlers

if not core.utils.termutils.is_linux():
    raise RuntimeError('Rush-webserver is only for linux. Ave Maria!')

_logging.basicConfig(level=_logging.DEBUG,  # noqa
                     format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
                     handlers=[
                         _logging.FileHandler("logs/handlers.log"),
                         _logging.StreamHandler()]
                     )
logger = _logging.getLogger(__name__)


class WebServer:
    def __init__(self, ip='localhost', port=8000, max_conns=None,
                 loader_impl=None, cache_impl=None,
                 sources_root='localfiles', logging=True):
        logger.disabled = not logging
        self.addr = (ip, port)
        self.max_conns = max_conns

        if max_conns is None:
            self.max_conns = core.utils.termutils.get_max_descriptors()

        sock = socket()
        core.utils.sockutils.bind_sock(sock, self.addr)

        self.handlers = []
        self.err_handlers = {
            'not-found': core.utils.default_err_handlers.not_found,
            'internal-error': core.utils.default_err_handlers.internal_error,
        }
        self.server_events_callbacks: Dict[callable or None] = {
            'on-startup': None,
            'on-shutdown': None,
        }
        self.redirects = {}

        self.process_workers: List[Process] = []
        self.loader = (loader_impl or core.utils.loader.Loader)(cache_impl, root=sources_root)

        self.http_server = core.server.HttpServer(sock, self.max_conns)
        handlers_manager = core.handlers.HandlersManager(self.http_server, self.loader,
                                                         self.handlers, self.err_handlers,
                                                         self.redirects)
        self.http_server.on_message_complete_callback = handlers_manager.call_handler

    def route(self, path, methods=None, filter_=None):
        if path[0] not in '/*':
            path = '/' + path

        def decorator(func):
            self.handlers.append(core.entities.Handler(func=func,
                                                       filter_=filter_,
                                                       path_route=path,
                                                       methods=methods))

            return func

        return decorator

    def err_handler(self, err_type):
        def wrapper(func):
            self.err_handlers[err_type] = func

            return func

        return wrapper

    def on_startup(self, func):
        self.server_events_callbacks['on-startup'] = func

        return func

    def on_shutdown(self, func):
        self.server_events_callbacks['on-shutdown'] = func

        return func

    def add_redirect(self, from_path, to):
        self.redirects[from_path] = to

    def add_redirects(self, redirects: dict):
        self.redirects.update(redirects)

    def start(self):
        on_startup_event_callback = self.server_events_callbacks['on-startup']

        if on_startup_event_callback is not None:
            logger.debug('found on-startup server event callback')
            on_startup_event_callback(self.loader)

        ip, port = self.addr
        logger.info(f'set max connections: {self.max_conns}')
        logger.info(f'running http server on {ip}:{port}')

        try:
            self.http_server.run()
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.info('aborted by user')
        except Exception as exc:
            logger.error(f'an error occurred while running http server: {exc} (see detailed trace '
                         'below)')
            logger.exception(format_exc())

        self.stop()

    def stop(self):
        on_shutdown_event_callback = self.server_events_callbacks['on-shutdown']

        if on_shutdown_event_callback is not None:
            logger.debug('found on-shutdown server event callback')
            on_shutdown_event_callback()

        logger.info('web-server has been stopped. Good bye')
        abort()

    def __del__(self):
        self.stop()
