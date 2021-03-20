from typing import Dict

from handler.client import Handler


handler = Handler(addr=('192.168.0.102', 10000))


@handler.update_parser
def parse_update(request_from, request):
    return {'request-from': request_from, 'body': request}


@handler()
def handle(client, request: Dict[str, bytes]):
    print('New request:', request)
    client.response(request['request-from'], b'you said: ' + request['body'])


handler.start()
