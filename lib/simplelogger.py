"""
Simple own logger, made cause I'm bicycler and I like to write
my own variants of different libraries
"""

from os import mkdir
from sys import stdout
from threading import Thread
from datetime import datetime
from queue import Queue, Empty
from os.path import isfile, dirname


_loggers = {}
DEFAULT_DATE_BLOCK = '[%a, %d %b, %H:%M:%S.%f] '

DEBUG = 0
INFO = 1
WARNING = 2
ERROR = 3
CRITICAL = 4
DISABLE = 10    # maximal level that disables any levels above
LOGLEVELS_STRINGIFIED = (
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
)


class Logger:
    def __new__(cls, name, *args, **kwargs):
        if name in _loggers:
            return _loggers[name]

        instance = object.__new__(cls)
        _loggers[name] = instance

        return instance

    def __init__(self, name, filename=None):
        self.name = name
        self.filename = filename or name + '.log'

        try:
            self.fd = open(self.filename, 'a')
        except FileNotFoundError:
            self.fd = open(self.filename, 'w')

        self.minimal_loglevel = DEBUG
        self.log_entries = Queue()

    def write(self, text, loglevel=DEBUG, time_format=DEFAULT_DATE_BLOCK,
              end='\n'):
        if loglevel < self.minimal_loglevel:
            return

        # legends says that f-strings even faster than usual concatenation
        self.fd.write(f'{datetime.now().strftime(time_format)}[{LOGLEVELS_STRINGIFIED[loglevel]}] '
                      f'{text}{end}')

    def set_log_level(self, new_log_level):
        self.minimal_loglevel = new_log_level

    def stop(self):
        self.fd.close()

    def __del__(self):
        self.stop()
