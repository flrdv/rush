from platform import system, uname
from subprocess import check_output


def get_max_descriptors():
    try:
        return int(check_output('ulimit -n', shell=True))
    except ValueError:
        # failed by some reason
        return None


def set_max_descriptors(value=None):
    """
    Trying to set max descriptors. Always returns max descriptors value
    """

    # in case of security, only int or None is allowed
    if value is not None and not isinstance(value, int):
        raise ValueError('setting max descriptors: given value that is not int or None')

    if value is None:
        value = 'unlimited'

    try:
        check_output('ulimit -Sn ' + str(value))

        return get_max_descriptors()
    except ValueError:
        return get_max_descriptors()


def is_linux():
    return system() == 'Linux'


def is_wsl():
    return is_linux() and 'Microsoft' in uname().release
