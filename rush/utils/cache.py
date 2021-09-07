import socket
import logging
import mimetypes
from threading import Thread
from traceback import format_exc
import os
from os.path import basename
from os import sendfile, SEEK_END
from typing import Union, Dict, Tuple, BinaryIO

import inotify.adapters
from inotify.calls import InotifyError

from ..core.httpserver import HttpServer  # just for type hint in Cache class
from .httputils import render_http_response, generate_chunked_data

# disable inotify logs cause they're useless
logging.getLogger('inotify.adapters').disabled = True

logger = logging.getLogger(__name__)


def _file_length_from_fd(fd, seek_to_begin=False) -> int:
    fd.seek(0, SEEK_END)

    if seek_to_begin:
        length = fd.tell()
        fd.seek(0)

        return length

    return fd.tell()


def _render_static_file_headers(filename, content_length,
                                exclude_headers=(),
                                chunked_transmission=False,
                                user_headers=None) -> bytes:
    mime, encoding = mimetypes.guess_type(filename)

    if mime is None:
        mime = 'application/octet-stream'

    headers = {
        'Content-Type': mime,
        **(user_headers or {})
    }

    if encoding is not None:
        headers['Content-Encoding'] = encoding

    if chunked_transmission:
        headers['Transfer-Encoding'] = 'chunked'

    if content_length is not None:
        headers['Content-Length'] = content_length

    return render_http_response(protocol='1.1',
                                code=200,
                                status_code='OK',
                                user_headers=headers,
                                body=b'',
                                exclude_headers=exclude_headers,
                                auto_content_length=False)


def _sendfile(out_fd, in_fd, offset, length):
    sent = sendfile(out_fd, in_fd, offset, length)

    if sent == length:
        return

    while sent != 0:
        sent = sendfile(out_fd, in_fd, offset, length)


class Cache:
    """
    The base class for all cache implementations
    """

    def add_file(self,
                 filename: str,
                 headers: Union[dict, None] = None
                 ):
        """
        Adds file to cache. Filename should be absolute path
        """
        ...

    def get_file(self, filename: str):
        """
        This method isn't used internally, but created to just exist
        in case of user will need to get a content of file
        """
        ...

    def send_file(self,
                  http_send: 'HttpServer.send',
                  conn: 'socket.socket',
                  filename: str,
                  headers: Union[dict, None] = None
                  ):
        """
        Receives function for pushing bytes string to http server,
        connection with user, absolute path to file that needs to
        be send to user, and additional headers

        If custom headers are given, headers are re-rendering
        """
        ...

    def start(self):
        """
        Function that is being called after initialization caching implementation's
        object. May start a thread, do some calculations, or nothing at all
        """
        ...

    def close(self):
        """
        For example, when server is shutting down, this method will be called
        """
        ...


class InMemoryCache(Cache):
    """
    Keeps file content in memory, updates it in the separated thread if file modifies

    Has good latency and a lot of RPS, the best choice for multi-processed configurations.
    But has high memory consumption: it loads files to the memory, in every process
    """

    def __init__(self):
        self.inotify = inotify.adapters.Inotify()

        self.cached_files: Dict[str, bytes] = {}  # full_file_name: rendered_content
        # original, non-rendered headers for each file,
        # their rendered length and total content length
        self.headers: Dict[str, Tuple[dict, int, int]] = {}

        self._running = True

    def _events_listener(self):
        while self._running:
            for event in self.inotify.event_gen(yield_nones=False, timeout_s=.5):
                # otherwise, previous line could be much more longer than it should
                _, event_types, file, _ = event

                if 'IN_MODIFY' in event_types:
                    internal_filename = '/' + file.lstrip('/')

                    with open(file, 'rb') as fd:
                        new_content = fd.read()
                        rendered_headers = _render_static_file_headers(internal_filename, fd.tell())
                        self.cached_files[file] = rendered_headers + new_content

                    logger.info(f'InMemoryCache: updated file "{file}"')

    def add_file(self,
                 filename: str,
                 headers: Union[dict, None] = None
                 ):
        with open(filename, 'rb') as fd:
            content = fd.read()

        content_length = len(content)
        rendered_headers = _render_static_file_headers(filename,
                                                       content_length=content_length,
                                                       user_headers=headers)

        self.cached_files[filename] = rendered_headers + content
        self.headers[filename] = (headers or {}, content_length, len(rendered_headers))

        try:
            self.inotify.add_watch(filename)
            logger.debug(f'InMemoryCache: watching file: {filename}')
        except InotifyError as exc:
            logger.error(f'InMemoryCache: failed to start watching file {filename}: {exc}')
            logger.exception(f'detailed error trace:\n{format_exc()}')

    def get_file(self, filename: str):
        _, _, body_offset = self.headers[filename]

        return self.cached_files[filename][body_offset:]

    def send_file(self,
                  http_send,
                  conn,
                  filename: str,
                  headers=None
                  ) -> None:
        if filename not in self.cached_files:
            self.add_file(filename, headers=headers)
        elif headers:
            original, body_offset, content_length = self.headers[filename]
            rendered_headers = _render_static_file_headers(filename,
                                                           content_length,
                                                           user_headers={
                                                               **original, **headers
                                                           })
            return http_send(conn, rendered_headers + self.cached_files[filename][body_offset:])

        http_send(conn, self.cached_files[filename])

    def start(self):
        Thread(target=self._events_listener).start()

    def close(self):
        self._running = False
        self.headers.clear()
        self.cached_files.clear()

    def __del__(self):
        self.close()


class DescriptorsCache(Cache):
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
        # filename: original headers and rendered headers
        self.headers: Dict[str, Tuple[dict, bytes]] = {}

        self.start = lambda: 'ok'

    def add_file(self,
                 filename: str,
                 headers: Union[dict, None] = None
                 ):
        fd = open(filename, 'rb')
        self.files[filename] = fd
        rendered_headers = _render_static_file_headers(filename,
                                                       content_length=None,
                                                       chunked_transmission=True,
                                                       user_headers=headers)
        self.headers[filename] = (headers or {}, rendered_headers)

    def get_file(self, filename):
        fd = self.files[filename]
        content = fd.read()
        fd.seek(0)

        return content

    def send_file(self,
                  http_send: 'HttpServer.send',
                  conn: 'socket.socket',
                  filename: str,
                  headers: Union[dict, None] = None
                  ):
        if filename not in self.files:
            self.add_file(filename)

        """
        Sending headers first
        """

        if headers:
            # _, origin_headers, body_offset, content_length = self.headers[filename]
            rendered_headers = _render_static_file_headers(filename,
                                                           content_length=None,
                                                           chunked_transmission=True,
                                                           user_headers={
                                                               **self.headers[filename][0],
                                                               **headers
                                                           })
            http_send(conn, rendered_headers)
        else:
            http_send(conn, self.headers[filename][1])

        """
        TODO: after Rush will be asynchronous, do not forget to 
              add more async-optimized chunked transfer
        """

        fd = self.files[filename]
        fd.seek(0)

        for chunk in generate_chunked_data(fd):
            http_send(conn, chunk)

    def close(self):
        self.headers.clear()

        for fd in self.files:
            fd.close()

    def __del__(self):
        self.close()


class FileSystemCache(Cache):
    """
    All the added files, turning into transmission-ready temporary
    files, and using sendfile() for delivering them to users. So,
    it works similar to InMemoryCache, but instead of keeping files
    in memory, we are keeping them in file system, ready to be sent
    to network stack of os
    """

    def __init__(self):
        # filename: (read-only fd of source, length of content)
        self.original_descriptors: Dict[str, Tuple[BinaryIO, int]] = {}
        # filename: (fd, length of all the content)
        self.temporary_descriptors: Dict[str, Tuple[BinaryIO, int]] = {}
        # filename: default headers
        self.headers: Dict[str, dict] = {}

        self.start = lambda: 'ladno'

        if not os.path.exists('.cache'):
            os.mkdir('.cache')

        self.inotify = inotify.adapters.Inotify()

        self._running = True

    def _events_listener(self):
        while self._running:
            for event in self.inotify.event_gen(yield_nones=False, timeout_s=2):
                # otherwise, previous line could be much more longer than it should
                _, event_types, file, _ = event

                if 'IN_MODIFY' in event_types:
                    internal_filename = '/' + file.lstrip('/')
                    origin_fd, _ = self.original_descriptors[internal_filename]
                    origin_fd_len = _file_length_from_fd(origin_fd)
                    copy_fd, _ = self.temporary_descriptors[internal_filename]
                    copy_fd.seek(0)
                    copy_fd.write(
                        _render_static_file_headers(
                            internal_filename,
                            origin_fd_len,
                            user_headers=self.headers[internal_filename]
                        )
                    )
                    _sendfile(copy_fd.fileno(), origin_fd.fileno(), 0, origin_fd_len)
                    # remove everything else in cases that new content is shorter
                    # than it was before
                    copy_fd.truncate()
                    self.original_descriptors[internal_filename] = (origin_fd, origin_fd_len)
                    self.temporary_descriptors[internal_filename] = (copy_fd, copy_fd.tell())

                    logger.info(f'FileSystemCache: updated file "{file}"')

    def add_file(self,
                 filename: str,
                 headers: Union[dict, None] = None
                 ):
        if filename in self.original_descriptors:
            raise FileExistsError

        origin_fd = open(filename, 'rb')
        origin_fd_len = _file_length_from_fd(origin_fd)
        self.original_descriptors[filename] = (origin_fd, origin_fd_len)
        new_filename = '.cache/' + basename(filename)

        if not os.path.exists(new_filename):
            with open(new_filename, 'wb') as new_file:
                new_file.write(
                    _render_static_file_headers(
                        filename, origin_fd_len
                    )
                )
                new_file.flush()
                _sendfile(
                    new_file.fileno(), origin_fd.fileno(), 0, origin_fd_len
                )

        new_fd = open(new_filename, 'rb')
        new_fd_len = _file_length_from_fd(new_fd)
        self.temporary_descriptors[filename] = (
            new_fd,
            new_fd_len
        )
        self.headers[filename] = headers or {}

    def get_file(self, filename: str):
        """
        Shouldn't be used, but made for cases when some stupid person will
        try to get file content from cache
        """

        fd, _ = self.original_descriptors[filename]
        fd.seek(0)
        content = fd.read()

        return content

    def send_file(self,
                  http_send: 'HttpServer.send',
                  conn: 'socket.socket',
                  filename: str,
                  headers: Union[dict, None] = None
                  ):
        if filename not in self.original_descriptors:
            self.add_file(filename)

        temp_fd, length = self.temporary_descriptors[filename]
        _sendfile(conn.fileno(), temp_fd.fileno(), 0, length)

    def close(self):
        for fd, _ in self.original_descriptors.values():
            fd.close()

        for temp_fd, _ in self.temporary_descriptors.values():
            temp_fd.close()
            os.remove(temp_fd.name)

    def __del__(self):
        self.close()
