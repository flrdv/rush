from typing import Iterable
from queue import Queue, Empty
from traceback import format_exc
from http_parser.http import HttpParser

from lib import simplelogger
from core.entities import Handler, Request

logger = simplelogger.Logger('handlers', filename='logs/handlers.log')


def process_worker(handlers, extra_handlers: dict, requests_queue: Queue):
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
            extra_handlers['not-found'](request)
            continue

        try:
            handler.func(request)
        except Exception as exc:
            logger.write(f'an uncaught error occurred in handler called "{handler.__name__}":',
                         simplelogger.ERROR)
            logger.write(format_exc(), simplelogger.ERROR, time_format='')

            # TODO: do not forget to wrap all the extra-handlers into some safety wrapper
            #       that will catch all the exceptions in extra-handlers to avoid process
            #       dying because of error in extra-handler
            extra_handlers['internal-error'](request, format_exc())


def rebuild_request_object(old_obj: Request, body, conn, parser: HttpParser):
    major, minor = parser.get_version()
    old_obj.build(protocol=f'HTTP/{major}.{minor}',
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
