"""
Internal module for http interacting. All the functions, methods, etc. should be
proxied
"""

from queue import Queue
from http_parser.http import HttpParser

from lib.epollserver import EpollServer
from utils.status_codes import status_codes

DEFAULT_RECV_BLOCK_SIZE = 8192  # how many bytes are receiving per 1 socket read


class HttpServer:
    def __init__(self, sock, max_clients):
        """
        Basic http server built on lib.epollserver

        Just receives raw bytes and puts them into the HttpServer.requests Queue object
        Puts into the Queue object such an objects: (data: bytes, conn: socket.socket,
                                                     parser: http_parser.http.HttpParser)
        """

        self.epollserver = EpollServer(sock, maxconns=max_clients)

        # I'm using http-parser but not parsing just to know when request has been ended
        # anyway I'm putting parser-object to the queue, so no new parsers entities
        # will be created
        self._requests_buff = {}    # conn: [parser, raw]

        self.requests = Queue()

    def _receive_handler(self, _, conn):
        parser, previously_received_body = self._requests_buff[conn]
        received_body_part = conn.recv(DEFAULT_RECV_BLOCK_SIZE)

        parser.execute(received_body_part, len(received_body_part))
        current_body = previously_received_body + received_body_part

        if parser.is_message_complete():
            self.requests.put((current_body, conn, parser))
            self._requests_buff[conn] = [HttpParser(decompress=True), b'']
        else:
            self._requests_buff[conn][1] = current_body


def render_http_response(protocol, status_code, status_code_desc,
                         content_type, headers, body):
    # default headers
    # TODO: add server-time header
    final_headers = {
        'Content-Length': len(body),
        'Server': 'rush',
        'Content-Type': content_type or 'text/html',
        'Connection': 'keep-alive'
    }
    final_headers.update(headers or {})
    body = body if isinstance(body, bytes) else body.encode()

    # building time
    status_description = status_code_desc or status_codes.get(status_code, 'NO DESCRIPTION')

    return b'%s %d %s\r\n%s\r\n\r\n%s' % (protocol.encode(), status_code,
                                          status_description.encode(),
                                          format_headers(final_headers), body)


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}' for key, value in headers.items()).encode()
