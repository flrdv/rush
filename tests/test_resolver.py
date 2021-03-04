from time import sleep
from threading import Thread
from traceback import format_exc

from servers.resolver.resolver_api import ResolverApi, ClusterNotFoundError

api = ResolverApi(addr=('192.168.0.102', 11100))


def add_not_cool_cluster_in_3_seconds():
    sleep(3)
    api.add_cluster('not cool cluster', ('lox', 2021))


try:
    print(api.connect())
    print(api.add_cluster('my cool cluster', ('sosi', 69420)), 'added cool cluster')
    print(api.get_cluster('my cool cluster'), 'this is my cool cluster!')

    try:
        print(api.get_cluster('my not cool cluster'), 'and this is not my cool cluster')
    except ClusterNotFoundError:
        print('my not cool cluster not found cause he doesn\'t exists!')

    Thread(target=add_not_cool_cluster_in_3_seconds).start()
    print('finally! I waited until not cool cluster registered again: ',
          api.wait_for_cluster('not cool cluster'))
except:
    print('oups')
    print(format_exc())

