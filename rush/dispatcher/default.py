from functools import reduce
from asyncio import iscoroutinefunction
from typing import (Dict, Callable, Awaitable, Union, Iterable, List, Optional)

from .. import exceptions
from .base import BaseDispatcher
from ..entities import Request, Response
from ..middlewares.base import BaseMiddleware
from ..utils.stringutils import make_sure_bytes_or_none
from ..typehints import RoutePath, AsyncFunction, HTTPMethod
from ..utils.httputils import HTTP_METHODS, render_http_response


class Handler:
    """
    A class that describes handler. Keeps it routing path,
    methods, etc.
    """

    def __init__(self,
                 handler: Callable[[Request, Response], Awaitable],
                 path: RoutePath,
                 methods: Iterable[bytes],
                 any_path: bool,
                 middlewares: List[BaseMiddleware]
                 ):
        self.handler = handler
        self.path = path
        self.methods = methods
        self.any_path = any_path
        self.middlewares = middlewares or []

    def get_performed_middleware(self,
                                 request: Request,
                                 response: Response) -> Awaitable:
        return reduce(
            lambda prev, next_: next_.process(prev, request),
            # all the middlewares `process()` method requires handler
            # but endpoint handler doesn't. So we just put endpoint handler
            # as the first element in the list of middlewares so we don't need
            # to pass any arguments to it. Ez solution, but ugly for linters
            [self.handler(request, response)] + self.middlewares  # noqa
        )


class Route:
    """
    Mainly class for cases when you need to add routes without using
    decorators, but using dp.add_routes([...])
    """

    def __init__(self,
                 handler: AsyncFunction,
                 path: RoutePath,
                 method_or_methods: Union[str, bytes, Iterable] = HTTP_METHODS,
                 middlewares: Optional[List[BaseMiddleware]] = None
                 ):
        self.handler = handler
        self.path = path if isinstance(path, bytes) else path.encode()

        if not isinstance(method_or_methods, Iterable):
            method_or_methods = {method_or_methods}

        self.methods = method_or_methods
        self.middlewares = middlewares or []


class AsyncDispatcher(BaseDispatcher):
    def __init__(self):
        self.usual_handlers: Dict[bytes, Handler] = {}
        self.any_paths_handlers: Dict[HTTPMethod, Handler] = {
            method: None for method in HTTP_METHODS
        }

    async def process_request(self,
                              request: Request,
                              response: Response,
                              http_send: Callable[[bytes], None]
                              ) -> None:
        if request.path not in self.usual_handlers:
            handler = self.any_paths_handlers[request.method]

            if handler is None:
                raise exceptions.HTTPNotFound(request, msg='no-registered-routers')
        else:
            handler = self.usual_handlers[request.path]

        if handler.middlewares:
            result = await handler.get_performed_middleware(request, response)
        else:
            result = await handler.handler(request, response)

        http_send(
            render_http_response(
                protocol=b'1.1',
                code=result.code,
                status_code=result.status,
                headers=result.headers if result.headers is not None else result.default_headers,
                body=result.body,
                # TODO: this shouldn't be always True, will be updated after chunked transfer
                #       will be implemented
                count_content_length=True
            )
        )

        request.wipe()

    def route(self,
              path: RoutePath,
              method: Union[str, bytes, None] = None,
              methods: Iterable[HTTPMethod] = HTTP_METHODS,
              middlewares: Optional[List[BaseMiddleware]] = None
              ):

        if method is not None:
            methods = {make_sure_bytes_or_none(method.upper())}

        def deco(coro: Callable[[Request, Response], Awaitable]):
            if not methods:
                raise exceptions.NoMethodsProvided(str(coro))

            if not iscoroutinefunction(coro):
                raise exceptions.HandlerMustBeCoroutineError(str(coro))

            self._put_handler(Handler(
                handler=coro,
                path=make_sure_bytes_or_none(path),
                methods=set(methods),
                any_path=path is None,
                middlewares=middlewares or []
            ))

            return coro

        return deco

    def get(self, path: RoutePath):
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
            any_path=not route.path,
            middlewares=route.middlewares
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
