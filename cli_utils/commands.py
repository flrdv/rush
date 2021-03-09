from threading import Thread

import servers.resolver.resolver


def _parse_addr(addr):
    ip, port = addr.split(':')

    return ip, int(port)


def start_resolver(addr=('localhost', 11100), daemon=False):
    if isinstance(addr, str):
        ip, port = _parse_addr(addr)
    else:
        ip, port = addr

    resolver = servers.resolver.resolver.Resolver(addr=(ip, port))

    if not daemon:
        return resolver.start(threaded=False)

    Thread(target=resolver.start, kwargs={'threaded': False}, daemon=True).start()
    print('[RUSH-CLI] Resolver has been started on')


aliases = {
    'run-resolver': start_resolver,
}
