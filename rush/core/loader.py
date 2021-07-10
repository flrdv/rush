import os.path
import logging

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, cache_impl, root):
        self.root = os.path.join(root, '')
        self._cache = cache_impl()
        self._cache.start()

        self.cached_files = []

        self.http_send = None

    def load(self, filename, cache=True):
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

    def cache_response(self, filename):
        if filename == '/':
            filename = 'index.html'

        return self._cache.add_response(self.root + filename.lstrip('/'))

    def send_response(self, conn, filename):
        if filename == '/':
            filename = 'index.html'

        return self._cache.send_response(self.http_send, conn,
                                         self.root + filename.lstrip('/'))
