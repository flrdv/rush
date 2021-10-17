class WebServerException(Exception):
    pass


class FileNotCachedError(WebServerException):
    pass


class HTTP404(WebServerException):
    pass
