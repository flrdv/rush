"""
Contains all the functions from utils.entities. Used to match it's name

Contains webserver-specific functions, but also user-used
"""

from utils.status_codes import status_codes


def response(protocol, code, body=None,
             status_code_desc=None, headers=None,
             content_type=None):
    # default headers
    final_headers = {
        'Content-Length': len(body),
        'Server': 'rush',
        'Content-Type': content_type or 'text/html',
        'Connection': 'keep-alive'
    }
    final_headers.update(headers or {})
    body = body if isinstance(body, bytes) else body.encode()

    # building time
    status_description = status_code_desc or status_codes.get(code, 'UNKNOWN')
    content = b'%s %d %s\r\n%s\r\n\r\n%s' % (protocol.encode(), code, status_description.encode(),
                                             format_headers(final_headers), body)

    return content


def get_handler(handlers, request, return_otherwise=None):
    for handler, handler_filter in handlers.items():
        if handler_filter(request):
            return handler

    return return_otherwise


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}' for key, value in headers.items()).encode()
