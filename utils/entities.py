from utils import case_formatter
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

    def response(self, protocol, code, body=None, status_code_desc=None,
                 headers=None, content_type=None):
        if not isinstance(body, bytes):
            body = (body or '').encode()

        description = status_code_desc or status_codes.get(code, 'UNKNOWN')
        main_headers = {
            'Content-Length': len(body),
            'Server': 'rush',
            'Content-Type': content_type or 'plain/text',
        }
        main_headers.update(headers or {})

        content = RESPONSE_TEMPLATE.format(protocol=protocol, code=code,
                                           description=description, headers=format_headers(main_headers),
                                           body='').encode()

        self.webserver.send_response(self.conn, content + body.lstrip(b'\n'))

    def static_response(self, response: 'Response'):
        """
        Same as response(), but used for responses with static content
        Static responses are convenient to implement using pre-rendered
        Response-object
        """

        self.webserver.send_response(self.conn, response.content)

    def __str__(self):
        return REQUEST_TEMPLATE.format(method=self.method, path=self.path,
                                       protocol=self.protocol, headers=format_headers(self.headers),
                                       body=self.body)

    __repr__ = __str__


class Response:
    def __init__(self, protocol, code, body=None,
                 status_code_desc=None, instant_build=True,
                 headers=None, content_type=None):
        """
        If you wanna add headers later - set instant_build to False
        to avoid useless http rendering
        """

        self.protocol = protocol
        self.code = code
        self.description = status_code_desc or status_codes.get(code, 'UNKNOWN')

        self.headers = {
            'Content-Length': len(body),
            'Server': 'rush',
            'Content-Type': content_type or 'plain/text',
        }
        self.headers.update(headers or {})

        self.body = body if isinstance(body, bytes) else body.encode()

        if instant_build:
            self.build()
        else:
            self.content = None

    def headers(self, from_dict=None, **kwargs):
        if from_dict is None:
            from_dict = {}

            for key, value in kwargs.items():
                from_dict[case_formatter.snake2camelcase(key)] = value

        self.headers.update(from_dict)

        return self

    def build(self):
        self.content = RESPONSE_TEMPLATE.format(protocol=self.protocol, code=self.code,
                                                description=self.description,
                                                headers=format_headers(self.headers),
                                                body='').encode()
        self.content += self.body.lstrip(b'\n')


def get_handler(handlers, request: Request, return_otherwise=None):
    for handler, handler_filter in handlers.items():
        if handler_filter(request):
            return handler

    return return_otherwise


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}' for key, value in headers.items())
