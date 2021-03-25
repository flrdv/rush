import re


class Filter:
    """
    Contains dict-sample and checks incoming request with dict-sample
    """

    def __init__(self, sample):
        self.sample = sample

    def __call__(self, request: 'Request'):
        return compare_filters(self.sample, request)


class Request:
    def __init__(self, typeof, path,
                 protocol, headers, body):
        self.type = typeof
        self.path = path
        self.protocol = protocol
        self.headers = headers
        self.body = body

    def get_values(self):
        return {**self.headers, 'body': self.body}

    def __str__(self):
        headers = '\n'.join((f'{key}={repr(value)}' for key, value in self.headers.items()))

        return f"""{self.type} {self.path} {self.protocol}
{headers}

{self.body or ''}"""

    __repr__ = __str__


def compare_filters(pattern: dict, source: Request):
    source_items = source.get_values().items()

    for key, value in pattern.items():
        for source_key, source_value in source_items:
            if re.fullmatch(key, source_key):
                if source_value is None or re.fullmatch(value, source_value):
                    break
        else:
            return False

    return True


def test_comparing():
    pattern = {"path": r"\w+/ok"}
    source1 = Request('get', None, None, {
        "path": 'ok/neok',
        "wow": "no"
    }, None)
    source2 = Request('get', None, None, {
        "path": "ok/ok"
    }, None)

    assert compare_filters(pattern, source1) is False
    assert compare_filters(pattern, source2) is True

    print('Comparing request with pattern works fine')


if __name__ == '__main__':
    test_comparing()
