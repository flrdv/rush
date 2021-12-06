import logging
from typing import Awaitable

from rush import webserver
from rush.entities import Request, Response
from rush.middlewares.base import BaseMiddleware
from rush.dispatcher.default import AsyncDispatcher, Route

logging.basicConfig()
logger = logging.getLogger('request_ctx_example')

dp = AsyncDispatcher()
app = webserver.WebServer()


class MyMiddleware(BaseMiddleware):
    async def process(self,
                      handler: Awaitable,
                      request: Request) -> Response:
        logger.info('doing some magic with request...')

        ...

        request.ctx['from_middleware'] = 'with love <3'

        response = await handler

        logger.info(f'look, look! Handler responded to us: {request.ctx["from_handler"]}; '
                    'I love this guy!')

        return response


async def my_route_handler(request: Request, response: Response) -> Response:
    logger.info('hope, middleware said something for us...')
    logger.info(f'yes, here it is: {request.ctx["from_middleware"]}! I love her! '
                'Looks like I need to say something in response...')
    request.ctx['from_handler'] = 'I love you, too!'

    return response(
        body=b'one day middleware will see this message and know how I love her...'
    )


dp.add_routes([
    Route(my_route_handler, '/route-middleware', 'GET')
])

app.run(dp)

