class ConnectionPool:
    def __init__(self, *groups):
        self.connection_pool = {group: [] for group in groups}

    def add_conn(self, group, conn):
        """
        This class is done for maximal performance,
        that's why we won't check if group exists
        """
        self.connection_pool.get(group, []).append(conn)

    def remove_conn(self, group, conn):
        self.connection_pool.get(group, [conn]).remove(conn)

    def get_conn(self, group):
        try:
            return self.connection_pool[group][0]
        except (KeyError, IndexError):
            pass

        raise ConnectionError('no connections found')

    def add_group(self, name):
        """
        This also clears pool of connections if group already exists
        """
        self.connection_pool[name] = []

    def remove_group(self, name):
        try:
            self.connection_pool.pop(name)
        except KeyError:
            return
