import asyncio
from typing import Union, Any, Dict, List, Callable, Awaitable, Optional

from . import storage
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

    def update(self, other, **kwargs):
        self.__parent.update(
            {key.lower(): value for key, value in other.items()},
            **kwargs
        )


class ContextDict(dict):
    """
    Context dict is just an abstraction to allow usage of dict without
    explicit __getitem__ and __setitem__. It means you can get (and set)
    values just by typing like:
        >>> ctx_dict = ContextDict()
        >>> ctx_dict.variable = 'some value'
        >>> ctx_dict.variable
        'some value'

    Thanks to t.me/entressi for this snippet (the fastest solution I got from him)
    """

    def __init__(self, *args, **kwargs):
        super(ContextDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class Request:
    # Purpose of context in request is only for exchanging some data between
    # middlewares and handlers without a lot of shitcode like django does
    # Values from this context are changing only in handlers or middlewares
    ctx: ContextDict = ContextDict()

    def __init__(self,
                 http_callback: HttpResponseCallback,
                 cache: storage.base.Storage):
        self.http_callback = http_callback
        self.cache = cache

        # not using Union cause every object's fields after initializing
        # ALWAYS will be refilled, but also I'd like to have proper
        # typehints
        self.method: Optional[bytes] = None
        self.path: Optional[bytes] = None
        self.fragment: Optional[bytes] = None
        self.raw_parameters: Optional[bytes] = None
        self.parsed_parameters: Optional[Dict[str, List[str]]] = None
        self.protocol: Optional[str] = None
        self.headers = None
        self.body: bytes = b''

        self.socket: Optional[Connection] = None
        self._on_chunk: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    async def wipe(self):
        """
        A method that clears path, body and headers attributes
        The purpose of this function is not to let already processed
        requests live longer than it should, cause this is potential
        DoS vulnerability. Also clearing path as it can be up to 65535
        bytes length, not a lot, but also can be a trouble
        """

        self.path = None
        self.fragment = None
        self.raw_parameters = None
        self.parsed_parameters: Optional[Dict[str, List[str]]] = None
        self.headers.clear()
        self.body = b''
        self.ctx.clear()

        self._on_chunk = None
        self._on_complete = None

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

    def get_on_chunk(self) -> Callable[[bytes], Awaitable]:
        return self._on_chunk

    def get_on_complete(self) -> Callable[[], Awaitable]:
        return self._on_complete

    def set_http_callback(self, callback: Callable[[bytes], Callable]):
        self.http_callback = callback

    def raw_response(self,
                     data: bytes
                     ) -> None:
        self.http_callback(data)

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

        if not self.parsed_parameters:
            self.parsed_parameters = parse_params(self.raw_parameters)

        return self.parsed_parameters


class Response:
    """
    Response class is just a storage
    The actual response will happen after it will be returned
    """

    def __init__(self, default_headers: dict):
        self.default_headers = default_headers
        self.rendered_response: Optional[bytes] = None

    def __call__(self,
                 code: int = 200,
                 status: Optional[str] = None,
                 headers: Optional[dict] = None,
                 body: bytes = b''
                 ):
        self.rendered_response = render_http_response(
            protocol=b'1.1',
            code=code,
            status_code=status,
            headers=headers if headers is not None else self.default_headers,
            body=body,
            # TODO: add handling different chunked responses
            #       as they don't need specified content-length
            count_content_length=True,
        )
