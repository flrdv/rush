from typing import Dict

from handler.client import Handler


handler = Handler()


@handler()
def handle(client, request: Dict[str, bytes]):
    print('New request:', request)
    client.response(b'you said: ' + request['body'])


handler.start()
