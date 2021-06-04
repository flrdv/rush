from utils.exceptions import NotFound

DEFAULT_404 = """\
<html>
    <head>
        <title>404 NOT FOUND</title>
    </head>
    <body>
        <br><br>
        <h1 align="center"><tt>404 REQUESTING PAGE NOT FOUND</tt></h1>
    </body>
</html>
"""
DEFAULT_500 = """\
<html>
    <head>
        <title>500 Internal Server Error</title>
    </head>
    <body>
        <br><br>
        <h1 align="center">500 Internal Server Error</h1>
    </body>
</html>

"""


def not_found(request):
    try:
        request.response_file('404.html')
    except NotFound:
        request.response(404, body=DEFAULT_404)


def internal_error(request):
    try:
        request.response_file('500.html')
    except NotFound:
        request.response(500, body=DEFAULT_500)
