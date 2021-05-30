"""
Simple own logger, made cause I'm bicycler and I like to write
my own variants of different libraries
"""

from sys import stdout
from threading import Thread
from datetime import datetime
from os import path, makedirs
from queue import Queue, Empty
from os.path import isfile, dirname


_loggers = {}
DEFAULT_DATE_BLOCK = '[%a, %d %b, %H:%M:%S.%f] '

ALL = 0
DEBUG = 1
INFO = 2
WARNING = 3
ERROR = 4
CRITICAL = 5
DISABLE = 999    # maximal level that disables any levels above
LOGLEVELS_STRINGIFIED = (
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
)

global_log_level = ALL


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
            file_dirname = path.dirname(self.filename)

            if file_dirname and not path.isdir(file_dirname):
                makedirs(file_dirname)

            self.fd = open(self.filename, 'w')

        self.minimal_loglevel = global_log_level
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
