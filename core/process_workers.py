import logging
from typing import Iterable
from traceback import format_exc

from utils.exceptions import NotFound
from core.entities import Handler, Request

logger = logging.getLogger(__name__)


def err_handler_wrapper(err_handler_type, func, request):
    try:
        func(request)
    except Exception as exc:
        logger.error(f'[ERROR-HANDLER] Caught an unhandled exception in {err_handler_type} '
                     f'handler (function name: {func.__name__}): {exc} (see full trace below)')
        logger.exception(format_exc())


def process_worker(http_server, loader, handlers,
                   err_handlers: dict, redirects: dict):
    """
    Function that infinitely running. Getting request from requests_queue and
    calling a handler that matches a request
    """

    request = Request(http_server, loader)
    # bind to avoid getting attribute of class instance every single request
    requests_queue = http_server.requests
    # some hardcoded binds for err handlers
    not_found_handler = err_handlers['not-found']
    internal_error_handler = err_handlers['internal-error']
    print('running process worker!')

    while True:
        print('waiting for a request..')
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

        handler = pick_handler(handlers, request)

        if handler is None:
            not_found_handler(request)
            continue

        try:
            handler.func(request)
        except NotFound:
            not_found_handler(request)
        except Exception as exc:
            logger.error('[ERROR-HANDLER] Caught an unhandled exception in handler (function name: '
                         f'{handler.func.__name__}): {exc} (see full trace below)')
            logger.exception(format_exc())

            internal_error_handler(request)


def pick_handler(handlers: Iterable[Handler], request):
    for handler in handlers:
        if handler.path_route not in {request.path, '*'}:
            continue

        if request.method not in handler.methods:
            continue

        if handler.filter is not None and not handler.filter(request):
            continue

        return handler

    return None
