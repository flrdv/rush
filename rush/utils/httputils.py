from rush.utils.status_codes import status_codes


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}'
                     for key, value in headers.items())\
               .encode()


def render_http_response(protocol: tuple, code: int, status_code: str or None,
                         user_headers: dict, body: str or bytes,
                         exclude_headers=()):
    # default headers
    # TODO: add server-time header
    headers = {
        'Content-Length': len(body),
        'Server': 'rush-webserver',
        'Connection': 'keep-alive',
        **(user_headers or {})
    }

    if exclude_headers:
        map(headers.pop, exclude_headers)

    status_description = status_code or status_codes.get(code, 'NO STATUS CODE')
    protocol = f'HTTP/{".".join(protocol)}'.encode()

    # TODO: in Python 3.11, they promised to make C-style formatting
    #       as fast as f-strings, but only if string is simple (%s, %r, %a).
    #       so don't forget to replace %d with %s (cast status_code to string)

    # I'm not using format_headers() function here just to avoid useless calling
    # as everybody knows, functions' calls are a bit expensive in CPython
    return b'%s %d %s\r\n%s\r\n\r\n%s' % (protocol, code, status_description.encode(),
                                          '\r\n'.join(f'{key.lower()}: {value}'
                                                      for key, value in headers.items())
                                                .encode(),
                                          body if isinstance(body, bytes) else body.encode())


def render_http_request(method: bytes, path: str, protocol: tuple,
                        headers: dict, body: bytes):
    if b'content-length' not in headers:
        headers[b'content-length'] = len(body)

    protocol = f'HTTP/{".".join(protocol)}'.encode()

    return b'%s %s %s\r\n%s\r\n\r\n%s' % (method, path.encode(), protocol,
                                          '\r\n'.join(f'{key.decode().lower()}: {value.decode()}'
                                                      for key, value in headers.items()).encode(),
                                          body)


def parse_params(params):
    """
    Returns dict with params (empty if no params given)
    """

    pairs = {}

    for attr in params.split(b'&' if b'&' in params else b';'):
        key, value = attr.decode().split('=')

        if key not in pairs:
            pairs[key] = [value]
        else:
            pairs[key].append(value)

    return pairs


_hexdig = '0123456789ABCDEFabcdef'
_hextobyte = {(a + b).encode(): bytes.fromhex(a + b)
              for a in _hexdig for b in _hexdig}


def decode_url(bytestring):
    if b'%' not in bytestring:
        return bytestring

    bits = bytestring.split(b'%')
    decoded: bytes = bits[0]

    for item in bits[1:]:
        try:
            decoded += _hextobyte[item[:2]] + item[2:]
        except KeyError:
            decoded += b'%' + item

    return decoded
