import logging
import mimetypes
from os import SEEK_END
from threading import Thread
from traceback import format_exc

import inotify.adapters
from inotify.calls import InotifyError

from .httputils import render_http_response

# disable inotify logs cause they're useless
logging.getLogger('inotify.adapters').disabled = True

logger = logging.getLogger(__name__)


def _file_length_from_fd(fd, seek_to_begin=False):
    fd.seek(0, SEEK_END)

    if seek_to_begin:
        length = fd.tell()
        fd.seek(0)

        return length

    return fd.tell()


def _render_headers(filename, content_length, include_content_length_header=True):
    mime, encoding = mimetypes.guess_type(filename)

    if mime is None:
        mime = 'application/octet-stream'

    headers = {
        'Content-Length': content_length,
        'Content-Type': mime,
    }

    if encoding is not None:
        headers['Content-Encoding'] = encoding

    return render_http_response(protocol=('1', '1'),
                                code=200,
                                status_code='OK',
                                user_headers=headers,
                                body=b'',
                                exclude_headers=('Content-Length',)
                                if not include_content_length_header
                                else ())


class InMemoryCache:
    """
    Keeps file content in memory, updates it in the separated thread if file modifies

    Has good latency and a lot of RPS, the best choice for multi-processed configurations.
    But has high memory consumption: it loads files to the memory, in every process
    """

    def __init__(self):
        self.inotify = inotify.adapters.Inotify()

        self.cached_files = {}  # full_file_name: (headers, content)
        self.get_file = self.cached_files.get

        self.cached_responses_headers = {}

        self._running = True

    def _events_listener(self):
        print('lollll')

        while self._running:
            for event in self.inotify.event_gen(yield_nones=False, timeout_s=.5):
                # otherwise, previous line could be much more longer than it should
                _, event_types, file, _ = event

                print('received events:', event_types)

                if 'IN_MODIFY' in event_types:
                    internal_filename = '/' + file.lstrip('/')

                    with open(file, 'rb') as fd:
                        self.cached_files[internal_filename] = fd.read()
                        self.cached_responses_headers[internal_filename] = _render_headers(internal_filename,
                                                                                           _file_length_from_fd(fd))

                    logger.info(f'InMemoryCache: updated file "{file}"')

        print('wait what the fuck?')

    def add_file(self, path_to_file):
        with open(path_to_file, 'rb') as fd:
            self.cached_files[path_to_file] = fd.read()

        try:
            self.inotify.add_watch(path_to_file)
            logger.debug(f'InMemoryCache: watching file: {path_to_file}')
        except InotifyError as exc:
            logger.error(f'InMemoryCache: failed to start watching file {path_to_file}: {exc}')
            logger.exception(f'\nFull traceback:\n{format_exc()}')

    """
    Here was get() method. I replaced it with lookup in __init__ to avoid useless
    methods proxying
    """

    def add_response(self, filename):
        """
        This is slow function, but works only once
        """

        if filename not in self.cached_files:
            self.add_file(filename)

        response_file = self.cached_files[filename]
        rendered_http_headers = _render_headers(filename, len(response_file))
        self.cached_responses_headers[filename] = rendered_http_headers

        return rendered_http_headers + response_file

    def send_response(self, http_send, conn, filename) -> None:
        if filename not in self.cached_files:
            self.add_file(filename)
        if filename not in self.cached_responses_headers:
            return http_send(conn, self.add_response(filename))

        http_send(conn,
                  self.cached_responses_headers[filename] +
                  self.cached_files[filename])

    def start(self):
        Thread(target=self._events_listener).start()

    def __del__(self):
        self._running = False


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
        content_length = len(content)
        rendered_headers = _render_headers(filename, content_length,
                                           include_content_length_header=False)
        self.responses[filename] = rendered_headers[:-2]

        return rendered_headers[:-2] + (b'Content-Length: %d\r\n\r\n' % content_length) + content

    def send_response(self, http_send, conn, filename):
        if filename not in self.files:
            self.add_file(filename)
        if filename not in self.responses:
            return http_send(conn, self.add_response(filename))

        fd = self.files[filename]
        response_headers = self.responses[filename] + (b'Content-Length: %d\r\n\r\n' %
                                                       _file_length_from_fd(fd, True))

        return http_send(conn, response_headers + self.get_file(filename))

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
        self.headers = {}  # filename: rendered http headers (without content-length)

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
            self.add_file(filename)
        if filename not in self.headers:
            return http_send(conn, self.add_response(filename))

        fd = self.files_descriptors[filename]
        conn.send(self.headers[filename] +
                  b'Content-Length: %d\r\n\r\n' % _file_length_from_fd(fd))
        conn.setblocking(1)
        conn.sendfile(fd)
        conn.setblocking(0)

    def add_response(self, filename):
        if filename not in self.files_descriptors:
            self.add_file(filename)

        fd = self.files_descriptors[filename]
        content_length = _file_length_from_fd(fd, seek_to_begin=True)
        rendered_headers = _render_headers(filename, content_length,
                                           include_content_length_header=False)[:-2]
        self.headers[filename] = rendered_headers

        # what's going on here? It's a shit code. Cause of specific
        # of current caching implementation, I cannot use static headers
        # for all. So, I just render headers without content-length header,
        # and just adding new value to static headers each time I response
        return rendered_headers + (b'Content-Length: %d\r\n\r\n' % content_length) + fd.read()

    def __del__(self):
        for fd in self.files_descriptors:
            fd.close()
