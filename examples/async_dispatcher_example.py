from rush import webserver
from rush.entities import Request, Response
from rush.dispatcher.default import AsyncDispatcher, Route

dp = AsyncDispatcher()
app = webserver.WebServer()


@dp.get('/deco')
async def deco_handler(request: Request, response: Response) -> Response:
    return response(
        body=b'Registered handler using decorator'
    )


async def route_handler(request: Request, response: Response) -> Response:
    return response(
        body=b'Registered handler using route'
    )


dp.add_routes([
    Route(route_handler, '/route', 'GET')
])

app.run(dp)
