from typing import Awaitable

from rush import webserver
from rush.entities import Request, Response
from rush.middlewares.base import BaseMiddleware
from rush.dispatcher.default import AsyncDispatcher, Route

dp = AsyncDispatcher()
app = webserver.WebServer()


class MyMiddleware(BaseMiddleware):
    async def process(self, handler: Awaitable, request: Request) -> Response:
        request.ctx.hello = 'hello, world!'
        response = await handler
        response.add_body(f'\nHandler said: {request.ctx["from_handler"]}')

        return response


@dp.get('/')
async def deco_handler(request: Request, response: Response) -> Response:
    return response(
        code=200,
        body=b'Hello, world!'
    )


@dp.get('/get-request-fields')
async def awaiting_demo(request: Request, response: Response) -> Response:
    return response(
        code=200,
        body=b'method: %s\npath: %s\nbody: %s' % (
            request.method, request.path, request.body
        )
    )


async def middleware_example(request: Request, response: Response) -> Response:
    request.ctx.from_handler = 'with love'

    return response(
        body=f'Middleware said: {request.ctx["hello"]}'
    )


async def echo_req_body_handler(request: Request, response: Response) -> Response:
    if 'easter' in request.headers:
        return response(
            code=201,
            body=b'wow, you found an easter egg!'
        )
    
    # it shouldn't be returned cause only one call of 
    # request.response() responses. Used returns for
    # more defined & usual behaviour
    return response(
        code=200,
        body=request.body
    )


dp.add_routes([
    Route(echo_req_body_handler, '/echo', 'GET'),
    Route(middleware_example, '/middlewares', 'GET',
          middlewares=[
              MyMiddleware()
          ])
])

app.run(dp)
