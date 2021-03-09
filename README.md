# Rush
Rush is a powerfull python web-server, focused on maximal horizontal expandability. Using microservices-like architecture

Detailed description of usage and architecture will be provided later, after project will be ready for alpha-testing (or when my lazy ass will have enough motivation to do it)


Road-to-the-release components' progress:
  - Resolver: done
  - Resolver api: done
  - Log server: done (untested)
  - Log server api: done (but I'm not sure, most of all, will be rewritten later)
  - Cluster server: done (untested)
  - Endpoint client: not started
  - Main server core: done (untested)
  - Main server (simple sockets wrapper): done (untested)
  - Main server (http wrapper): not started
  - Epoll Server Lib (lib.epollserver): done
  - Dumb User Protection (lib.epollserver.handshake, lib.epollserver.do_handshake): done
  - Periodic Events Lib (lib.periodic_events): done
  - Messages Delivering protocol (lib.msgproto): done
