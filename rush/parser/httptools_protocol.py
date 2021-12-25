import asyncio
from typing import Optional

from httptools import HttpRequestParser

from ..entities import Request
from ..utils.httputils import decode_url
from ..typehints import AsyncFunction, Nothing
from ..entities import CaseInsensitiveDict


class Protocol:
    REQUEST_HEADERS = CaseInsensitiveDict()

    def __init__(self,
                 request_obj: Request,
                 ):
        self.request_obj = request_obj

        self.headers = self.REQUEST_HEADERS.copy()
        self.body: bytes = b''
        self.file: bool = False

        self.received: bool = False

        self._on_chunk: Optional[AsyncFunction] = None
        self._on_complete: Optional[AsyncFunction[Nothing]] = None

        self.parser: Optional[HttpRequestParser] = None

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

        self.request_obj.path = url
        self.request_obj.raw_parameters = parameters
        self.request_obj.fragment = fragment
        self.request_obj.method = self.parser.get_method()

    def on_header(self, header: bytes, value: bytes):
        self.headers[header.decode()] = value.decode()

    def on_headers_complete(self):
        self.request_obj.protocol = self.parser.get_http_version()
        self.request_obj.headers = self.headers

        if self.headers.get('transfer-encoding') == 'chunked' or \
                self.headers.get('content-type', '').startswith('multipart/'):
            self.file = True
            self._on_chunk, self._on_complete = \
                self.request_obj.get_on_chunk(), self.request_obj.get_on_complete()

    def on_body(self, body: bytes):
        if self._on_chunk:
            asyncio.create_task(self._on_chunk(body))
        else:
            self.request_obj.body += body

    def on_message_complete(self):
        self.received = True

        if self._on_complete:
            asyncio.create_task(self._on_complete())
