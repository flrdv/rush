from rush import webserver
from rush.entities import Request, Response
from rush.dispatcher.default import AsyncDispatcher

dp = AsyncDispatcher()
app = webserver.WebServer()


@dp.get('/')
async def home(request: Request, response: Response) -> Response:
    return response(
        body=b'<h1>Hello, world!</h1>'
    )


app.run(dp)
