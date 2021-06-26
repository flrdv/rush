import logging
from time import sleep

logger = logging.getLogger(__name__)


def bind_sock(sock, addr, max_retries=99999,
              retries_timeout=3, disable_logs=True):
    addr_stringified = addr[0] + ':' + str(addr[1])

    if disable_logs:
        logger.disabled = True

    for retry_num in range(1, max_retries + 1):
        logger.info(f'trying to bind server on {addr_stringified}...')

        try:
            sock.bind(addr)
            logger.info(f'server successfully binded on {addr_stringified}')
            logger.disabled = False

            return True
        except OSError:
            logger.error(f'failed to bind server on {addr_stringified} for {retry_num} ' +
                         ('time' if retry_num == 1 else 'times'))

        sleep(retries_timeout)

    logger.critical(f'failed to bind server on {addr_stringified}: '
                    'max retries limit exceeded')

    logger.disabled = False

    return False
