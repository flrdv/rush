## Rush-v2 architecture

### Rush-v2 is building in accordance with all the optimization, architecture experience, and speed-boosters I got from Rush-v1

---

Entry point - rush/webserver.py. It contains the only class - `WebServer`. This class 
implements not only user-api, but also forking logic, initializing http server, handling 
interrupts

`WebServer` object implements `.start()` method, that:
- calls on-startup event callback
- forking due to user configuration
- binds server socket to specified address
- initializes http server and passes handlers manager to it
- properly stopping it's work after occurred error (like unhandled exceptions, aborting by user, etc.), 
  like killing it's children forks

---

Http server - rush/core/httpserver.py. It implements class `HttpServer` that receives only 
`socket` object and `max_conns`. Works on epoll. After receiving full request, it calls 
on-message-complete-callback: function that is passing on server initializing. Passing such arguments:

- request body (represented as bytestring)
- client connection object (`socket` object)
- protocol version (tuple of major and minor version of protocol)
- request method
- request path
- query-string (parameters from url)
- request headers (frozen dict)
- is received request a file transfer
  
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
result - save a bit time on each request. 

---

Loader is rush/core/utils/loader.py. This module implements `Loader` class. 
Loader handles sending files from file system. Caching can be chosen by yourself
by passing valid Cache-like object to loader.
