import asyncio
from asyncio import Future
from typing import Union, Any, Callable, Awaitable

from .cache import Cache
from utils.status_codes import status_codes
from utils.httputils import render_http_response
from .typehints import (HttpResponseCallback, URI, HTTPMethod,
                        HTTPVersion, Connection)


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


class Request:
    def __init__(self,
                 http_callback: HttpResponseCallback,
                 cache: Cache):
        self.http_callback = http_callback
        self.cache = cache

        # not using Union cause every object's fields after initializing
        # ALWAYS will be refilled, but also I'd like to have proper
        # typehints
        self.method: HTTPMethod = b''
        self.path: URI = b''
        self.protocol: HTTPVersion = ''

        self._headers_future: Union[Future, None] = None
        self._headers: Union[CaseInsensitiveDict, None] = None
        self._body_future: Union[Future, None] = None
        self._body: bytes = b''

        self.socket: Union[Connection, None] = None
        self._on_chunk: Union[Callable, None] = None
        self._on_complete: Union[Callable, None] = None

    def _build(self,
               method: HTTPMethod,
               path: URI,
               protocol: HTTPVersion,
               socket: Connection):
        self.method = method
        self.path = path
        self.protocol = protocol
        self._headers_future.__init__()
        self._headers = None
        self._body_future.__init__()
        self._body = None
        self.socket = socket

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

    def on_complete(self, handler: Union[Callable[[bytes], Callable],
                                         Callable[[bytes], Awaitable]]) -> None:
        """
        Same as on_chunk
        """

        self._on_complete = make_sure_async(handler)

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
                body if isinstance(body, bytes) else body.encode()
            )
        )


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
