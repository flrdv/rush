import server as webserver


server = webserver.WebServer()


@server.serve(func=lambda msg: True)
def handler(request):
    print('New request:', request)


server.start()
