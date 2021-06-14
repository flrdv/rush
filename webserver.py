import socket
import logging as _logging
from signal import SIGKILL
from os import abort, kill, fork, getpid

from psutil import cpu_count
from typing import List, Dict
from traceback import format_exc
from multiprocessing import Process

import core.httpserver
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
                 sources_root='localfiles', logging=True,
                 processes=0):
        logger.disabled = not logging

        if processes is None:
            processes = cpu_count()

        self.processes = processes
        self.forks = []

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

        self.addr = (ip, port)
        self.max_conns = max_conns

        if max_conns is None:
            self.max_conns = core.utils.termutils.get_max_descriptors()

        self.dad = getpid()

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

    def _i_am_dad_process(self):
        return self.dad == getpid()

    def start(self):
        on_startup_event_callback = self.server_events_callbacks['on-startup']

        if on_startup_event_callback is not None:
            logger.debug('found on-startup server event callback')
            on_startup_event_callback(self.loader)

        ip, port = self.addr
        logger.info(f'set max connections: {self.max_conns}')
        logger.info(f'set server processes count: {self.processes}')
        logger.debug(f'dad pid: {self.dad}')

        for fork_index in range(self.processes):
            if self._i_am_dad_process():
                if (child_fork := fork()) != 0:
                    self.forks.append(child_fork)
                    logger.debug(f'fork #{fork_index} with pid {child_fork}')

        try:
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
            succeeded = core.utils.sockutils.bind_sock(sock, self.addr,
                                                       disable_logs=not self._i_am_dad_process())

            if not succeeded:
                logger.error('failed to bind server: retries limit exceeded')
                return
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.error('failed to bind server: aborted by user')
            return

        if self._i_am_dad_process():
            logger.info(f'running http server on {ip}:{port}')

        http_server = core.httpserver.HttpServer(sock, self.max_conns)
        handlers_manager = core.handlers.HandlersManager(http_server, self.loader,
                                                         self.handlers, self.err_handlers,
                                                         self.redirects)
        http_server.on_message_complete_callback = handlers_manager.call_handler

        try:
            http_server.run()
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.info('aborted by user')
        except Exception as exc:
            logger.error(f'an error occurred while running http server: {exc} (see detailed trace '
                         'below)')
            logger.exception(format_exc())

        # if dad-process was killed, all the children will be also killed
        # otherwise, only current child will die
        self.stop()

    def stop(self):
        if getpid() == self.dad:
            on_shutdown_event_callback = self.server_events_callbacks['on-shutdown']

            if on_shutdown_event_callback is not None:
                logger.debug('found on-shutdown server event callback')
                on_shutdown_event_callback()

            if self.forks:
                logger.info('killing server forks')

            for child in self.forks:
                kill(child, SIGKILL)
                logger.debug('killed child: ' + str(child))

            logger.info('web-server has been stopped. Good bye')
            abort()

    def __del__(self):
        self.stop()
