## Describing Rush-v2, forgetting about Rush-v1 (that is currently in master; actual description is about `remake` branch)

### Rush-v2 is building in accordance with all the optimization & architecture experience I got from Rush-v1

---

Entry point of webserver - rush/webserver.py. This module contains class-controller, 
that is collecting handlers and packing them into core.entities.Handler classes. After 
that, class-controller initializes core.server.HttpServer class, starting process-workers
and passes a queue with requests to them

* Queue with requests is being filled by HttpServer, that's why the only thing that is required
from class-controller is passing HttpServer.requests to process-workers
  
---

Process worker is a separated but memory-shared process, that is waiting for a request from given
requests_queue, and after receiving just calls a handler which filters match the request.
If there are no handlers that matches the request, error-handler will be called

---

Error handler is a usual handler, but handles only when server calls it manually. For example,
when no usual handlers found that matches the request, handler for not-found event will be called. 
Error handlers should be provided from class-controller as a dict in format: {error-handler-type: callable}.
Full list of currently available error handlers:
- not-found: as already been noted, being called only when no other handlers didn't match the request
- internal-error: being called when handler raises an exception

Error handlers receive the same argument as usual handlers: request (core.entities.Request)

---

Request entity: all the handlers receive only one argument (currently; soon will be added accessibility to
receive kwargs with string that was matched in a path): instance of core.entities.Request. According to 
rules of webserver optimization, there is only one instance of Request object per process worker.
This means, that with every request old Request-instance's fields will be rewritten. In case you wanna try
some UB-raising things like `def my_handler(request: entities.Request): del request` I'm not in responsibility
of results, so, don't even try to open issues
