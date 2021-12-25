from platform import system, uname


def is_windows():
    return system() == 'Windows'


def is_linux():
    return system() == 'Linux'


def is_wsl():
    return is_linux() and 'Microsoft' in uname().release
