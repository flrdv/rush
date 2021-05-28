from time import sleep

from lib import simplelogger


def bind_sock(logger: simplelogger.Logger, sock, addr, max_retries=99999,
              retries_timeout=3):
    addr_stringified = addr[0] + ':' + str(addr[1])

    for retry_num in range(1, max_retries + 1):
        logger.write(f'[INIT] Trying to bind server on {addr_stringified}...',
                     simplelogger.INFO)

        try:
            sock.bind(addr)
            logger.write(f'[INIT] Server successfully binded on {addr_stringified}',
                         simplelogger.INFO)

            return True
        except OSError:
            logger.write(f'[INIT] Failed to bind server on {addr_stringified} for {retry_num} ' +
                         ('time' if retry_num == 1 else 'times'),
                         simplelogger.ERROR)

        sleep(retries_timeout)

    logger.write(f'[INIT] Failed to bind server on {addr_stringified}: max retries limit exceeded',
                 simplelogger.ERROR)

    return False
