# Rush
Rush is a powerfull python web-server, focused on maximal horizontal expandability. Using microservices-like architecture

Detailed description of usage and architecture will be provided later, after project will be ready for alpha-testing (or when my lazy ass will have enough motivation to do it)


Road-to-the-release components' progress:
  - Resolver: done
  - Resolver api: done
  - Log server: done (untested)
  - Log server api: in progress (waiting for auto re-connecting)
  - Cluster server: not started
  - Endpoint client: not started
  - Main server core: in progress
  - Main server (http wrapper): not started
  - Epoll Server Lib (lib.epollserver): done
  - Dumb User Protection (lib.epollserver.handshake, lib.epollserver.do_handshake): done
  - Periodic Events Lib (lib.periodic_events): done
  - Messages Delivering protocol (lib.msgproto): done
