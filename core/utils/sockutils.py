from time import sleep


def bind_sock(logger, sock, addr, max_retries=99999,
              retries_timeout=3):
    addr_stringified = addr[0] + ':' + str(addr[1])

    for retry_num in range(1, max_retries + 1):
        logger.info(f'[INIT] Trying to bind server on {addr_stringified}...')

        try:
            sock.bind(addr)
            logger.info(f'[INIT] Server successfully binded on {addr_stringified}')

            return True
        except OSError:
            logger.error(f'[INIT] Failed to bind server on {addr_stringified} for {retry_num} ' +
                         ('time' if retry_num == 1 else 'times'))

        sleep(retries_timeout)

    logger.critical(f'[INIT] Failed to bind server on {addr_stringified}: '
                    'max retries limit exceeded')

    return False
