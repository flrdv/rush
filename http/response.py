class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def __str__(self):
        return f'{self.status}\r\n{self.headers}\r\n\r\n{self.body}'

    def __bytes__(self):
        return str(self).encode()

    __repr__ = __str__
