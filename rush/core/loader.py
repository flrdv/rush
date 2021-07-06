import os.path
import logging

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, cache_impl, root):
        self.root = os.path.join(root, '')
        self._cache = cache_impl()
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

    def cache_and_get_response(self, filename):
        return self._cache.add_response(self.root + filename.lstrip('/'))

    def get_cached_response(self, filename):
        return self._cache.get_response(self.root + filename.lstrip('/'))
