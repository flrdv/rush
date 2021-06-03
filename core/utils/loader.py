import os.path
import logging
from threading import Thread

import inotify.adapters
from inotify.constants import IN_MODIFY

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
    def __init__(self, root='localfiles'):
        self.root = os.path.join(root, '')
        self.cache = AutoUpdatingCache(self.root)
        self.cache.start()

        self.cached_files = []

    def load(self, filename, cache=True):
        if self.root + filename in self.cache.cached_files:
            return self.cache.get(filename)

        with open(self.root + filename, 'rb') as fd:
            content = fd.read()

        if cache:
            self.cache.add(self.root + filename, content)

        return content

    def cache(self, *files):
        for file in files:
            with open(self.root + file, 'rb') as fd:
                self.cache.add(self.root + file, fd.read())


class AutoUpdatingCache:
    """
    Default cache that is using inotify lib to see when files has changed, to reload their content
    """

    def __init__(self, root):
        self.root = root
        self.inotify = inotify.adapters.Inotify()

        self.cached_files = {}

    def _events_listener(self):
        for event in self.inotify.event_gen(yield_nones=False):
            _, event_types, path, filename = event

            if IN_MODIFY in event_types:
                with open(path + '/' + filename, 'rb') as fd:
                    self.cached_files[os.path.join(path, filename)] = fd.read()

                logger.info(f'cache: updated file PATH={path} FILENAME={filename}')

    def add(self, path_to_file, actual_content):
        if path_to_file in self.cached_files:
            return

        self.cached_files[path_to_file] = actual_content
        self.inotify.add_watch(path_to_file)

    def get(self, path_to_file):
        return self.cached_files[path_to_file]

    def start(self):
        Thread(target=self._events_listener).start()
