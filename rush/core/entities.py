from rush.core.utils import httputils


class Handler:
    def __init__(self, func, filter_, path_route,
                 methods, any_paths):
        self.func = func
        self.filter = filter_
        self.any_paths = any_paths
        self.path_route = path_route.rstrip('/') if path_route is not None else None

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
        self._parameters = None
        self.headers = None
        self.body = None
        self.conn = None
        self.file = None
        self.args = {}

        self._http_server = http_server
        self.loader = loader

        self._files_responses_cache = {}

    def build(self, protocol, method, path, parameters,
              headers, body, conn, file):
        self.protocol = protocol
        self.method = method
        self.path = path
        self._parameters = parameters
        self.headers = headers
        self.body = body
        self.conn = conn
        self.file = file
        self.args.clear()

    def response(self, code, body=b'', headers=None, code_desc=None):
        self._http_server.send(self.conn, httputils.render_http_response(self.protocol, code,
                                                                         code_desc, headers,
                                                                         body))

    def response_file(self, filename, **kwargs):
        """
        Loads file from loader. If file not found, FileNotFoundError exception
        will be raised and processed by handlers manager
        """

        if filename not in self._files_responses_cache:
            request = httputils.render_http_response(self.protocol, 200, 'OK',
                                                     None, self.loader.load(filename))
            self._files_responses_cache[filename] = request
        else:
            request = self._files_responses_cache[filename]

        return self.raw_response(request)

    def raw_response(self, data: bytes):
        """
        Proxy function for HttpServer.send

        `data` has to be bytes-like, otherwise error in handler will occur
        if user wants to response with http, he should just call http response
        renderer function as an argument
        """

        self._http_server.send(self.conn, data)

    def parse_args(self):
        if not self.args and self._parameters:
            self.args = httputils.parse_qs(self._parameters)
