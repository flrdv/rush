import timeit

setup = """
import core.utils.httputils as parser
"""

print(timeit.timeit("queries ='/hello?name=bill'.split('?')[1]\nparser.parse_qs(queries)",
                    setup=setup, number=100_000))
