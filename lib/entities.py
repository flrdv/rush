REQUEST_TEMPLATE = """\
{method} {path} {protocol}
{headers}

{body}
"""
RESPONSE_TEMPLATE = """\
{protocol} {code} {description}
{headers}

{body}
"""


class Request:
    def __init__(self, webserver, conn, method,
                 path, protocol, headers, body):
        self.webserver = webserver
        self.conn = conn
        self.method = method
        self.path = path
        self.protocol = protocol
        self.headers = headers
        self.body = body

    def get_values(self):
        return {**self.headers, 'body': self.body}

    def response(self, response):
        # if isinstance(data, Response):
        #     data = data.build()

        self.webserver.send_response(self.conn, response.content)

    def __str__(self):
        headers = '\n'.join((f'{key}={repr(value)}' for key, value in self.headers.items()))

        return REQUEST_TEMPLATE.format(method=self.method, path=self.path,
                                       protocol=self.protocol, headers=headers,
                                       body=self.body)

    __repr__ = __str__


class Response:
    def __init__(self, protocol, code, description,
                 body=None):

        self.protocol = protocol
        self.code = code
        self.description = description

        headers = {
            'Content-Length': len(body),
            'Server': 'rush',
        }

        self.body = body

        cooked_headers = '\n'.join(f'{key}: {value}' for key, value in headers.items())

        self.content = RESPONSE_TEMPLATE.format(protocol=protocol, code=code,
                                                description=description, headers=cooked_headers,
                                                body=body or '').encode()


def get_handler(handlers, request: Request, return_otherwise=None):
    for handler, handler_filter in handlers.items():
        if handler_filter(request):
            return handler

    return return_otherwise
