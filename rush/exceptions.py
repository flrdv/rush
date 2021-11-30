class WebServerError(Exception):
    pass


class FileNotCachedError(WebServerError):
    pass


class HandlerMustBeCoroutineError(WebServerError):
    pass


class NoMethodsProvided(WebServerError):
    pass


class HTTPError(Exception):
    def __init__(self,
                 request,
                 **kwargs):
        self.request = request

        # an additional stash for dynamic values
        # not very good choice, but may be useful in some cases
        for key, value in kwargs.items():
            setattr(self, key, value)

        super(HTTPError, self).__init__(kwargs.get('msg', ''))


class HTTPBadRequest(HTTPError):
    code = 400
    description = b'Bad Request'


class HTTPUnauthorized(HTTPError):
    code = 401
    description = b'Unauthorized'
    user = None


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
    proxy = None


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
    expected = None


class HTTPInternalServerError(HTTPError):
    code = 500
    description = b'Internal Server Error'
    traceback = None


class HTTPNotImplemented(HTTPError):
    code = 501
    description = b'Not Implemented'
    details = None


class HTTPBadGateway(HTTPError):
    code = 502
    description = b'Bad Gateway'


class HTTPServiceUnavailable(HTTPError):
    code = 503
    description = b'Service Unavailable'
    service = None


class HTTPGatewayTimeout(HTTPError):
    code = 504
    description = b'Gateway Timeout'


class HTTPHTTPVersionNotSupported(HTTPError):
    code = 505
    description = b'HTTP Version Not Supported'
    requested_version = None
    supported_version = b'1.1'
