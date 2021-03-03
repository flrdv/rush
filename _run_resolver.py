import servers.resolver.resolver


if __name__ == '__main__':
    resolver = servers.resolver.resolver.Resolver(('192.168.0.102', 11100))
    resolver.start()
