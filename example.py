from rush import webserver, entities
from rush.dispatcher.default import SimpleAsyncDispatcher, Route

dp = SimpleAsyncDispatcher()
app = webserver.WebServer()


@dp.get('/')
async def deco_handler(request: entities.Request) -> None:
    return request.response(
        code=200,
        body=b'Hello, world!'
    )


@dp.get('/get-request-fields')
async def awaiting_demo(request: entities.Request) -> None:
    method: bytes = request.method
    path: bytes = request.path
    headers: entities.CaseInsensitiveDict = request.headers
    body: bytes = request.body
    
    return request.response(
        code=200,
        body=b'great job, buddy'
    )


async def echo_req_body_handler(request: entities.Request) -> None:
    if 'easter' in request.headers:
        return request.response(
            code=201,
            body=b'wow, you found an easter egg!'
        )
    
    # it shouldn't be returned cause only one call of 
    # request.response() responses. Used returns for
    # more defined & usual behaviour
    request.response(
        code=200,
        body=request.body
    )


dp.add_routes([
    Route(echo_req_body_handler, '/echo', 'GET')
])

app.run(dp)
