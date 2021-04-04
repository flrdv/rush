"""
Simple own logger, made cause I'm bicycler and I like to write
my own variants of different libraries
"""

from sys import stdout
from os.path import isfile
from threading import Thread
from datetime import datetime
from queue import Queue, Empty


_loggers = {}
DEFAULT_DATE_BLOCK = '[%a, %d %b, %H:%M:%S.%f] '

DEBUG = 0
INFO = 1
WARNING = 2
ERROR = 3
CRITICAL = 4
LOGLEVERS_STRINGIFIED = (
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

    def __init__(self, name, files=(), also_stdout=True,
                 keep_files_opened=True):
        self.name = name
        self.filenames = files or (name + '.log',)
        self.keep_files_opened = keep_files_opened
        self.stdout_included = also_stdout
        self.fds = self.get_fds() if keep_files_opened else []
        self.loglevel = DEBUG

        if also_stdout:
            self.fds.append(stdout)

        self.log_entries = Queue()

        self._active = True
        Thread(target=self.writer).start()

    def get_fds(self):
        fds = []

        for filename in self.filenames:
            if not isfile(filename):
                mode = 'w'
            else:
                mode = 'a'

            fds.append(open(filename, mode))

        return fds

    def close_fds(self, fds):
        return map(lambda fd: fd.close(), fds)

    def writer(self):
        while self._active:
            try:
                time_block, text, end, to_stdout = self.log_entries.get(timeout=1)
                curr_time = datetime.now()
            except Empty:
                continue

            formatted_log_entry = curr_time.strftime(time_block) + text + end

            if self.keep_files_opened:
                fds = self.fds
            else:
                fds = self.get_fds()

            for fd in fds:
                fd.write(formatted_log_entry)
                fd.flush()

            if to_stdout and not self.stdout_included:
                stdout.write(formatted_log_entry)
                stdout.flush()

            if not self.keep_files_opened:
                self.close_fds(fds)

    def write(self, loglevel, text, time_format=DEFAULT_DATE_BLOCK,
              end='\n', to_stdout=False):
        if loglevel < self.loglevel:
            return

        text = '[' + LOGLEVERS_STRINGIFIED[loglevel] + '] ' + text

        self.log_entries.put((time_format, text, end, to_stdout))

    def set_log_level(self, log_level):
        self.loglevel = log_level

    def stop(self):
        self._active = False
        self.close_fds(self.fds)

    def __del__(self):
        self.stop()
