import urllib.request
import urllib.error


def get_external(otherwise='127.0.0.1'):
    try:
        return urllib.request.urlopen('https://ident.me').read().decode('utf8')
    except urllib.error.URLError:
        return otherwise
