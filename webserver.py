from socket import socket
import logging as _logging
from psutil import cpu_count
from typing import List, Dict
from traceback import format_exc
from multiprocessing import Process

import core.server
import core.entities
import core.utils.loader
import core.process_workers
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
                 process_workers=None, loader_impl=None, cache_impl=None,
                 sources_root='localfiles', logging=True):
        logger.disabled = logging
        self.addr = (ip, port)

        if process_workers is None:
            # logical=True: processor threads
            # logical=False: processor cores
            process_workers = cpu_count(logical=True)

        self.process_workers_count = process_workers

        if max_conns is None:
            max_conns = core.utils.termutils.get_max_descriptors()

        sock = socket()
        core.utils.sockutils.bind_sock(sock, self.addr)

        self.http_server = core.server.HttpServer(sock, max_conns)

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

    def route(self, path, methods=None, filter_=None):
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

        logger.info(f'starting {self.process_workers_count} process workers')

        for _ in range(self.process_workers_count):
            process = Process(target=core.process_workers.process_worker, args=(self.http_server,
                                                                                self.loader,
                                                                                self.handlers,
                                                                                self.err_handlers,
                                                                                self.redirects))
            self.process_workers.append(process)
            process.start()
            logger.debug(f'started process worker ident:{process.ident} with pid {process.pid}')

        ip, port = self.addr
        logger.info(f'* running http server on {ip}:{port}')

        try:
            self.http_server.start()
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.info('aborted by user')
        except Exception as exc:
            logger.error(f'an error occurred while running http server: {exc} (see detailed trace below)')
            logger.exception(format_exc())

        self.stop()

    def stop(self):
        on_shutdown_event_callback = self.server_events_callbacks['on-shutdown']

        if on_shutdown_event_callback is not None:
            logger.debug('found on-shutdown server event callback')
            on_shutdown_event_callback()

        logger.info('stopping web-server...')
        logger.info('terminating process workers')

        for process in self.process_workers:
            logger.debug(f'terminating process ident:{process.ident} with pid {process.pid}')
            process.terminate()

        logger.info('process workers has been terminated. Good bye')

    def __del__(self):
        self.stop()
