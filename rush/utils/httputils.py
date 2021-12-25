from string import hexdigits
from typing import Union, Optional, Dict, List, BinaryIO

from .status_codes import status_codes

HTTP_METHODS = {b'GET', b'HEAD', b'POST', b'PUT',
                b'DELETE', b'CONNECT', b'OPTIONS',
                b'TRACE', b'PATCH'}
HEX_TO_BYTE = {(a + b).encode(): bytes.fromhex(a + b)
               for a in hexdigits for b in hexdigits}


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}'
                     for key, value in headers.items()) \
        .encode()


def render_http_response(protocol: bytes,
                         code: int,
                         status_code: Optional[bytes],
                         headers: Union[dict, bytes],
                         body: bytes,
                         count_content_length: bool = False) -> bytes:
    """
    A function for rendering http responses. Uses C-formatting as the only way for
    formatting byte-strings (f-strings with encoding are shit)

    Arguments:
             protocol - protocol version, string in format `major.minor`,
             code - response status code,
             status_code - may be None, than it'll be taken from the list of known.
                           If no known status codes relate to the status code, UNKNOWN
                           will be used
             headers - a dict (or CaseInsensitiveDict) with headers. May be bytes, than
                       they won't be rendered
             body - only bytes are accepted
             count_content_length - disabled by default, but if enabled and headers aren't
                                    already rendered, content-length header will be replaced
                                    by len(body)
    """

    if not isinstance(headers, bytes):
        if count_content_length:
            headers['content-length'] = len(body)

        headers = '\r\n'.join(
            f'{key}: {value}' for key, value in headers.items()
        ).encode()

    status_description = status_code or status_codes.get(code, 'UNKNOWN')

    # TODO: in Python 3.11, they promised to make C-style formatting
    #       as fast as f-strings, but only if string is simple (%s, %r, %a).
    #       so don't forget to replace %d with %s (cast status_code to string)

    # I'm not using format_headers() function here just to avoid useless calling
    # as everybody knows, functions' calls are a bit expensive in CPython
    return b'HTTP/%s %d %s\r\n%s\r\n\r\n%s' % (protocol, code, status_description, headers, body)


def render_http_request(method: bytes,
                        path: bytes,
                        protocol: bytes,
                        headers: dict,
                        body: Union[bytes, str],
                        chunked: bool = False) -> bytes:
    if not chunked and 'content-length' not in headers:
        headers['content-length'] = len(body)

    return b'%s %s HTTP/%s\r\n%s\r\n\r\n%s' % (method, path, protocol,
                                               '\r\n'.join(f'{key}: {value}'
                                                           for key, value in headers.items()).encode(),
                                               body.encode() if isinstance(body, str) else body)


def generate_chunked_data(fd: BinaryIO, chunk_length: int = 4096):
    chunk = fd.read(chunk_length)

    # it's a hack but anyway, we don't need 0x part
    # there also can not be negative values, so it's ok
    chunk_length_in_hex = hex(chunk_length)[2:].encode() + b'\r\n'

    """
    First, we are rendering current chunk
    Then, we are reading new chunk
    If reading new chunk returned empty string, it means, that already 
    rendered chunk was the last one, so statically counted hex length
    is invalid, that's why we're re-rendering chunk with it's 
    real length
    """

    while chunk:
        prev_chunk, chunk = chunk, fd.read(chunk_length)

        if not chunk:
            # returning last one chunk with it's real length
            # and null chunk to say client that that's it
            # no more beer, get the fuck out

            yield (
                    b'%s\r\n%s\r\n' % (hex(len(prev_chunk))[2:].encode(), prev_chunk) +
                    b'0\r\n\r\n'
            )
            return

        yield b'%s%s\r\n' % (chunk_length_in_hex, chunk)


def parse_params(params: bytes) -> Dict[str, List[str]]:
    """
    Returns dict with params (empty if no params given)

    May raise exceptions: ValueError
    """

    pairs: Dict[str, List] = {}

    for attr in params.split(b'&' if b'&' in params else b';'):
        key, value = attr.decode().split('=', 1)

        if key not in pairs:
            pairs[key] = [value]
        else:
            pairs[key].append(value)

    return pairs


def decode_url(bytestring: bytes) -> bytes:
    bits = bytestring.split(b'%')
    decoded: bytes = bits[0]

    for item in bits[1:]:
        try:
            decoded += HEX_TO_BYTE[item[:2]] + item[2:]
        except KeyError:
            decoded += b'%' + item

    return decoded
