from typing import Iterable
from queue import Queue, Empty
from traceback import format_exc
from http_parser.http import HttpParser

from lib import simplelogger
from core.entities import Handler, Request

logger = simplelogger.Logger('handlers', filename='logs/handlers.log')


def err_handler_wrapper(err_handler_type, func, request):
    try:
        func(request)
    except Exception:
        logger.write(f'[ERROR-HANDLER] Caught an unhandled exception in {err_handler_type} '
                     f'handler (function name: {func.__name__}):',
                     simplelogger.ERROR)
        logger.write(format_exc(), simplelogger.ERROR, time_format='')


def process_worker(handlers, err_handlers: dict, requests_queue: Queue):
    """
    Function that infinitely running. Getting request from requests_queue and
    calling a handler that matches a request
    """

    request = Request()

    while True:
        try:
            body, conn, parser = requests_queue.get()
        except Empty:
            continue

        rebuild_request_object(request, body, conn, parser)
        handler = pick_handler(handlers, request)

        if handler is None:
            err_handlers['not-found'](request)
            continue

        try:
            handler.func(request)
        except Exception:
            logger.write(f'[ERROR-HANDLER] Caught an unhandled exception in '
                         f'handler (function name: {handler.__name__}):',
                         simplelogger.ERROR)
            logger.write(format_exc(), simplelogger.ERROR, time_format='')

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
