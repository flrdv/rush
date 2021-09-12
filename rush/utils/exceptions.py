class RushException(Exception):
    """
    Basic exception
    """

    pass


class NotFoundError(RushException):
    """
    Exception that is being raised in handlers when some file was not found.
    Mostly raising in loader, but also can be raised for a special by user
    """

    pass


class InvalidURLError(RushException):
    """
    Exception that is being raised if requesting url is invalid
    """
