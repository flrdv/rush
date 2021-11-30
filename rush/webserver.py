import os
import socket
import logging
import asyncio
import multiprocessing
from signal import SIGKILL
from traceback import format_exc
from dataclasses import dataclass, field
from typing import List, Dict, Type, Union, Optional

from . import exceptions
from .utils import sockutils
from .server.base import HTTPServer
from .typehints import AsyncFunction
from .entities import CaseInsensitiveDict
from .dispatcher.base import BaseDispatcher
from .server.aiohttpserver import AioHTTPServer
from .storage import (base as storage_base,
                      fd_sendfile as storage_fd_sendfile)


@dataclass
class Settings:
    host: str = field(default='0.0.0.0')
    port: int = field(default=9090)
    max_bind_retries: Optional[int] = field(default=None)
    bind_retries_timeout: Union[int, float] = field(default=3)
    max_connections: Optional[int] = field(default=1024)
    processes: Optional[int] = field(default=None)

    default_headers: CaseInsensitiveDict = field(
        default_factory=lambda: CaseInsensitiveDict(
            server='rush',
            connection='keep-alive'
        )
    )

    logging_level: int = field(default=logging.DEBUG)
    logging_format: str = field(default='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
    logs_dir: str = field(default='logs')
    logs_file: str = field(default='webserver.log')

    storage: Type[storage_base.Storage] = field(default=storage_fd_sendfile.SimpleDevStorage)
    httpserver: Type[HTTPServer] = field(default=AioHTTPServer)

    asyncio_logging: bool = field(default=True)
    asyncio_logging_level: int = field(default=logging.DEBUG)


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

        self.http_errors_handlers: Dict[Type[exceptions.HTTPError], AsyncFunction] = {}

    def run(self, dp: BaseDispatcher):
        """
        This function is called once when user starts the server.
        Everything it does - just checks whether dispatcher
        was inherited from base class, and setting forks count
        if not specified. Then it just creates n-1 processes with
        web-server workers and running the n one
        """

        if not isinstance(dp, BaseDispatcher):
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

    def _server_worker(self, dp: BaseDispatcher):
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
            self.settings.storage(),
            self.settings.default_headers
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
