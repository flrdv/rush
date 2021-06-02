from core.utils import httputils


class Handler:
    def __init__(self, func, filter_, path_route,
                 methods):
        self.func = func
        self.filter = filter_
        self.path_route = path_route.rstrip('/')
        self.methods = methods or {'GET', 'HEAD', 'POST', 'PUT',
                                   'DELETE', 'CONNECT', 'OPTIONS',
                                   'TRACE', 'PATCH'}


class Request:
    """
    Request object that will be reusing, that's why constructor is empty,
    but build() is working like a constructor
    """

    def __init__(self, http_server):
        self.protocol = None
        self.method = None
        self.path = None
        self.headers = None
        self.body = None
        self.conn = None
        self.file = None

        self._http_server = http_server

    def build(self, protocol, method, path,
              headers, body, conn, file):
        self.protocol = protocol
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.conn = conn
        self.file = file

    def response(self, code, description=None, body=b'',
                 headers=None):
        self._http_server.send(httputils.render_http_response(self.protocol, code, description,
                                                              headers, body))

    def raw_response(self, data: bytes):
        """
        Proxy function for HttpServer.send

        `data` has to be bytes-like, otherwise error in handler will occur
        if user wants to response with http, he should just call http response
        renderer function as an argument
        """

        self._http_server.send(data)
