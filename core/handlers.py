import logging
from typing import Iterable
from traceback import format_exc

from utils.exceptions import NotFound
from core.entities import Handler, Request

logger = logging.getLogger(__name__)


class HandlersManager:
    def __init__(self, http_server, loader, handlers,
                 err_handlers, redirects):
        self.http_server = http_server
        self.loader = loader
        self.handlers = handlers
        self.err_handlers = err_handlers
        self.redirects = redirects

        self.request_obj = Request(http_server, loader)
        # some hardcoded binds for err handlers
        self.not_found_handler = err_handlers['not-found']
        self.internal_error_handler = err_handlers['internal-error']

    def call_handler(self, body, conn, proto_version,
                     method, path, headers):
        request_obj = self.request_obj
        self.request_obj.build(protocol=proto_version,
                               method=method,
                               path=path,
                               headers=headers,
                               body=body,
                               conn=conn,
                               file=None)

        if path in self.redirects:
            return self.request_obj.response(301, headers={'Location': self.redirects[path]})

        handler = _pick_handler(self.handlers, request_obj)

        if handler is None:
            return self.not_found_handler(request_obj)

        try:
            handler.func(request_obj)
        except (FileNotFoundError, NotFound):
            self.not_found_handler(request_obj)
        except Exception as exc:
            logger.error('[ERROR-HANDLER] Caught an unhandled exception in handler (function name: '
                         f'{handler.func.__name__}): {exc}\nFull traceback:\n{format_exc()}')

            self.internal_error_handler(request_obj)


def err_handler_wrapper(err_handler_type, func, request):
    try:
        func(request)
    except Exception as exc:
        logger.error(f'caught an unhandled exception in {err_handler_type} handler (function name: '
                     f'{func.__name__}): {exc}\nFull traceback:\n{format_exc()}')


def _pick_handler(handlers: Iterable[Handler], request):
    for handler in handlers:
        if handler.path_route not in {request.path, '*'}:
            continue

        if request.method not in handler.methods:
            continue

        if handler.filter is not None and not handler.filter(request):
            continue

        return handler

    return None


def _process_worker(http_server, loader, handlers,
                    err_handlers: dict, redirects: dict):
    """
    DEPRECATED

    Function that infinitely running. Getting request from requests_queue and
    calling a handler that matches a request
    """

    # bind to avoid getting attribute of class instance every single request
    requests_queue = http_server.requests
    responses_queue = http_server.responses
    request = Request(responses_queue, loader)
    # some hardcoded binds for err handlers
    not_found_handler = err_handlers['not-found']
    internal_error_handler = err_handlers['internal-error']

    while True:
        body, conn, (proto_version, method, path, headers) = requests_queue.get()
        request.build(protocol=proto_version,
                      method=method,
                      path=path,
                      headers=headers,
                      body=body,
                      conn=conn,
                      file=None)

        if path in redirects:
            request.response(301, headers={'Location': redirects[path]})
            continue

        handler = _pick_handler(handlers, request)

        if handler is None:
            not_found_handler(request)
            continue

        try:
            handler.func(request)
        except NotFound:
            not_found_handler(request)
        except Exception as exc:
            logger.error('[ERROR-HANDLER] Caught an unhandled exception in handler (function name: '
                         f'{handler.func.__name__}): {exc}\nFull traceback:\n{format_exc()}')

            internal_error_handler(request)
