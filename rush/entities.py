import asyncio
from asyncio import Future
from typing import Union, Any, Dict, List, Callable, Awaitable, Optional

from . import sfs
from .utils.status_codes import status_codes
from .utils.httputils import render_http_response, parse_params
from .typehints import (HttpResponseCallback, Connection)


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
                 cache: sfs.base.SFS):
        self.http_callback = http_callback
        self.cache = cache

        # not using Union cause every object's fields after initializing
        # ALWAYS will be refilled, but also I'd like to have proper
        # typehints
        self._method: Future = Future()
        self._awaited_method: Optional[bytes] = None
        self._path: Future = Future()
        self._awaited_path: Optional[bytes] = None
        self._fragment: Future = Future()
        self._awaited_fragment: Optional[bytes] = None
        self._raw_parameters: Future = Future()
        self._awaited_raw_parameters: Optional[bytes] = None
        self._parsed_parameters: Optional[Dict[str, List[str]]] = None
        self._protocol: Future = Future()
        self._awaited_protocol: Optional[bytes] = None

        self._headers: CaseInsensitiveDict = CaseInsensitiveDict()
        self._body: Future = Future()
        self._awaited_body: Optional[bytes] = None

        self.socket: Optional[Connection] = None
        self._on_chunk: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    def wipe(self):
        """
        A method that clears path, body and headers attributes
        The purpose of this function is not to let already processed
        requests live longer than it should, cause this is potential
        DoS vulnerability. Also clearing path as it can be up to 65535
        bytes length, not a lot, but also can be a trouble
        """

        self._method.__init__()
        self._awaited_method = None
        self._path.__init__()
        self._awaited_path = None
        self._fragment.__init__()
        self._awaited_fragment = None
        self._raw_parameters.__init__()
        self._awaited_raw_parameters = None
        self._parsed_parameters = None
        self._protocol.__init__()
        self._awaited_protocol = None
        self._headers.clear()
        self._body.__init__()
        self._awaited_body = None

    def on_chunk(self, handler: Union[Callable[[bytes], Callable],
                                      Callable[[bytes], Awaitable]]) -> None:
        """
        on_chunk can receive as usual callable, as coroutines. But
        in case of getting usual callable, we make a coroutine
        from it, that is actually not async, but able to be ran
        in event loop
        """

        self._on_chunk = handler  # make_sure_async(handler)

    def on_complete(self, handler: Union[Callable[[bytes], Callable],
                                         Callable[[bytes], Awaitable]]) -> None:
        """
        Same as on_chunk
        """

        self._on_complete = handler  # make_sure_async(handler)

    def get_on_chunk(self) -> Callable[[bytes], Awaitable]:
        return self._on_chunk

    def get_on_complete(self) -> Callable[[], Awaitable]:
        return self._on_complete

    async def method(self):
        if self._awaited_method:
            return self._awaited_method

        return await self._method.result()

    async def protocol(self):
        if self._awaited_protocol:
            return self._awaited_protocol

        return await self._protocol.result()

    async def path(self):
        if self._awaited_path:
            return self._awaited_path

        return await self._path.result()

    def headers(self):
        return self._headers

    async def body(self):
        if self._awaited_body:
            return self._awaited_body

        return await self._body.result()

    def set_method(self, method: bytes):
        self._method.set_result(method)

    def set_protocol(self, protocol: str):
        self._protocol.set_result(protocol)

    def set_path(self, path: bytes):
        self._path.set_result(path)

    def set_header(self, header: str, value: str) -> None:
        self._headers[header] = value

    def set_body(self, body: bytes):
        self._body.set_result(body)

    async def response(self,
                       code: int = 200,
                       status: Union[str, bytes, None] = None,
                       body: Union[str, bytes] = b'',
                       headers: Union[dict, 'CaseInsensitiveDict', None] = None
                       ) -> None:
        self.http_callback(
            render_http_response(
                await self.protocol(),
                code,
                status or status_codes[code],
                self.headers if not headers else {**self.headers, **headers},
                body
            )
        )

    async def params(self) -> Dict[str, List[str]]:
        """
        Returns a dict with URI parameters, where keys are bytes
        and values are lists with bytes. This may be not convenient
        for user, but this behaviour matches RFC

        Also, it isn't parsing anything until user will need it.
        If user never called Request.params(), they also never will
        be parsed

        If no parameters provided, empty dictionary will be returned
        """

        if self._parsed_parameters:
            return self._parsed_parameters

        raw_params = self._awaited_raw_parameters \
            if self._awaited_raw_parameters \
            else await self._raw_parameters

        if not raw_params:
            return {}

        self._parsed_parameters = parse_params(raw_params)

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
