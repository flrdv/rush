import os
import socket
import logging
import asyncio
import platform
import multiprocessing
from traceback import format_exc
from dataclasses import dataclass, field
from typing import List, Type, Union, Optional

from .utils import sockutils
from .server.base import HTTPServer
from .utils.termutils import is_windows
from .entities import CaseInsensitiveDict
from .dispatcher.base import BaseDispatcher
from .server.aiohttpserver import AioHTTPServer
from .storage import (base as storage_base,
                      fd_sendfile as storage_fd_sendfile)


try:
    from signal import SIGKILL
except ImportError:
    from signal import CTRL_C_EVENT as SIGKILL

logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
)


@dataclass
class Settings:
    host: str = field(default='127.0.0.1')
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

    logger: logging.Logger = field(default_factory=logging.getLogger)

    storage: Type[storage_base.Storage] = field(default=storage_fd_sendfile.SimpleDevStorage)
    httpserver: Type[HTTPServer] = field(default=AioHTTPServer)

    asyncio_logging: bool = field(default=True)
    asyncio_logging_level: int = field(default=logging.DEBUG)


class WebServer:
    def __init__(self,
                 settings: Settings = Settings(),
                 ):
        self.logger = settings.logger
        asyncio_logger = logging.getLogger('asyncio')
        asyncio_logger.disabled = not settings.asyncio_logging
        asyncio_logger.setLevel(settings.asyncio_logging_level)

        self.settings = settings

        # if children is None, current process isn't parent
        # only parent process has a list of children
        self._children: Optional[List[int]] = []

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

        children_count = self._get_children_count(self.settings.processes)

        if children_count != self.settings.processes:
            self.logger.info(f'setting processes count to {children_count}')

        self.logger.debug(f'forking {children_count} times')
        self._children = self._do_forks(n=children_count)

        if self._children is not None:
            self.logger.info('children has been spawned')

        self._server_worker(dp)

    def _get_children_count(self, raw_count: Optional[int]) -> int:
        """
        Returns a count of children has to be spawned

        Returns 0 if Windows (as reuseport isn't available under windows)
        Returns raw_count if raw_count is bigger than 1
        Returns 0 if raw_count is 1
        Returns multiprocessing.cpu_count() - 1 if raw_count is None or <0
        """

        if is_windows():
            if raw_count not in (0, 1):
                self.logger.info('running under windows: reuseport is '
                                 'not available; disabling forks')
            return 0

        if raw_count is None or raw_count < 0:
            return multiprocessing.cpu_count() - 1

        return raw_count - 1 if raw_count > 0 else 0

    def _do_forks(self, n: int) -> Optional[List[int]]:
        spawned_children = []

        for child_num in range(n - 1):
            child_pid = os.fork()

            if child_pid != 0:
                spawned_children.append(child_pid)
                self.logger.debug(f'started child process id={child_num} pid={child_pid}')
            else:
                return

        return spawned_children

    def _server_worker(self, dp: BaseDispatcher):
        """
        Finally, we're in our brand-new process that belongs only to us, hohoho
        """

        self.logger.disabled = not self._is_parent()

        sock = socket.socket()

        if not is_windows():
            # as I said before, windows does not support reuseport
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

            if self._is_parent():
                self.logger.critical('the problem was caused in parent process, shutting down'
                                     'the server')
                self._kill_children()

            sock.close()
            raise SystemExit(1)

        if self._is_parent():
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
                if self._is_parent():
                    self.logger.info('shutting down (aborted by user)...')
                    self._kill_children()
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
                                    'https://github.com/floordiv/rush/issues with detailed '
                                    'description of the case, web-server version, traceback, '
                                    'environment, and, if it\'s possible, a sample of code to '
                                    'reproduce an error')
                self.logger.info('continuing the job')

    def _is_parent(self) -> bool:
        """
        Returns True or False, depending on fact whether we're in parent process
        or not. Mainly used for internal purposes, but also can be used by user
        for some reason (really idk for what user should use this)
        """

        return self._children is not None

    def _kill_children(self):
        if self._is_parent():
            self.logger.debug('killing children...')

            for child in self._children:
                try:
                    os.kill(child, SIGKILL)
                except SystemError as syserr:
                    self.logger.warning(f'failed to kill children pid={child}: {syserr}')

            self._children.clear()
            self.logger.info('killed all the children')

    def stop(self):
        """
        Here should be implemented calling some events callbacks
        or something like that
        Currently the only thing we need is just killing all the children

        Maybe, also should be good to close server here, but it should be closed
        by itself because there is no way to implement this without using
        shit code
        """

        self._kill_children()

    def __del__(self):
        self.stop()
