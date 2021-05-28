from utils.webutils import format_headers, response as render_response

REQUEST_TEMPLATE = """\
{method} {path} {protocol}
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

    def response(self, protocol, code, body=None, status_code_desc=None,
                 headers=None, content_type=None):
        """
        Didn't write just *args, **kwargs to let IDE propose user auto-completions for
        arguments
        """
        self.webserver.send_response(self.conn, render_response(protocol, code,
                                                                body=body,
                                                                status_code_desc=status_code_desc,
                                                                headers=headers,
                                                                content_type=content_type
                                                                ))

    def raw_response(self, response: bytes):
        """
        Same as self.response(), but user can send anything he wants.
        For example, he wanna send some bullshit to client that is not
        a valid http packet. He can do that!
        """

        self.webserver.send_response(self.conn, response)

    def __str__(self):
        return REQUEST_TEMPLATE.format(method=self.method, path=self.path,
                                       protocol=self.protocol, headers=format_headers(self.headers),
                                       body=self.body)

    __repr__ = __str__


class Handler:
    def __init__(self, func, route,
                 methods, filter_):
        self.func = func
        self.route = route
        self.methods = methods
        self.filter = filter_


def default_not_found_handler(loader, request):
    content, content_type = loader.load('404.html')
    request.response('HTTP/1.1', 404, content, content_type=content_type)


def default_internal_error_handler(loader, request):
    content, content_type = loader.load('internal_error.html')
    request.response('HTTP/1.1', 500, content, content_type=content_type)
