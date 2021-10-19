import asyncio
import logging
from asyncio import Future
from dataclasses import dataclass
from typing import Union, Any, Dict, List, Callable, Awaitable, Type

from . import sfs, server
from .utils.status_codes import status_codes
from .server.httpserver import EpollHttpServer
from .utils.httputils import render_http_response, parse_params
from .typehints import (HttpResponseCallback, URI, HTTPMethod,
                        HTTPVersion, Connection, URIParameters,
                        URIFragment)


def make_async(func: Callable) -> Callable[[Any], Awaitable]:
    """
    A modern analogue for asyncio.coroutine(), that is unfortunately
    was deprecated
    """

    async def not_real_async() -> Any:
        return func()

    return not_real_async


def make_sure_async(func: Union[Callable[[Any], Callable],
                                Callable[[Any], Awaitable]]) -> Callable[[Any], Awaitable]:
    return \
        func if asyncio.iscoroutinefunction(func) \
        else make_async(func)


@dataclass
class Settings:
    host: str = '0.0.0.0'
    port: int = 9090
    max_bind_retries: Union[int, None] = None
    bind_retries_timeout: Union[int, float] = 3
    max_connections: Union[int, None] = None
    processes: Union[int, None] = None

    logging_level: int = logging.DEBUG
    logging_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    logs_dir = 'logs'
    logs_file = 'webserver.log'

    sfs: Type[sfs.base.SFS] = sfs.fd_sendfile.SimpleDevSFS
    httpserver = EpollHttpServer


class Request:
    def __init__(self,
                 http_callback: HttpResponseCallback,
                 cache: sfs.base.SFS):
        self.http_callback = http_callback
        self.cache = cache

        # not using Union cause every object's fields after initializing
        # ALWAYS will be refilled, but also I'd like to have proper
        # typehints
        self.method: HTTPMethod = b''
        self.path: URI = b''
        self.fragment: URIFragment = b''
        self.raw_parameters: URIParameters = b''
        self._parsed_parameters: Union[Dict[bytes, List[bytes]], None] = None
        self.protocol: HTTPVersion = ''

        self._headers_future: Union[Future, None] = None
        self._headers: Union[CaseInsensitiveDict, None] = None
        self._body_future: Union[Future, None] = None
        self._body: bytes = b''

        self.socket: Union[Connection, None] = None
        self._on_chunk: Union[Callable, None] = None
        self._on_complete: Union[Callable, None] = None

    def reinit(self,
               method: HTTPMethod,
               path: URI,
               parameters: URIParameters,
               fragment: URIFragment,
               protocol: HTTPVersion,
               socket: Connection):
        self.method = method.upper()
        self.path = path
        self.raw_parameters = parameters
        self.fragment = fragment
        self.protocol = protocol
        self._headers_future.__init__()
        self._headers = None
        self._body_future.__init__()
        self._body = None
        self.socket = socket

    def wipe(self):
        """
        A method that clears path, body and headers attributes
        The purpose of this function is not to let already processed
        requests live longer than it should, cause this is potential
        DoS vulnerability. Also clearing path as it can be up to 65535
        bytes length, not a lot, but also can be a trouble
        """

        self._body = b''
        self._headers = None
        self.path = b''

    def set_headers(self, headers: 'CaseInsensitiveDict') -> None:
        self._headers_future.set_result(headers)

    def set_body(self, body: bytes) -> None:
        self._body_future.set_result(body)

    async def headers(self) -> 'CaseInsensitiveDict':
        if self._headers:
            return self._headers

        self._headers = await self._headers_future.result()

        return self._headers

    async def body(self) -> bytes:
        if self._body:
            return self._body

        self._body = await self._body_future.result()

        return self._body

    def on_chunk(self, handler: Union[Callable[[bytes], Callable],
                                      Callable[[bytes], Awaitable]]) -> None:
        """
        on_chunk can receive as usual callable, as coroutines. But
        in case of getting usual callable, we make a coroutine
        from it, that is actually not async, but able to be ran
        in event loop
        """

        self._on_chunk = make_sure_async(handler)

    def get_on_chunk(self) -> Callable[[bytes], Awaitable]:
        return self._on_chunk

    def on_complete(self, handler: Union[Callable[[bytes], Callable],
                                         Callable[[bytes], Awaitable]]) -> None:
        """
        Same as on_chunk
        """

        self._on_complete = make_sure_async(handler)

    def get_on_complete(self) -> Callable[[], Awaitable]:
        return self._on_complete

    async def response(self,
                       code: int = 200,
                       status: Union[str, bytes, None] = None,
                       body: Union[str, bytes] = b'',
                       headers: Union[dict, 'CaseInsensitiveDict', None] = None) -> None:
        self.http_callback(
            render_http_response(
                self.protocol,
                code,
                status or status_codes[code],
                await self.headers() if not headers else (await self.headers()).update(headers),
                body
            )
        )

    def params(self) -> Dict[bytes, List[bytes]]:
        """
        Returns a dict with URI parameters, where keys are bytes
        and values are lists with bytes. This may be not convenient
        for user, but this behaviour matches RFC

        Also, it isn't parsing anything until user will need it.
        If user never called Request.params(), they also never will
        be parsed

        If no parameters provided, empty dictionary will be returned
        """

        if not self.raw_parameters:
            return {}

        if self._parsed_parameters is None:
            self._parsed_parameters = parse_params(self.raw_parameters)

        return self._parsed_parameters


class ObjectPool:
    def __init__(self,
                 object_entity,
                 pool_size: int = 1000,
                 object_initializer: Union[Callable, None] = None):
        self.object = object_entity
        self.size = pool_size
        self.initializer = object_initializer

        self.pool: list = []

    def new_object(self) -> object:
        if self.initializer:
            return self.initializer(self.object)

        return self.object()

    def pop(self) -> object:
        if not self.pool:
            return self.new_object()

        return self.pool.pop()

    def push(self, obj) -> None:
        if len(self.pool) >= self.size:
            return

        self.pool.append(obj)


class CaseInsensitiveDict(dict):
    """
    A class that works absolutely like usual dict, but keys are case-insensitive
    Do not try to make him work with anything that is not bytes or a string!
    """

    def __init__(self, *args, **kwargs):
        # it's really faster to call super() once
        # and get it from self, than call it every time
        self.__parent = super()
        super().__init__(*args, **kwargs)

    def __getitem__(self, item: Union[str, bytes]) -> Any:
        return self.__parent.__getitem__(item.lower())

    def __setitem__(self, key: Union[str, bytes], value: Any) -> None:
        self.__parent.__setitem__(key.lower(), value)

    def __contains__(self, item: Union[str, bytes]) -> bool:
        return self.__parent.__contains__(item.lower())

    def get(self, item: Union[str, bytes], instead: Any = None) -> Any:
        return self.__parent.get(item.lower(), instead)

    def pop(self, key: Union[str, bytes]) -> Any:
        return self.__parent.pop(key.lower())

    def setdefault(self, key: Union[str, bytes], default: Any = None) -> Any:
        return self.__parent.setdefault(key.lower(), default)
