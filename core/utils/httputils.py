from utils.status_codes import status_codes


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
