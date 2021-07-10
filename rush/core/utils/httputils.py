import re

from rush.utils.status_codes import status_codes


def render_http_response(protocol, status_code, status_code_desc,
                         user_headers, body):
    # default headers
    # TODO: add server-time header
    headers = {
        'Content-Length': len(body),
        'Server': 'rush-webserver',
        'Connection': 'keep-alive',
        **(user_headers or {})
    }
    status_description = status_code_desc or status_codes.get(status_code, 'NO DESCRIPTION')
    protocol = f'HTTP/{".".join(protocol)}'.encode()

    # TODO: in Python 3.11, they promised to make C-style formatting
    #       as fast as f-strings, but only if string is simple (%s, %r, %a).
    #       so don't forget to replace %d with %s (cast status_code to string)
    return b'%s %d %s\r\n%s\r\n\r\n%s' % (protocol, status_code,
                                          status_description.encode(),
                                          '\r\n'.join(f'{key}: {value}' for key, value in headers.items()).encode(),
                                          body if isinstance(body, bytes) else body.encode())


# just if somebody will need this
def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}' for key, value in headers.items()).encode()


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
