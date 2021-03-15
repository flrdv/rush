"""
Mainserver-core makes only 1 thing: receives parsed request from wrapper
and distributes it to a most unloaded handler from handlers group to a
which one request belongs

class MainServerCore:
    __init__(response_callback, addr=('localhost', 1111), block_size=4096):
        - response_callback: callable object, that receives 1 argument
                             (see 'Response Callback Callable' part)
        - addr: local address on which handlers will be served
        - block_size: how much bytes per time will be received
                      from handler's socket (see part 'Handlers
                      Messages Delivering Protocol')
    send_request(request: dict):
        - request: request serialized to python's dict (for http
                   requests should be parsed to dict, too)

        This function just pushing request to worker-thread (see 'Requests
        Thread' part), so it's call is almost free
    start(threaded=False):
        - threaded: if set to True, function will return nothing,
                    but thread with this function will be started.

        Initialize and run mainserver-core. This function is blocking,
        it means, that mainserver-core will run until this function
        is running

part 'Response Callback Callable':
    Any callable object that receives 2 arguments: `response_to` and `response`.
    `response_to` may be any string, even integer or hash. It's problem of wrapper
    that will response to client this response belongs to. `response` is also any
    object, that should be specified with wrapper (it may be dict, that will be
    serialized to http again, or even directly http to avoid waste of resources).
    May be blocking, because will be called in a parallel thread (see 'Responses
    Thread' part)

part 'Handlers Messages Delivering Protocol':
    Server Side:
        Handlers can send to server only 2 types of packets:
            - heartbeat-packet with local machine's load
            - response

        Packets format:
            - 1 byte - type of request:
                - \x69 (heartbeat):
                    - 1 byte - integer that means machine's cpu load
                - \x42 (response):
                    - 4 bytes - length of the response
                    - 1-4294967295 bytes (4.2GB per response is current maximal response size,
                                          may be increased in future)

        When server receives RECEIVE event from epoll, it is reading
        blocks from socket by n bytes (see 'class MainServerCore.__init__:block_size'
        part)

part 'Responses Thread':
    Worker-thread that checking shared list with responses. If not
    empty - getting response_to and sends client it's response

part 'Requests Thread':
    Worker-thread that checking shared list with requests. If not
    empty - thread is looking for group that belongs to request,
    and the most unloaded handler and sends request to it

part 'How Will Maximal Response Size Increased':
    If required, maximal response size may be fixed by changing
    protocol by this way:
        - 1 byte - bytes of size of packet (uint, 255 is maximal value)
        - n bytes - length of message (max packet size by this way is
                    idk how much, but a lot as fuck)
        - a lot as fuck (up to 2^2000TB) bytes - body
"""
