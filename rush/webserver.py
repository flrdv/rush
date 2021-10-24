import os
import socket
import logging
import asyncio
import multiprocessing
from signal import SIGKILL
from traceback import format_exc
from dataclasses import dataclass
from typing import List, Dict, Type, Union

from .utils import sockutils
from .typehints import Coroutine
from .sfs import base as sfs_base, fd_sendfile as sfs_fd_sendfile
from . import entities, exceptions
from .server.base import HTTPServer
from .dispatcher.base import Dispatcher
from .server.aiohttpserver import AioHTTPServer


@dataclass
class Settings:
    host: str = '0.0.0.0'
    port: int = 9090
    max_bind_retries: Union[int, None] = None
    bind_retries_timeout: Union[int, float] = 3
    max_connections: Union[int, None] = 1024
    processes: Union[int, None] = None

    logging_level: int = logging.DEBUG
    logging_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    logs_dir = 'logs'
    logs_file = 'webserver.log'

    sfs: Type[sfs_base.SFS] = sfs_fd_sendfile.SimpleDevSFS
    httpserver: Type[HTTPServer] = AioHTTPServer

    asyncio_logging: bool = True
    asyncio_logging_level: int = logging.DEBUG


class WebServer:
    def __init__(self,
                 settings: Settings = Settings(),
                 ):
        if not os.path.exists(settings.logs_dir):
            os.mkdir(settings.logs_dir)

        logs_file_path = os.path.join(
            settings.logs_dir, settings.logs_file
        )

        logging.basicConfig(
            level=settings.logging_level,
            format=settings.logging_format,
            handlers=[
                logging.FileHandler(logs_file_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger()
        self.logger.info(f'writing logs to {logs_file_path}')

        asyncio_logger = logging.getLogger('asyncio')
        asyncio_logger.disabled = not settings.asyncio_logging
        asyncio_logger.setLevel(settings.asyncio_logging_level)

        self.settings = settings

        self.children: List[int] = []
        self.parent_pid: int = os.getpid()

        self.http_errors_handlers: Dict[Type[exceptions.HTTPError], Coroutine] = {}

    def run(self, dp: Dispatcher):
        """
        This function is called once when user starts the server.
        Everything it does - just checks whether dispatcher
        was inherited from base class, and setting forks count
        if not specified. Then it just creates n-1 processes with
        web-server workers and running the n one
        """

        if not isinstance(dp, Dispatcher):
            raise TypeError(f'{dp} object must be inherited from '
                            'rush.dispatcher.base.Dispatcher object!')

        if self.settings.processes is None:
            # if processes count is set to None, set the number
            # to processor logical cores count
            logical_cores = multiprocessing.cpu_count()
            self.logger.info(f'setting processes count to {logical_cores}')
            self.settings.processes = logical_cores

        self.logger.debug(f'forking {self.settings.processes} times')

        for child_num in range(self.settings.processes - 1):
            child_pid = os.fork()

            if child_pid != 0:
                self.children.append(child_pid)
                self.logger.debug(f'started child process id={child_num} pid={child_pid}')
            else:
                break

        if self.is_parent():
            self.logger.info('children has been spawned')

        self._server_worker(dp)

    def _server_worker(self, dp: Dispatcher):
        """
        Finally, we're in our brand-new process that belongs only to us, hohoho
        """

        self.logger.disabled = not self.is_parent()

        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
        self.logger.debug(f'trying to bind on {self.settings.host}:{self.settings.port}...')

        succeeded, retries_went = sockutils.bind_sock(
            sock=sock,
            addr=(self.settings.host, self.settings.port),
            max_retries=self.settings.max_bind_retries or 99999,
            retries_timeout=self.settings.bind_retries_timeout
        )

        if not succeeded:
            bind_retries = self.settings.max_bind_retries
            retries_timeout = self.settings.bind_retries_timeout
            self.logger.error(f'failed to bind server on {self.settings.host}:{self.settings.port}:'
                              f'max retries exceeded (retries={bind_retries}, '
                              f'retries_timeout={retries_timeout}, '
                              f'time_elapsed={round(bind_retries * retries_timeout, 2)}secs)')

            if self.is_parent():
                self.logger.critical('the problem was caused in parent process, shutting down'
                                     'the server')
                self.kill_children()

            sock.close()

            raise SystemExit(1)

        if self.is_parent():
            self.logger.info(f'successfully bound socket on {self.settings.host}:{self.settings.port}')
            self.logger.info('press CTRL-C to stop the server')

        http_server = self.settings.httpserver(
            sock,
            self.settings.max_connections,
            dp.process_request,
            self.settings.sfs()
        )

        while True:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(http_server.poll())
            except (KeyboardInterrupt, SystemExit, EOFError):
                if self.is_parent():
                    self.logger.info('shutting down (aborted by user)...')
                    self.kill_children()
                    http_server.stop()

                    break
                else:
                    self.logger.info(f'child pid={os.getpid()} received KeyboardInterrupt; '
                                     f'continuing the job, server can be stopped only from '
                                     f'parent process')
            except Exception as exc:
                self.logger.exception(f'an error occurred while running http server: {exc}\n'
                                      f'Detailed trace:\n{format_exc()}')
                self.logger.warning('most of all, this is a bug; please, open an issue on '
                                    'https://github.com/floordiv/rush/issues with detailed description '
                                    'of the case, environment, and, if possible, a sample of code to '
                                    'reproduce an error')
                self.logger.info('continuing the job')

    def is_parent(self) -> bool:
        """
        Returns True or False, depending on fact whether we're in parent process
        or not. Mainly used for internal purposes, but also can be used by user
        for some reason (really idk for what user should use this)
        """

        return os.getpid() == self.parent_pid

    def kill_children(self):
        if self.is_parent():
            self.logger.debug('killing children...')

            for child in self.children:
                os.kill(child, SIGKILL)

            self.children.clear()
            self.logger.info('killed all the children')

    def stop(self):
        """
        Here should be implemented calling some events callbacks
        or something like that
        and killing children
        """
        self.kill_children()

    def __del__(self):
        self.stop()
