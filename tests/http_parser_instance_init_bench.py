from timeit import timeit

print(timeit('buff = [HttpParser(decompress=True), b\'\']',
             setup='from http_parser.http import HttpParser',
             number=50_000))
