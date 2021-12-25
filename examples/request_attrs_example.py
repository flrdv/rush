import logging

from rush import webserver
from rush.entities import Request, Response
from rush.dispatcher.default import AsyncDispatcher, Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('request_attrs_example')

dp = AsyncDispatcher()
app = webserver.WebServer()


async def log_request_attrs(request: Request, response: Response) -> Response:
    logger.info(
        f'Got a request:\n'
        f'protocol: HTTP/{request.protocol}\n'
        f'path: {request.path}\n'
        f'method: {request.method}\n'
        f'parameters: {request.params()}\n'
        f'fragment: {request.fragment}\n'
        f'headers: {request.headers}\n'
        f'body: {request.body}'
    )

    return response(
        body=b'<h1>Lorem ipsum</h1>'
    )


dp.add_routes([
    Route(log_request_attrs, '/')
])

app.run(dp)
