class WebServerException(Exception):
    pass


class FileNotCachedError(WebServerException):
    pass


class HTTPError(Exception):
    pass


class HTTPBadRequest(HTTPError):
    code = 400
    description = b'Bad Request'


class HTTPUnauthorized(HTTPError):
    code = 401
    description = b'Unauthorized'


class HTTPPaymentRequired(HTTPError):
    code = 402
    description = b'Payment Required'


class HTTPForbidden(HTTPError):
    code = 403
    description = b'Forbidden'


class HTTPNotFound(HTTPError):
    code = 404
    description = b'Not Found'


class HTTPMethodNotAllowed(HTTPError):
    code = 405
    description = b'Method Not Allowed'


class HTTPNotAcceptable(HTTPError):
    code = 406
    description = b'Not Acceptable'


class HTTPProxyAuthenticationRequired(HTTPError):
    code = 407
    description = b'Proxy Authentication Required'


class HTTPRequestTimeout(HTTPError):
    code = 408
    description = b'Request Timeout'


class HTTPConflict(HTTPError):
    code = 409
    description = b'Conflict'


class HTTPGone(HTTPError):
    code = 410
    description = b'Gone'


class HTTPLengthRequired(HTTPError):
    code = 411
    description = b'Length Required'


class HTTPPreconditionFailed(HTTPError):
    code = 412
    description = b'Precondition Failed'


class HTTPRequestEntityTooLarge(HTTPError):
    code = 413
    description = b'Request Entity Too Large'


class HTTPURITooLong(HTTPError):
    code = 414
    description = b'Request-URI Too Long'


class HTTPUnsupportedMediaType(HTTPError):
    code = 415
    description = b'Unsupported Media Type'


class HTTPRequestedRangeNotSatisfiable(HTTPError):
    code = 416
    description = b'Requested Range Not Satisfiable'


class HTTPExpectationFailed(HTTPError):
    code = 417
    description = b'Expectation Failed'


class HTTPInternalServerError(HTTPError):
    code = 500
    description = b'Internal Server Error'


class HTTPNotImplemented(HTTPError):
    code = 501
    description = b'Not Implemented'


class HTTPBadGateway(HTTPError):
    code = 502
    description = b'Bad Gateway'


class HTTPServiceUnavailable(HTTPError):
    code = 503
    description = b'Service Unavailable'


class HTTPGatewayTimeout(HTTPError):
    code = 504
    description = b'Gateway Timeout'


class HTTPHTTPVersionNotSupported(HTTPError):
    code = 505
    description = b'HTTP Version Not Supported'
