from threading import Thread
from importlib import import_module

import servers.resolver.resolver
import servers.cluster.cluster


def _parse_addr(addr):
    ip, port = addr.split(':')

    return ip, int(port)


def start_resolver(addr='localhost:11100', daemon=False):
    ip, port = _parse_addr(addr)
    resolver = servers.resolver.resolver.Resolver(addr=(ip, port))

    if not daemon:
        return resolver.start(threaded=False)

    Thread(target=resolver.start, kwargs={'threaded': False}, daemon=True).start()
    print('[RUSH-CLI] Resolver has been started on')


def start_mainserver(addr='localhost:0', daemon=False, file=None):
    if file is None:
        print('[RUSH-CLI] File not specified')

    ip, port = _parse_addr(addr)

    try:
        mainserver = import_module(file)
    except ImportError as exc:
        return print('[RUSH-CLI] Failed to start main server:', exc)

    if not hasattr(mainserver, 'start'):
        print('[RUSH-CLI] Invalid main server format. Check docs '
              'to get know how to build main server')

        return

    if not daemon:
        return mainserver.start()

    Thread(target=mainserver.start).start()


def start_cluster(addr='localhost:0', daemon=False, profile=None):
    addr = _parse_addr(addr)
    cluster = servers.cluster.cluster.Cluster(addr=addr, profile=profile)

    if not daemon:
        return cluster.start()

    Thread(target=cluster.start).start()


aliases = {
    'run-resolver': start_resolver,
    'run-mainserver': start_mainserver,
    'run-cluster': start_cluster,
}
