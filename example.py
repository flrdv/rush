from rush import webserver, entities
from rush.dispatcher.default import SimpleAsyncDispatcher, Route

dp = SimpleAsyncDispatcher()
app = webserver.WebServer()


@dp.get('/')
async def deco_handler(request: entities.Request) -> None:
    await request.response(
        code=200,
        body=b'Hello, world!'
    )


@dp.get('/awaiting-demo')
async def awaiting_demo(request: entities.Request) -> None:
    await request.method()
    await request.path()
    await request.protocol()
    await request.params()
    await request.fragment()
    await request.headers()
    await request.body()

    await request.response(
        code=200,
        body=b'awaiting request methods has succeeded'
    )


async def aiohttp_like_handler(request: entities.Request) -> None:
    if 'easter' in await request.headers():
        return await request.response(
            code=201,
            body=b'wow, you found an easter egg!'
        )

    await request.response(
        code=200,
        body=await request.body()
    )


dp.add_routes([
    Route(aiohttp_like_handler, '/echo', 'GET')
])

app.run(dp)

