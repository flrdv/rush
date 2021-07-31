import os.path
import logging
from traceback import format_exc

from ..utils.cache import Cache

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, cache_impl, root):
        self.root = os.path.join(root, '')

        if not issubclass(cache_impl, Cache):
            raise TypeError(f'cache implementation {cache_impl} has to be '
                            'inherited from rush.utils.cache.Cache class')

        self._cache = cache_impl()
        self._cache.start()

        self.cached_files = []

        self.http_send = None

    def get_file(self, filename, cache=True):
        file_path = self.root + filename.lstrip('/')

        if file_path in self.cached_files:
            return self._cache.get_file(file_path)

        if cache:
            self._cache.add_file(file_path)

            return self._cache.get_file(file_path)
        else:
            with open(file_path, 'rb') as fd:
                return fd.read()

    def cache_files(self, *files):
        for file in files:
            file = file.lstrip('/')

            if not file:
                file = 'index.html'

            try:
                self._cache.add_file(self.root + file)
                self.cached_files.append(self.root + file)
            except FileNotFoundError:
                logger.error(f'trying to cache non-existing file: {self.root + file}')
            except FileExistsError:
                logger.warning(f'trying to cache already cached file: {self.root + file}')

    def send_response(self, conn, filename, headers):
        if filename == '/':
            filename = 'index.html'

        try:
            return self._cache.send_file(self.http_send, conn,
                                         self.root + filename.lstrip('/'),
                                         headers)
        except IsADirectoryError:
            raise FileNotFoundError from None

    def close(self):
        self._cache.close()
