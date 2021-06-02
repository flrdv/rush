import logging
from typing import List
from socket import socket
from traceback import format_exc
from multiprocessing import cpu_count, Process

from core import server, handlers_manager, entities, utils

if not utils.termutils.is_linux():
    raise RuntimeError('Rush-webserver is only for linux. Ave Maria!')

logging.basicConfig(level=logging.DEBUG,  # noqa
                    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
                    handlers=[
                        logging.FileHandler("logs/handlers.log"),
                        logging.StreamHandler()]
                    )
logger = logging.getLogger(__name__)


class WebServer:
    def __init__(self, addr, max_conns=None, process_workers=None):
        if process_workers is None:
            process_workers = cpu_count()

        self.process_workers_count = process_workers

        if max_conns is None:
            max_conns = utils.termutils.get_max_descriptors()

        sock = socket()
        utils.sockutils.bind_sock(logger, sock, addr)

        self.http_server = server.HttpServer(sock, max_conns)

        self.handlers = []
        self.err_handlers = {
            'not-found': None,
            'internal-error': None
        }

        self.process_workers: List[Process] = []

    def route(self, path, methods=None, filter_=None):
        def decorator(func):
            self.handlers.append(entities.Handler(func=func,
                                                  filter_=filter_,
                                                  path_route=path,
                                                  methods=methods))

            return func

        return decorator

    def start(self):
        logger.info(f'starting {self.process_workers_count} process workers')

        for _ in range(self.process_workers_count):
            process = Process(target=handlers_manager.process_worker, args=(self.http_server,
                                                                            self.handlers,
                                                                            self.err_handlers))
            self.process_workers.append(process)
            process.start()
            logger.debug(f'started process worker {process.ident} with pid {process.pid}')

        logger.info('running http server')

        try:
            self.http_server.start()
        except (KeyboardInterrupt, SystemExit, EOFError):
            logger.info('aborted by user')
            self.stop()
        except Exception as exc:
            logger.error(f'an error occurred while running http server: {exc} (see detailed trace below)')
            logger.exception(format_exc())

    def stop(self):
        logger.info('stopping web-server...')
        logger.info('terminating process workers')

        for process in self.process_workers:
            logger.debug(f'terminating process {process.ident} with pid {process.pid}')
            process.terminate()

        logger.info('process workers has been terminated. Good bye')

    def __del__(self):
        self.stop()

