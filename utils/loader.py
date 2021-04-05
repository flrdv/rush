content_types = {
    'html': 'text',
    'css': 'text',
    'png': 'image',
    'ico': 'image',
    'jpg': 'image',
    'jpeg': 'image',
}


class Loader:
    def __init__(self, root='localfiles', caching=False):
        self.root = root
        self.caching = caching

        self.cache = {}
        self.paths_aliases = {}
        self.default_404_response = """\
<html>
    <head>
        <title>404 NOT FOUND</title>
    </head>
    <body>
        <h6 align="center">404 REQUESTING PAGE NOT FOUND</h6>
    </body>
</html>        
"""

    def load(self, path: str, load_otherwise: str or None = '/404.html',
             cache: bool = None):
        if path == '/':
            path = '/index.html'

        if path in self.cache:
            return self.cache[path]

        try:
            with open(self.root + path, 'rb') as fd:
                content = fd.read()
        except FileNotFoundError:
            if not load_otherwise:
                return self.default_404_response.encode(), 'text/html'

            return self.load(load_otherwise, load_otherwise='', cache=cache)

        if cache is None:
            cache = self.caching

        extension = path.split('.')[-1]
        content_type = content_types.get(extension, 'text') + '/' + extension

        if cache:
            self.cache[path] = (content, content_type)

        return content

    def cache_files(self, *files):
        for file in files:
            self.load(file, cache=True)
