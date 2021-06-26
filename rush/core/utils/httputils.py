import re

from rush.utils.status_codes import status_codes


def render_http_response(protocol, status_code, status_code_desc,
                         headers, body):
    # default headers
    # TODO: add server-time header
    final_headers = {
        'Content-Length': len(body),
        'Server': 'rush-webserver',
        'Connection': 'keep-alive'
    }
    final_headers.update(headers or {})
    body = body if isinstance(body, bytes) else body.encode()

    # building time
    status_description = status_code_desc or status_codes.get(status_code, 'NO DESCRIPTION')

    return b'%s %d %s\r\n%s\r\n\r\n%s' % (b'HTTP/%i.%i' % protocol, status_code,
                                          status_description.encode(),
                                          format_headers(final_headers), body)


def format_headers(headers: dict):
    return '\n'.join(f'{key}: {value}' for key, value in headers.items()).encode()


"""
There will be a part from urllib.parse with some changes
"""

_hexdig = '0123456789ABCDEFabcdef'
_hextobyte = None


def _noop(obj):
    return obj


def _decode_args(args, encoding='ascii',
                 errors='strict'):
    return tuple(x.decode(encoding, errors) if x else '' for x in args)


def _encode_result(obj, encoding='ascii',
                   errors='strict'):
    return obj.encode(encoding, errors)


def _coerce_args(*args):
    # Invokes decode if necessary to create str args
    # and returns the coerced inputs along with
    # an appropriate result coercion function
    #   - noop for str inputs
    #   - encoding function otherwise
    if isinstance(args[0], str):
        return args + (_noop,)
    return _decode_args(args) + (_encode_result,)


def parse_qs(qs, keep_blank_values=False, strict_parsing=False,
             encoding='utf-8', errors='replace', max_num_fields=None, separator='&'):
    return dict(parse_qsl(qs, keep_blank_values, strict_parsing,
                          encoding=encoding, errors=errors,
                          max_num_fields=max_num_fields, separator=separator))


def unquote_to_bytes(string):
    """unquote_to_bytes('abc%20def') -> b'abc def'."""
    # Note: strings are encoded as UTF-8. This is only an issue if it contains
    # unescaped non-ASCII characters, which URIs should not.
    if not string:
        return b''
    if isinstance(string, str):
        string = string.encode('utf-8')
    bits = string.split(b'%')
    if len(bits) == 1:
        return string
    res = [bits[0]]
    append = res.append
    # Delay the initialization of the table to not waste memory
    # if the function is never called
    global _hextobyte
    if _hextobyte is None:
        _hextobyte = {(a + b).encode(): bytes.fromhex(a + b)
                      for a in _hexdig for b in _hexdig}
    for item in bits[1:]:
        try:
            append(_hextobyte[item[:2]])
            append(item[2:])
        except KeyError:
            append(b'%')
            append(item)
    return b''.join(res)


_asciire = re.compile('([\x00-\x7f]+)')


def unquote(string, encoding='utf-8', errors='replace'):
    if isinstance(string, bytes):
        return unquote_to_bytes(string).decode(encoding, errors)
    if '%' not in string:
        return string
    bits = _asciire.split(string)
    res = [bits[0]]
    append = res.append
    for i in range(1, len(bits), 2):
        append(unquote_to_bytes(bits[i]).decode(encoding, errors))
        append(bits[i + 1])
    return ''.join(res)


def parse_qsl(qs, keep_blank_values=False, strict_parsing=False,
              encoding='utf-8', errors='replace', max_num_fields=None, separator='&'):
    qs, _coerce_result = _coerce_args(qs)
    separator, _ = _coerce_args(separator)
    r = []
    for name_value in qs.split(separator):
        if not name_value and not strict_parsing:
            continue
        nv = name_value.split('=', 1)
        if len(nv) != 2:
            if strict_parsing:
                raise ValueError("bad query field: %r" % (name_value,))
            # Handle case of a control-name with no equal sign
            if keep_blank_values:
                nv.append('')
            else:
                continue
        if len(nv[1]) or keep_blank_values:
            name = nv[0].replace('+', ' ')
            name = unquote(name, encoding=encoding, errors=errors)
            name = _coerce_result(name)
            value = nv[1].replace('+', ' ')
            value = unquote(value, encoding=encoding, errors=errors)
            value = _coerce_result(value)
            r.append((name, value))
    return r


"""
Some part from urllib.parse has been ended
"""

