from typing import Union

from httptools import HttpRequestParser

from ..entities import Request
from ..utils.httputils import decode_url
from ..typehints import Coroutine, Nothing
from ..entities import CaseInsensitiveDict


class Protocol:
    headers = CaseInsensitiveDict()

    def __init__(self,
                 request_obj: Request,
                 ):
        self.request_obj = request_obj

        self.body = b''
        self.file = False

        self.received: bool = False

        self._on_chunk: Union[Coroutine, None] = None
        self._on_complete: Union[Coroutine[Nothing], None] = None

        self.parser: Union[HttpRequestParser, None] = None

    def on_url(self, url: bytes):
        if b'%' in url:
            url = decode_url(url)

        parameters = fragment = None

        if b'?' in url:
            url, parameters = url.split(b'?', 1)

            if b'#' in parameters:
                parameters, fragment = parameters.split(b'#', 1)
        elif b'#' in url:
            url, fragment = url.split(b'#', 1)

        self.request_obj.set_path(url)
        self.request_obj.set_params(parameters)
        self.request_obj.set_fragment(fragment)

    def on_header(self, header: bytes, value: bytes):
        self.headers[header.decode()] = value.decode()

    def on_headers_complete(self):
        self.request_obj.set_protocol(self.parser.get_http_version())
        self.request_obj.set_headers(self.headers)

        if self.headers.get(b'transfer-encoding') == b'chunked' or \
                self.headers.get(b'content-type', b'').startswith(b'multipart/'):
            self.file = True
            self._on_chunk, self._on_complete = \
                self.request_obj.get_on_chunk(), self.request_obj.get_on_complete()

    def on_body(self, body: bytes):
        if self._on_chunk:
            self._on_chunk(body)
        else:
            self.body += body

    def on_body_complete(self):
        self.request_obj.set_body(self.body)

    def on_message_complete(self):
        if not self.body:
            self.request_obj.set_body(b'')

        self.received = True

        if self._on_complete:
            self._on_complete()
