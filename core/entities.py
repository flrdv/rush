from core.utils import httputils


class Handler:
    def __init__(self, func, filter_, path_route,
                 methods):
        self.func = func
        self.filter = filter_
        self.path_route = path_route.rstrip('/')

        if not self.path_route:
            # we made a mistake, we fixed a mistake
            self.path_route = '/'

        self.methods = methods or {'GET', 'HEAD', 'POST', 'PUT',
                                   'DELETE', 'CONNECT', 'OPTIONS',
                                   'TRACE', 'PATCH'}


class Request:
    """
    Request object that will be reusing, that's why constructor is empty,
    but build() is working like a constructor
    """

    def __init__(self, http_server, loader):
        self.protocol = None
        self.method = None
        self.path = None
        self.headers = None
        self.body = None
        self.conn = None
        self.file = None

        self._http_server = http_server
        self.loader = loader

    def build(self, protocol, method, path,
              headers, body, conn, file):
        self.protocol = protocol
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.conn = conn
        self.file = file

    def response(self, code, body=b'', headers=None, code_desc=None):
        self._http_server.send(self.conn, httputils.render_http_response(self.protocol, code,
                                                                         code_desc, headers,
                                                                         body))

    def response_file(self, filename, **kwargs):
        """
        Loads file from loader. If file not found, FileNotFoundError exception
        will be raised and processed by handlers manager
        """

        body = self.loader.load(filename)

        self.response(200, body=body, **kwargs)

    def raw_response(self, data: bytes):
        """
        Proxy function for HttpServer.send

        `data` has to be bytes-like, otherwise error in handler will occur
        if user wants to response with http, he should just call http response
        renderer function as an argument
        """

        self._http_server.send(self.conn, data)
