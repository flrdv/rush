import os.path
import logging
from threading import Thread
from traceback import format_exc

import inotify.adapters
from inotify.calls import InotifyError
from inotify.constants import IN_MODIFY

from rush.core.utils import httputils

logger = logging.getLogger(__name__)

content_types = {
    'html': 'text',
    'css': 'text',
    'png': 'image',
    'ico': 'image',
    'jpg': 'image',
    'jpeg': 'image',
}


class Loader:
    def __init__(self, cache_impl, root):
        self.root = root
        self._cache = cache_impl(self.root)
        self._cache.start()

        self.cached_files = []
        self.cached_responses = {}

    def load(self, filename, cache=True):
        if filename == '/':
            filename = '/index.html'
        elif filename[0] != '/':
            filename = '/' + filename

        if filename in self._cache.cached_files:
            return self._cache.get(filename)

        with open(self.root + filename, 'rb') as fd:
            content = fd.read()

        if cache:
            self._cache.add(filename, content)

        return content

    def cache_files(self, *files):
        for file in files:
            if file[0] != '/':
                file = '/' + file

            try:
                with open(self.root + file, 'rb') as fd:
                    self._cache.add(file, fd.read())
            except FileNotFoundError:
                logger.error(f'trying to cache non-existing file: {self.root + file}')

    def cache_response(self, filename):
        return self._cache.add_response(filename, self.load(filename))

    def get_cached_response(self, filename, otherwise=None):
        return self._cache.get_response(filename, otherwise)


class AutoUpdatingCache:
    """
    Default cache that is using inotify lib to see when files has changed, to reload their content
    """

    def __init__(self, root):
        self.root = root
        self.inotify = inotify.adapters.Inotify()

        self.cached_files = {}
        self.cached_responses = {}

    def _events_listener(self):
        for event in self.inotify.event_gen(yield_nones=False):
            _, event_types, path, filename = event

            if IN_MODIFY in event_types:
                file_path = os.path.join(path, filename)

                with open(file_path, 'rb') as fd:
                    new_content = fd.read()

                    self.cached_files[file_path] = new_content
                    self.add_response(file_path, new_content)

                logger.info(f'cache: updated file PATH={path} FILENAME={filename}')

    def add(self, path_to_file, actual_content):
        if path_to_file[0] != '/':
            path_to_file = '/' + path_to_file

        self.cached_files[path_to_file] = actual_content

        try:
            self.inotify.add_watch(self.root + path_to_file)
        except InotifyError as exc:
            logger.error(f'failed to start watching file {self.root + path_to_file}: {exc}'
                         f'\nFull traceback:\n{format_exc()}')

    def get(self, path_to_file):
        return self.cached_files[path_to_file]

    def add_response(self, filename, new_content):
        if new_content is None:
            new_content = self.get(filename)

        response = httputils.render_http_response((1, 1), 200, 'OK',
                                                  None, new_content)
        self.cached_responses[filename] = response

        return response

    def get_response(self, filename, otherwise):
        return self.cached_responses.get(filename, otherwise)

    def start(self):
        Thread(target=self._events_listener).start()
