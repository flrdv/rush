import os.path
import logging
from threading import Thread
from traceback import format_exc

import inotify.adapters
from inotify.calls import InotifyError
from inotify.constants import IN_MODIFY

from rush.core.utils import httputils

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, cache_impl, root):
        self.root = os.path.join(root, '')
        self._cache = cache_impl()

        self.cache_response = lambda filename: self._cache.add_response(self.root + filename.lstrip('/'))
        self.get_cached_response = lambda filename: self._cache.get_response(self.root + filename.lstrip('/'))

        self._cache.start()

        self.cached_files = []

    def load(self, filename, cache=True):
        file_path = self.root + filename.lstrip('/')

        if file_path in self._cache.cached_files:
            return self._cache.get(file_path)

        with open(file_path, 'rb') as fd:
            content = fd.read()

        if cache:
            self._cache.add(file_path, content)

        return content

    def cache_files(self, *files):
        for file in files:
            file = file.lstrip('/')

            try:
                with open(self.root + file, 'rb') as fd:
                    self._cache.add(self.root + file, fd.read())
            except FileNotFoundError:
                logger.error(f'trying to cache non-existing file: {self.root + file}')


class AutoUpdatingCache:
    """
    Default cache that is using inotify lib to see when files has changed, to reload their content
    """

    def __init__(self):
        self.inotify = inotify.adapters.Inotify()

        self.cached_files = {}
        self.get = self.cached_files.get

        self.cached_responses_headers = {}

    def _events_listener(self):
        for event in self.inotify.event_gen(yield_nones=False):
            _, event_types, path, filename = event

            if IN_MODIFY in event_types:
                file_path = os.path.join(path, filename)

                with open(file_path, 'rb') as fd:
                    self.cached_files[file_path] = fd.read()

                logger.info(f'cache: updated file PATH={path} FILENAME={filename}')

    def add(self, path_to_file, actual_content):
        self.cached_files[path_to_file] = actual_content

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
            with open(filename, 'rb') as fd:
                self.add(filename, fd.read())

        response_file = self.cached_files[filename]
        response_headers = httputils.render_http_response(('1', '1'), 200, 'OK',
                                                          {'Content-Length': len(response_file)}, b'')
        self.cached_responses_headers[filename] = response_headers

        return response_headers + response_file

    def get_response(self, filename) -> bytes or None:
        if filename not in self.cached_responses_headers or \
                filename not in self.cached_files:
            return None

        return self.cached_responses_headers[filename] + self.cached_files[filename]

    def start(self):
        Thread(target=self._events_listener).start()
