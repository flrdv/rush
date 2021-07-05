import os
import socket
import logging as _logging
from signal import SIGKILL

from typing import Dict
from traceback import format_exc
from multiprocessing import cpu_count

from .core import entities, httpserver, handlers
from .core.utils import (termutils, default_err_handlers, sockutils,
                         loader as loaderlib, httputils)

if not termutils.is_linux():
    raise RuntimeError('Rush-webserver is only for linux. Ave Maria!')

if not os.path.exists('logs'):
    os.mkdir('logs')

_logging.basicConfig(level=_logging.DEBUG,  # noqa
                     format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
                     handlers=[
                         _logging.FileHandler("logs/handlers.log"),
                         _logging.StreamHandler()]
                     )
logger = _logging.getLogger(__name__)

DEFAULTPAGES_DIR = os.path.join(os.path.dirname(__file__), 'defaultpages')


class WebServer:
    def __init__(self, host='localhost', port=8000, max_conns=None,
                 loader=loaderlib.Loader, cache=loaderlib.AutoUpdatingCache,
                 sources_root=None, logging=True, processes=0):
        logger.disabled = not logging

        if processes is None:
            processes = cpu_count()

        self.processes = processes
        self.forks = []

        self.handlers = []
        self.err_handlers = {
            'not-found': default_err_handlers.not_found,
            'internal-error': default_err_handlers.internal_error,
        }
        self.server_events_callbacks: Dict[callable or None] = {
            'on-startup': None,
            'on-shutdown': None,
        }
        self.redirects = {}

        self.loader = loader(cache, root=sources_root or DEFAULTPAGES_DIR)

        self.addr = (host, port)

        if max_conns is None:
            max_conns = termutils.get_max_descriptors()
        elif max_conns > termutils.get_max_descriptors():
            logger.info('max_conns is less than descriptors available,')
            logger.info('setting max descriptors count to new value')
            max_conns = termutils.set_max_descriptors(max_conns)

        self.max_conns = max_conns
        self.dad = os.getpid()

    def route(self, path=None, methods=None, filter_=None,
              any_path=False):
        if path and path[0] not in '/*':
            path = '/' + path

        def decorator(func):
            self.handlers.append(entities.Handler(func=func,
                                                  filter_=filter_,
                                                  path_route=path,
                                                  methods=methods,
                                                  any_paths=any_path))

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
        self.redirects[from_path] = httputils.render_http_response(protocol=(1, 1),
                                                                   status_code=301,
                                                                   status_code_desc=None,  # choose it by itself
                                                                   user_headers={'Location': to},
                                                                   body=b'')

    def add_redirects(self, redirects: dict):
        self.redirects.update(redirects)

    def _i_am_dad_process(self):
        return self.dad == os.getpid()

    def start(self):
        on_startup_event_callback = self.server_events_callbacks['on-startup']

        if on_startup_event_callback is not None:
            on_startup_event_callback(self.loader)

        ip, port = self.addr

        if self.processes and termutils.is_wsl():
            logger.warning('wsl does not supports SO_REUSEPORT socket flag')
            logger.warning('setting processes count to 0')
            self.processes = 0

        logger.info(f'set max connections: {self.max_conns}')
        logger.info(f'set server processes count: {self.processes}')
        logger.debug(f'dad pid: {self.dad}')

        for fork_index in range(1, self.processes):
            if self._i_am_dad_process():
                # I could easily use walrus operator here, and that could be much
                # more beautiful. But backward capability of walrus operator sucks
                # so I have to use such a primitive and old-style way

                child_fork = os.fork()

                if child_fork != 0:
                    self.forks.append(child_fork)
                    logger.debug(f'fork #{fork_index} with pid {child_fork}')
            else:
                # every fork will continue iterating, but this will stop them
                break

        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)

        try:
            succeeded = sockutils.bind_sock(sock, self.addr,
                                            disable_logs=not self._i_am_dad_process())

            if not succeeded:
                logger.error('failed to bind server: retries limit exceeded')
                return
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.error('failed to bind server: aborted by user')
            return

        if self._i_am_dad_process():
            logger.info(f'running http server on {ip}:{port}')

        http_server = httpserver.HttpServer(sock, self.max_conns)
        handlers_manager = handlers.HandlersManager(http_server, self.loader,
                                                    self.handlers, self.err_handlers,
                                                    self.redirects)
        http_server.on_message_complete_callback = handlers_manager.call_handler

        while True:
            try:
                http_server.run()
            except (KeyboardInterrupt, SystemExit, EOFError):
                logger.info('aborted by user')
                break
            except Exception as exc:
                logger.critical(f'an error occurred while running http server: {exc}')
                logger.exception('detailed error trace:\n' + format_exc())
                logger.info('continuing job')

        # if dad-process was killed, all the children will be also killed
        # otherwise, only current child will die
        self.stop()

    def stop(self):
        if self._i_am_dad_process():
            on_shutdown_event_callback = self.server_events_callbacks['on-shutdown']

            if on_shutdown_event_callback is not None:
                on_shutdown_event_callback()

            if self.forks:
                logger.info('killing server forks')

            for child in self.forks:
                os.kill(child, SIGKILL)
                logger.debug('killed child: ' + str(child))

            logger.info('web-server has been stopped. Good bye')
            os.abort()

    def __del__(self):
        self.stop()
