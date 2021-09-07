from typing import Union

try:
    import simdjson as json
except ImportError:
    try:
        import ujson as json
    except ImportError:
        import json

from rush.utils.httputils import (parse_params,
                                  render_http_response,
                                  render_http_request)


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
        # always means that there is chunked file
        self.file = None
        self.args = {}

        self.on_chunk = lambda part: 'ok'
        self.on_complete = lambda: 'ladno'

        self._http_server = http_server
        self._send = http_server.send
        self.loader = loader

        self._files_responses_cache = {}

    def build(self,
              protocol: str,
              method: bytes,
              path: str,
              parameters: bytes,
              fragment: bytes,
              headers: 'CaseInsensitiveDict',
              body: bytes,
              conn,
              file: bool
              ):
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

    def response(self,
                 body: Union[str, bytes] = b'',
                 code: int = 200,
                 headers: Union[dict, None] = None,
                 status_code: Union[str, None] = None
                 ):

        self._send(self.conn, render_http_response(protocol=self.protocol,
                                                   code=code,
                                                   status_code=status_code,
                                                   user_headers=headers,
                                                   body=body.encode() if isinstance(body, str) else body))

    def response_json(self,
                      data: Union[dict, list, bytes],
                      code: int = 200,
                      status_code: Union[str, None] = None,
                      headers: Union[dict, None] = None
                      ):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()

        final_headers = {
            'Content-Type': 'application/json',
            **(headers or {})
        }

        self._send(self.conn, render_http_response(protocol=self.protocol,
                                                   code=code,
                                                   status_code=status_code,
                                                   user_headers=final_headers,
                                                   body=data))

    def response_file(self,
                      filename: str,
                      headers: Union[dict, None] = None
                      ):
        """
        Loads file from loader. If file not found, FileNotFoundError exception
        will be raised and processed by handlers manager
        """

        if filename == '/':
            filename = 'index.html'

        self.loader.send_response(self.conn, filename, headers=headers)

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

    def get_form(self):
        if self.method == b'POST':
            return parse_params(self.body)

        return {}

    def receive_file(self, on_chunk, on_complete=None):
        if self.file:
            self.on_chunk = on_chunk
            self.on_complete = on_complete

    def __str__(self):
        return render_http_request(self.method,
                                   self.path,
                                   self.protocol,
                                   self.headers,
                                   self.body,
                                   chunked=bool(self.on_chunk)).decode()

    __repr__ = __str__


class CaseInsensitiveDict(dict):
    def __init__(self, *args, **kwargs):
        self.__parent = super()
        super().__init__(*args, **kwargs)

    def __getitem__(self, item):
        return self.__parent.__getitem__(item.lower())

    def __setitem__(self, key, value):
        self.__parent.__setitem__(key.lower(), value)

    def __contains__(self, item):
        return self.__parent.__contains__(item)

    def get(self, item, instead=None):
        return self.__parent.get(item.lower(), instead)

    def pop(self, key):
        return self.__parent.pop(key.lower())
