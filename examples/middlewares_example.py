import logging
from typing import Awaitable

from rush import webserver
from rush.entities import Request, Response
from rush.middlewares.base import BaseMiddleware
from rush.dispatcher.default import AsyncDispatcher, Route

logging.basicConfig()
logger = logging.getLogger('middlewares_example')

dp = AsyncDispatcher()
app = webserver.WebServer()


class MyMiddleware(BaseMiddleware):
    async def process(self,
                      handler: Awaitable,
                      request: Request) -> Response:
        logger.info('pre-processing request in middleware...')

        ...

        response = await handler

        logger.info('post-processing response in middleware...')

        ...

        return response


class MyGlobalMiddleware(BaseMiddleware):
    async def process(self,
                      handler: Awaitable,
                      request: Request) -> Response:
        """
        This is usual middleware, but applies to all the handlers on dispatcher level
        """

        logger.info('I am global middleware, and doing here some calculations before '
                    'non-global middlewares will be called')

        ...

        return await handler


@dp.get('/deco-middleware', middlewares=[
    MyMiddleware()
])
async def my_deco_handler(request: Request, response: Response) -> Response:
    logger.info('processing request in handler...')

    ...

    return response(
        body=b'processed everything!'
    )


async def my_route_handler(request: Request, response: Response) -> Response:
    ...  # same as in my_deco_handler

    return response(
        body=b'processed everything, but in route handler!'
    )


dp.add_global_middlewares(
    MyGlobalMiddleware(),
)
dp.add_routes([
    Route(my_route_handler, '/route-middleware', 'GET')
])

app.run(dp)
