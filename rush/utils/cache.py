import os
import logging
from os import SEEK_END
from threading import Thread
from traceback import format_exc

import inotify.adapters
from inotify.calls import InotifyError
from inotify.constants import IN_MODIFY

from rush.core.utils.httputils import render_http_response

logger = logging.getLogger(__name__)


class InMemoryCache:
    """
    Keeps file content in memory, updates it in the separated thread if file modifies

    Has good latency and a lot of RPS, the best choice for multi-processed configurations.
    But has high memory consumption: it loads files to the memory, in every process
    """

    def __init__(self):
        self.inotify = inotify.adapters.Inotify()

        self.cached_files = {}
        self.get_file = self.cached_files.get

        self.cached_responses_headers = {}

    def _events_listener(self):
        for event in self.inotify.event_gen(yield_nones=False):
            _, event_types, path, filename = event

            if IN_MODIFY in event_types:
                file_path = os.path.join(path, filename)

                with open(file_path, 'rb') as fd:
                    self.cached_files[file_path] = fd.read()

                logger.info(f'cache: updated file PATH={path} FILENAME={filename}')

    def add_file(self, path_to_file):
        with open(path_to_file, 'rb') as fd:
            self.cached_files[path_to_file] = fd.read()

        try:
            self.inotify.add_watch(path_to_file)
        except InotifyError as exc:
            logger.error(f'failed to start watching file {path_to_file}: {exc}'
                         f'\nFull traceback:\n{format_exc()}')

    """
    Here was get() method. I replaced it with lookup in __init__ to avoid useless
    methods proxying
    """

    def add_response(self, filename):
        if filename not in self.cached_files:
            self.add_file(filename)

        response_file = self.cached_files[filename]
        response_headers = render_http_response(('1', '1'), 200, 'OK',
                                                {'Content-Length': len(response_file)}, b'')
        self.cached_responses_headers[filename] = response_headers

        return response_headers + response_file

    def send_response(self, http_send, conn, filename) -> bytes or None:
        if filename not in self.cached_files:
            self.add_file(filename)
        if filename not in self.cached_responses_headers:
            return http_send(conn, self.add_response(filename))

        http_send(conn,
                  self.cached_responses_headers[filename] +
                  self.cached_files[filename])

    def start(self):
        Thread(target=self._events_listener).start()


class FsCache:
    """
    Class that opens files for reading in the beginning, then reads and
    returns content when there is a need to send a response

    Has very good latency (in my tests, there was up to 0.075 ms average
    response time) and very low memory consumption, but web-server works
    with RPS of single-processed config. The best choice is to use it with
    configured processes count of PHYSICAL (not LOGICAL) cores
    (processes=None automatically set processes count to logical cores count)
    """

    def __init__(self):
        self.files = {}  # name: fd
        self.responses = {}  # filename: headers

        self.start = lambda: 'ok'

    def add_file(self, filename):
        self.files[filename] = open(filename, 'rb')

    def get_file(self, filename):
        fd = self.files[filename]
        content = fd.read()
        fd.seek(0)

        return content

    def add_response(self, filename):
        if filename not in self.files:
            self.add_file(filename)

        content = self.get_file(filename)
        response_headers = render_http_response(('1', '1'), 200, 'OK',
                                                {'Content-Length': len(content)},
                                                b'')
        self.responses[filename] = response_headers

        return response_headers + content

    def send_response(self, http_send, conn, filename):
        if filename not in self.files:
            self.add_file(filename)
        if filename not in self.responses:
            return http_send(conn, self.add_response(filename))

        return http_send(conn, self.responses[filename] + self.get_file(filename))

    def __del__(self):
        for fd in self.files:
            fd.close()


class FdCache:
    """
    Works all the same as FsCache, but instead of reading from fd to socket,
    calling `socket.socket.sendfile` to directly copy from fd to socket in
    kernel-space

    Gives bad latency against FsCache and InMemoryCache, also ~2x slower
    than InMemoryCache, but has all the same memory consumption as a
    FsCache
    """

    def __init__(self):
        self.files_descriptors = {}  # filename: fd (in read-mode)
        self.headers = {}  # filename: rendered http headers

        self.start = lambda: 'ladno'

    def add_file(self, filename):
        if filename in self.files_descriptors:
            raise FileExistsError

        self.files_descriptors[filename] = open(filename, 'rb')

    def get_file(self, filename):
        """
        Shouldn't be used, but made for cases when some stupid person will
        try to get file content from cache
        """

        fd = self.files_descriptors[filename]
        fd.seek(0)
        content = fd.read()

        return content

    def send_response(self, http_send, conn, filename):
        if filename not in self.files_descriptors:
            self.add_response(filename)
        if filename not in self.headers:
            return http_send(conn, self.add_response(filename))

        conn.send(self.headers[filename])
        conn.setblocking(1)
        conn.sendfile(self.files_descriptors[filename])
        conn.setblocking(0)

    def add_response(self, filename):
        if filename not in self.files_descriptors:
            self.add_file(filename)

        fd = self.files_descriptors[filename]
        fd.seek(0, SEEK_END)    # we'll need that for rendering correct response

        headers = render_http_response(('1', '1'), 200, 'OK',
                                       {'Content-Length': fd.tell()},
                                       b'')
        self.headers[filename] = headers
        fd.seek(0)

        return headers + fd.read()

    def __del__(self):
        for fd in self.files_descriptors:
            fd.close()
