from rush.core.utils.httputils import parse_params, render_http_response


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

        if methods:
            self.methods = {method.upper().encode() for method in methods}
        else:
            self.methods = {b'GET', b'HEAD', b'POST', b'PUT',
                            b'DELETE', b'CONNECT', b'OPTIONS',
                            b'TRACE', b'PATCH'}


class Request:
    """
    Request object that will be reusing, that's why constructor is empty,
    but build() is working like a constructor
    """

    def __init__(self, http_server, loader):
        self.protocol = None
        self.method = None
        self.path = None
        self.raw_parameters = None
        self.fragment = None
        self.headers = None
        self.body = None
        self.conn = None
        self.file = None
        self.args = {}

        self._http_server = http_server
        self._send = http_server.send
        self.loader = loader

        self._files_responses_cache = {}

    def build(self, protocol, method, path, parameters,
              fragment, headers, body, conn, file):
        self.protocol = protocol
        self.method = method
        self.path = path
        self.raw_parameters = parameters
        self.fragment = fragment
        self.headers = headers
        self.body = body
        self.conn = conn
        self.file = file
        self.args.clear()

    def response(self, code, body=b'', headers=None, code_desc=None):
        self._send(self.conn, render_http_response(self.protocol, code,
                                                   code_desc, headers,
                                                   body))

    def response_file(self, filename):
        """
        Loads file from loader. If file not found, FileNotFoundError exception
        will be raised and processed by handlers manager
        """

        if filename == '/':
            filename = 'index.html'

        self.loader.send_response(self.conn, filename)

    def raw_response(self, data: bytes):
        """
        Proxy function for HttpServer.send

        `data` has to be bytes-like, otherwise error in handler will occur
        if user wants to response with http, he should just call http response
        renderer function as an argument
        """

        self._send(self.conn, data)

    def get_args(self):
        if self.raw_parameters:
            return parse_params(self.raw_parameters)
        
        return {}
