import logging
from queue import Queue
from typing import Iterable
from traceback import format_exc
from http_parser.http import HttpParser

from core.entities import Handler, Request

logging.basicConfig(filename='logs/handlers.log', level=logging.DEBUG,
                    format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger('handler')


def err_handler_wrapper(err_handler_type, func, request):
    try:
        func(request)
    except Exception as exc:
        logger.error(f'[ERROR-HANDLER] Caught an unhandled exception in {err_handler_type} '
                     f'handler (function name: {func.__name__}): {exc} (see full trace below)')
        logger.exception(format_exc())


def process_worker(handlers, err_handlers: dict, requests_queue: Queue):
    """
    Function that infinitely running. Getting request from requests_queue and
    calling a handler that matches a request
    """

    request = Request()

    while True:
        body, conn, parser = requests_queue.get()
        rebuild_request_object(request, body, conn, parser)
        handler = pick_handler(handlers, request)

        if handler is None:
            err_handlers['not-found'](request)
            continue

        try:
            handler.func(request)
        except Exception as exc:
            logger.error('[ERROR-HANDLER] Caught an unhandled exception in handler (function name: '
                         f'{handler.__name__}): {exc} (see full trace below)')
            logger.exception(format_exc())

            # TODO: do not forget to wrap all the extra-handlers with extra_handler_wrapper
            err_handlers['internal-error'](request)


def rebuild_request_object(old_obj: Request, body, conn, parser: HttpParser):
    old_obj.build(protocol=parser.get_version(),
                  method=parser.get_method(),
                  path=parser.get_path(),
                  headers=parser.get_headers(),
                  body=body,
                  conn=conn,
                  file=None)


def pick_handler(handlers: Iterable[Handler], request):
    for handler in handlers:
        if handler.path_route != request.path:
            continue

        if request.method not in handler.methods:
            continue

        if handler.filter is not None and not handler.filter(request):
            continue

        return handler

    return None
