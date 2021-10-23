from asyncio import iscoroutinefunction
from typing import (Dict, Any, Callable, Awaitable, Union, Iterable)

from .. import exceptions
from .base import Dispatcher
from ..entities import Request
from ..utils.httpmethods import ALL_METHODS
from ..typehints import RoutePath, Coroutine
from ..utils.stringutils import make_sure_bytes_or_none


class Handler:
    """
    A class that describes handler. Keeps it routing path,
    methods, etc.
    """

    def __init__(self,
                 handler: Callable[[Request], Awaitable],
                 path: RoutePath,
                 methods: Iterable[bytes],
                 any_path: bool
                 ):
        self.handler = handler
        self.path = path
        self.methods = methods
        self.any_path = any_path


class Route:
    """
    Mainly class for cases when you need to add routes without using
    decorators, but using dp.add_routes([...])
    """

    def __init__(self,
                 handler: Coroutine,
                 path: RoutePath,
                 method_or_methods: Union[str, bytes, Iterable] = ALL_METHODS
                 ):
        self.handler = handler
        self.path = path

        if not isinstance(method_or_methods, Iterable):
            method_or_methods = {method_or_methods}

        self.methods = method_or_methods


class SimpleAsyncDispatcher(Dispatcher):
    def __init__(self):
        self.usual_handlers: Dict[bytes, Handler] = {}
        self.any_paths_handlers: Dict[Any[ALL_METHODS], Handler] = {
            method: None for method in ALL_METHODS
        }

    async def process_request(self,
                              request: Request
                              ) -> None:
        if await request.path() not in self.usual_handlers:
            handler = self.any_paths_handlers[request.method]

            if handler is None:
                raise exceptions.HTTPNotFound(request)
        else:
            handler = self.usual_handlers[await request.path()]

        await handler.handler(request)
        request.wipe()

    def route(self,
              path: RoutePath,
              method: Union[str, bytes, None] = None,
              methods: Iterable[bytes] = ALL_METHODS
              ):

        if method is not None:
            methods = {make_sure_bytes_or_none(method.upper())}

        def deco(coro: Callable[[Request], Awaitable]):
            if not methods:
                raise exceptions.NoMethodsProvided(str(coro))

            if not iscoroutinefunction(coro):
                raise exceptions.HandlerMustBeCoroutineError(str(coro))

            self._put_handler(Handler(
                handler=coro,
                path=make_sure_bytes_or_none(path),
                methods=set(methods),
                any_path=path is None
            ))

            return coro

        return deco

    def get(self,
            path: RoutePath):
        return self.route(path, 'GET')

    def post(self, path: RoutePath):
        return self.route(path, 'POST')

    def head(self, path: RoutePath):
        return self.route(path, 'HEAD')

    def put(self, path: RoutePath):
        return self.route(path, 'PUT')

    def trace(self, path: RoutePath):
        return self.route(path, 'TRACE')

    def connect(self, path: RoutePath):
        return self.route(path, 'CONNECT')

    def delete(self, path: RoutePath):
        return self.route(path, 'DELETE')

    def options(self, path: RoutePath):
        return self.route(path, 'OPTIONS')

    def patch(self, path: RoutePath):
        return self.route(path, 'PATCH')

    def add_routes(self, routes: Iterable[Route]):
        for route in routes:
            self.add_route(route)

    def add_route(self, route: Route):
        self._put_handler(Handler(
            handler=route.handler,
            path=route.path,
            methods=route.methods,
            any_path=route.path is None
        ))

    def _put_handler(self, handler: Handler) -> None:
        if handler.any_path:
            self._add_any_path_handler(handler)
        else:
            self.usual_handlers[handler.path] = handler

    def _add_any_path_handler(self, handler: Handler) -> None:
        assert handler.any_path, TypeError('expected any path handler, got usual handler instead')

        for method in handler.methods:
            self.any_paths_handlers[method] = handler
