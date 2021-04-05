from os.path import join

from utils.status_codes import status_codes

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

    def response(self, protocol, code, body=None, status_code_desc=None):
        description = status_code_desc or status_codes.get(code, 'UNKNOWN')
        headers = {
            'Content-Length': len(body),
            'Server': 'rush',
        }
        cooked_headers = '\n'.join(f'{key}: {value}' for key, value in headers.items())

        content = RESPONSE_TEMPLATE.format(protocol=protocol, code=code,
                                           description=description, headers=cooked_headers,
                                           body=body or '').encode()

        self.webserver.send_response(self.conn, content)

    def static_response(self, response: 'Response'):
        """
        Same as response(), but used for responses with static content
        Static responses are convenient to implement using pre-rendered
        Response-object
        """

        self.webserver.send_response(self.conn, response.content)

    def __str__(self):
        headers = '\n'.join((f'{key}={repr(value)}' for key, value in self.headers.items()))

        return REQUEST_TEMPLATE.format(method=self.method, path=self.path,
                                       protocol=self.protocol, headers=headers,
                                       body=self.body)

    __repr__ = __str__


class Response:
    def __init__(self, protocol, code, body=None,
                 status_code_desc=None):
        self.protocol = protocol
        self.code = code
        self.description = status_code_desc or status_codes.get(code, 'UNKNOWN')

        headers = {
            'Content-Length': len(body),
            'Server': 'rush',
        }

        self.body = body

        cooked_headers = '\n'.join(f'{key}: {value}' for key, value in headers.items())
        self.content = RESPONSE_TEMPLATE.format(protocol=protocol, code=code,
                                                description=self.description, headers=cooked_headers,
                                                body=body or '').encode()


class Loader:
    def __init__(self, root='localfiles', caching=False):
        self.root = root
        self.caching = caching

        self.cache = {}
        self.default_404_response = """\
<html>
    <head>
        <title>404 NOT FOUND</title>
    </head>
    <body>
        <h6>404 REQUEST PAGE NOT FOUND</h6>
    </body>
</html>        
"""

    def load(self, path: str, load_otherwise: str or None = '/404.html',
             cache: bool = None):
        if path == '/':
            path = '/index.html'

        if path in self.cache:
            return self.cache[path]

        try:
            with open(self.root + path) as fd:
                content = fd.read()
        except FileNotFoundError:
            if not load_otherwise:
                return self.default_404_response

            return self.load(load_otherwise, load_otherwise='', cache=cache)

        if cache is None:
            cache = self.caching

        if cache:
            self.cache[path] = content

        return content

    def cache_files(self, *files):
        for file in files:
            self.load(file, cache=True)


def get_handler(handlers, request: Request, return_otherwise=None):
    for handler, handler_filter in handlers.items():
        if handler_filter(request):
            return handler

    return return_otherwise
