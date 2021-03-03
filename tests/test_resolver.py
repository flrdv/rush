from traceback import format_exc

from servers.resolver.resolver_api import ResolverApi


try:
    api = ResolverApi(addr=('192.168.0.102', 11100))
    print(api.connect())
    print(api.add_cluster('my cool cluster', ('sosi', 69420)), 'added cool cluster')
    print(api.get_cluster('my cool cluster'), 'this is my cool cluster!')
    print(api.get_cluster('my not cool cluster'), 'and this is not my cool cluster')
except:
    print('oups')
    print(format_exc())
