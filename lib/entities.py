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
    def __init__(self, values):
        self.values = values

    def get_values(self):
        return self.values

    def __getattr__(self, item):
        return object.__getattribute__(self, 'values')[item]

    def __getitem__(self, item):
        return self.values[item]

    def __str__(self):
        values = ', '.join(f'{var}={repr(val)}' for var, val in self.values.items())

        return f'Request({values})'

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
    source1 = Request({
        "path": 'ok/neok',
        "wow": "no"
    })
    source2 = Request({
        "path": "ok/ok"
    })

    assert compare_filters(pattern, source1) is False
    assert compare_filters(pattern, source2) is True

    print('Comparing request with pattern works fine')


if __name__ == '__main__':
    test_comparing()
