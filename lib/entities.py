class Request:
    def __init__(self, webserver, conn, typeof,
                 path, protocol, headers, body):
        self.webserver = webserver
        self.conn = conn
        self.type = typeof
        self.path = path
        self.protocol = protocol
        self.headers = headers
        self.body = body

    def get_values(self):
        return {**self.headers, 'body': self.body}

    def response(self, data):
        self.webserver.send_response(self.conn, data)

    def __str__(self):
        headers = '\n'.join((f'{key}={repr(value)}' for key, value in self.headers.items()))

        return f"""{self.type} {self.path} {self.protocol}
{headers}

{self.body or ''}"""

    __repr__ = __str__


def get_handler(handlers, request: Request, return_otherwise=None):
    for handler, handler_filter in handlers.items():
        if handler_filter(request):
            return handler

    return return_otherwise
