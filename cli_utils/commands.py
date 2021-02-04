import rush.servers.cluster_resolver.resolver
from rush.cli_utils import run_as_daemon


def start_resolver(ip='localhost', port=11100):
    resolver = rush.servers.cluster_resolver.resolver.Resolver(addr=(ip, port))
    run_as_daemon.run_function(resolver.run_blocking_handler)


aliases = {
    'run-resolver': start_resolver,
}
