from sys import argv, exit

from cli_utils import commands


HELP_FILE = 'cli_utils/help.txt'


def get_help_text(from_file=HELP_FILE):
    try:
        with open(from_file) as fd:
            return fd.read()
    except FileNotFoundError:
        return '<no help provided, looks like file does not exists>'


if __name__ == '__main__':
    args = argv[1:]

    if len(args) < 1:
        print(get_help_text())
        exit()

    handler, *handler_args = args
    handler_func = commands.aliases.get(handler)

    if handler_func is None:
        print('[RUSH-CLI] No such command:', handler)
        exit(1)

    handler_func()
