import argparse
from sys import exit
from platform import system

from cli_utils import commands


def get_kwargs_from_argparse_namespace(namespace, none_as_null=True, ignore=()):
    kwargs = {}

    for var, val in namespace._get_kwargs():
        if (val is None and none_as_null) or var in ignore:
            continue

        kwargs[var] = val

    return kwargs


if __name__ == '__main__':
    if system() != 'Linux':
        print('[RUSH-CLI] Rush webserver is available only for Linux '
              f'but using {system()} instead')
        exit(1)

    arguments_parser = argparse.ArgumentParser(description='CLI for Rush-webserver')
    arguments_parser.add_argument('cmd', metavar='command')
    arguments_parser.add_argument('--addr')
    arguments_parser.add_argument('--daemon', default=True, type=bool)
    arguments_parser.add_argument('--profile')

    parsed = arguments_parser.parse_args()
    handler = commands.aliases.get(parsed.cmd)

    if handler is None:
        print('[RUSH-CLI] No command is provided. Type --help to get help about cli')
        exit(1)

    handler_kwargs = get_kwargs_from_argparse_namespace(parsed, ignore=('cmd',))
    handler(**handler_kwargs)
