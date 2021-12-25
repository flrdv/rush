import logging
import sys
import traceback
from functools import reduce
from asyncio import iscoroutinefunction
from typing import (Dict, Callable, Awaitable, Union, Type, Iterable, List, Optional)

from .. import exceptions
from .base import BaseDispatcher
from ..entities import Request, Response
from ..middlewares.base import BaseMiddleware
from ..utils.stringutils import make_sure_bytes_or_none
from ..utils.httputils import HTTP_METHODS, render_http_response
from ..typehints import RoutePath, AsyncFunction, HTTPMethod, Logger

ErrorHandler = Callable[[Request, Response, Exception], Awaitable[Response]]
PRE_RENDERED_INTERNAL_ERROR_RESPONSE = render_http_response(
    protocol=b'1.1',
    code=500,
    status_code=b'Internal Server Error',
    headers=b'content-type: text/html\r\ncontent-length: 33',
    body=b'<h1>500 Internal Server Error</h1>'
)
PRE_RENDERED_NOT_FOUND = render_http_response(
    protocol=b'1.1',
    code=404,
    status_code=b'Not Found',
    headers=b'content-type: text/html\r\ncontent-length: 22',
    body=b'<h1>404 Not Found</h1>'
)


def collapse_middlewares(middlewares: List[BaseMiddleware],
                         handler: Awaitable,
                         request: Request) -> Awaitable:
    """
    Takes a list of middlewares and a handler, and returns single coroutine
    that is just a chain of nested calls of next middleware (or handler in
    the end)
    """

    # TODO: benchmark, what is faster: given variant below,
    #       or making the last middleware already with handler,
    #       and collapse all them only after that
    return reduce(
        lambda prev, next_: next_.process(prev, request),
        # all the middlewares `process()` method requires handler
        # but endpoint handler doesn't. So we just put endpoint handler
        # as the first element in the list of middlewares so we don't need
        # to pass any arguments to it. Ez solution, but ugly for linters
        [handler] + middlewares  # noqa
    )


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
                 middlewares: List[BaseMiddleware]):
        self.handler = handler
        self.path = path
        self.methods = methods
        self.any_path = any_path
        self.middlewares = middlewares or []

    def get_wrapped_handler(self,
                            request: Request,
                            response: Response) -> Awaitable:
        return collapse_middlewares(
            middlewares=self.middlewares,
            handler=self.handler(request, response),
            request=request
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
                 middlewares: Optional[List[BaseMiddleware]] = None):
        self.handler = handler
        self.path = path if isinstance(path, bytes) else path.encode()

        if not isinstance(method_or_methods, Iterable):
            method_or_methods = {method_or_methods}

        self.methods = method_or_methods
        self.middlewares = middlewares or []


class AsyncDispatcher(BaseDispatcher):
    def __init__(self, logger: Logger = None):
        if logger is None:
            self.logger = logging.getLogger()
        else:
            self.logger = logger

        self.usual_handlers: Dict[bytes, Handler] = {}
        self.any_paths_handlers: Dict[HTTPMethod, Handler] = {
            method: None for method in HTTP_METHODS
        }

        # a dict with exceptions and handlers of the exceptions
        self.error_handlers: Dict[Type[Exception], ErrorHandler] = {}

        self.global_middlewares: List[BaseMiddleware] = []

    def on_begin_serving(self):
        """
        Implicitly insert global middlewares to the list of middlewares
        of all the handlers. Inserting to the beginning as it is tenable
        for global middlewares to be first who will process the request
        """

        for handler in self.usual_handlers.values():
            self._apply_middlewares(handler, self.global_middlewares)

        for handler in self.any_paths_handlers.values():
            if handler is not None:
                self._apply_middlewares(handler, self.global_middlewares)

    async def process_request(self,
                              request: Request,
                              response: Response,
                              http_send: Callable[[bytes], None]) -> None:
        if request.path not in self.usual_handlers:
            handler = self.any_paths_handlers[request.method]

            if handler is None:
                err_handler = self._get_error_handler(exceptions.HTTPNotFound)

                if err_handler is not None:
                    rendered_response = await self._run_exception_handler(
                        exc_handler=err_handler,
                        request=request,
                        response=response,
                        exception=exceptions.HTTPNotFound(
                            request,
                            msg='no handlers attached for the request'
                        )
                    )
                else:
                    rendered_response = PRE_RENDERED_INTERNAL_ERROR_RESPONSE
                    self.logger.warning(f'{request.path.decode()}: no handlers attached')

                http_send(rendered_response)
                return
        else:
            handler = self.usual_handlers[request.path]

        try:
            if handler.middlewares:
                result = await handler.get_wrapped_handler(request, response)
            else:
                result = await handler.handler(request, response)
        except Exception as exc:
            http_send(await self._handle_exception(request, response, exc))
            return

        http_send(
            render_http_response(
                protocol=b'1.1',
                code=result.code,
                status_code=result.status,  # status can be None
                headers=result.headers,     # but body can't, otherwise TypeError
                body=result.body or b'',
                # TODO: this option shouldn't be always True, so after native chunked transfer
                #       will be implemented this flag will become optional
                count_content_length=True
            )
        )

    def route(self,
              path: RoutePath,
              method: Union[str, bytes, None] = None,
              methods: Iterable[HTTPMethod] = HTTP_METHODS,
              middlewares: Optional[List[BaseMiddleware]] = None):
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

    def get(self, path: RoutePath,
            middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'GET', middlewares=middlewares)

    def post(self, path: RoutePath,
             middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'POST', middlewares=middlewares)

    def head(self, path: RoutePath,
             middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'HEAD', middlewares=middlewares)

    def put(self, path: RoutePath,
            middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'PUT', middlewares=middlewares)

    def trace(self, path: RoutePath,
              middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'TRACE', middlewares=middlewares)

    def connect(self, path: RoutePath,
                middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'CONNECT', middlewares=middlewares)

    def delete(self, path: RoutePath,
               middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'DELETE', middlewares=middlewares)

    def options(self, path: RoutePath,
                middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'OPTIONS', middlewares=middlewares)

    def patch(self, path: RoutePath,
              middlewares: Optional[List[BaseMiddleware]] = None):
        return self.route(path, 'PATCH', middlewares=middlewares)

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

    def handle_error(self, error: Type[Exception]):
        def deco(coro: AsyncFunction):
            self.error_handlers[error] = coro

            return coro

        return deco

    def add_global_middleware(self, middleware: BaseMiddleware):
        self.global_middlewares.append(middleware)

    def add_global_middlewares(self, *middlewares: BaseMiddleware):
        for middleware in middlewares:
            self.add_global_middleware(middleware)

    async def _handle_exception(self,
                                request: Request,
                                response: Response,
                                exc: Exception) -> bytes:
        err_handler = self._get_error_handler(exc.__class__)

        if err_handler is None:
            if isinstance(exc, exceptions.HTTPError):
                # if no handlers attached, but as we have HTTPError,
                # we can show the default error page to user

                return render_http_response(
                    protocol=request.protocol.encode(),
                    code=exc.code,
                    status_code=exc.description,
                    headers=response.default_headers,
                    body=b'<h1>%d %s</h1>' % (exc.code, exc.description),
                    count_content_length=True
                )

            self.logger.exception('no error handlers registered for exception:')

            return PRE_RENDERED_INTERNAL_ERROR_RESPONSE

        return await self._run_exception_handler(
            exc_handler=err_handler,
            request=request,
            response=response,
            exception=exc
        )

    def _get_error_handler(self, exc_class: Type[Exception]) -> Optional[ErrorHandler]:
        for exception_class in exc_class.mro():
            if exception_class in self.error_handlers:
                # idk why linter is yelling, as exc_class is always an exception,
                # he is always a subclass of Exception, subclass of subclass of Exception, etc.
                return self.error_handlers[exception_class]  # noqa

    async def _run_exception_handler(self,
                                     exc_handler: ErrorHandler,
                                     request: Request,
                                     response: Response,
                                     exception: Exception):
        try:
            result = await exc_handler(request, response, exception)
        except exceptions.HTTPError as exc:
            request = exc.request

            return render_http_response(
                protocol=request.protocol,
                code=exc.code,
                status_code=exc.description,
                headers=response.default_headers,
                body=b'<h1>%d %s</h1>' % (exc.code, exc.description)
            )
        except Exception:   # noqa: again I need to catch all the exceptions here
            self.logger.exception('uncaught exception in error handler:')

            return PRE_RENDERED_INTERNAL_ERROR_RESPONSE

        return render_http_response(
            protocol=b'1.1',
            code=result.code,
            status_code=result.status,
            headers=result.headers,
            body=result.body,
            count_content_length=True
        )

    @staticmethod
    def _apply_middlewares(handler: Handler, middlewares: List[BaseMiddleware]):
        handler.middlewares.extend(middlewares)

    def _put_handler(self, handler: Handler) -> None:
        if handler.any_path:
            self._add_any_path_handler(handler)
        else:
            self.usual_handlers[handler.path] = handler

    def _add_any_path_handler(self, handler: Handler) -> None:
        for method in handler.methods:
            self.any_paths_handlers[method] = handler
