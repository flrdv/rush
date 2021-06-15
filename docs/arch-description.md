## Rush-v2 architecture

### Rush-v2 is building in accordance with all the optimization, architecture experience, and speed-boosters I got from Rush-v1

---

Entry point - rush/webserver.py. It contains the only class - `WebServer`. This class 
implements not only user-api, but also forking logic, initializing http server, handling 
interrupts

`WebServer` object implements `.run()` method, that:
- calls on-startup event callback
- forking due to user configuration
- binds server socket to specified address
- initializes http server and passes handlers manager to it
- properly stopping it's work after occurred error (like unhandled exceptions, aborting by user, etc.), 
  like killing it's children forks
  
---

Epoll eventpoll lib - rush/lib/epollserver.py. This is a tiny library that gets user handlers,
and calling them after receiving epoll events. Made and designed for ease use of epoll (implementing
server on epoll manually, using select.epoll directly in server is disgusting and non-scalability)

You can see docs of epollserver directly in lib sources, from big docstring

---

Http server - rush/core/httpserver.py. It implements class `HttpServer` that receives only 
`socket` object and `max_conns`. Works on epollserver. After receiving full request, it calls 
on-message-complete-callback: function that is passing on server initializing. Passing such arguments:

- request body (represented as bytestring)
- client connection object (`socket` object)
- protocol version (tuple of major and minor version of protocol)
- request method
- request path
- query-string (parameters from url)
- request headers (frozen dict)
  
---

Handlers manager - rush/core/handlers.py. Implements class `HandlersManager`, that takes such a parameters: 
- usual handlers
- error handlers
- static redirects
- loader
- http server instance

After calling, picks handler (firstly - by routing path, then - by method, and if presented - by 
filter (callable handler-like function that also receives request-object, and returns bool that
means whether will be handler called or not))

If handler wasn't picked, `not-found` handler will be called
If occurs `FileNotFound`/`utils.exceptions.NotFound` exceptions, `not-found` error handler will be called
If occurs any other exception, `internal-error` error handler will be called

---

Error handler is a usual handler, but calling only when something fails. For example, unhandled
exception occurred in handler (`internal-error` handler), or handler for request wasn't found
(`not-found` handler). Receives also one argument: `core.entities.Request` object

---

`core.entities.Request` object is an object that being initialized only once, after what will be used
during the whole server life-time. This is made to avoid creating instances in runtime, and as a 
result - save a bit time on each request. Implements parsing parameters from requesting path,
but first you need to call `request.parse_args()`. This is made due to avoid parsing url parameters
in cases when it is not needed for user, because parsing is really expensive (parsing 100,000 
parameters strings takes about 0.2 sec. In case of my server shows 175k RPS, using arguments parsing
decreases RPS to value 155k, and makes latency much more worse)

---

Loader is rush/core/utils/loader.py. This module implements `Loader` class, and `AutoUpdatingCache`
cache class that is used by default. Loader handles getting files from disk. If required, it is caching
it to given cache object. `AutoUpdatingCache` is a class that implements in-memory files caching
with auto-updating them after their modifying. `AutoUpdatingCache` just starts a thread that is
catching events from `inotify`, and updating in-memory file content with new one from fs
