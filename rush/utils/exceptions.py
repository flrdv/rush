class RushException(Exception):
    """
    Basic exception
    """

    pass


class NotFound(RushException):
    """
    Exception that is being raised in handlers when some file was not found.
    Mostly raising in loader, but also can be raised for a special by user
    """

    pass


class InvalidURL(RushException):
    """
    Exception that is being raised if requesting url is invalid
    """
