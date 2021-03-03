import servers.logserver.logserver as logserver


if __name__ == '__main__':
    my_logserver = logserver.LogServer(addr=('192.168.0.102', 11101))
    my_logserver.start()
