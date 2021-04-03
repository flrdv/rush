from time import time
from os.path import isfile


def benchmark(name=None, logfile='benchmark.log'):
    def decorator(func):
        def wrapper(*args, **kwargs):
            begin = time()
            func(*args, **kwargs)
            end = time()
            write_results(f'{name or func.__name__}: {(end - begin) * 1000} ms', logfile)

        return wrapper

    return decorator


def write_results(results, logfile):
    if not isfile(logfile):
        mode = 'w'
    else:
        mode = 'a'

    with open(logfile, mode) as fd:
        fd.write(results + '\n')
