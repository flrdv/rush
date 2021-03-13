import argparse
from sys import exit, argv
from platform import system

from cli_utils import commands


def get_kwargs_from_argparse_namespace(namespace, none_as_null=True, ignore=()):
    kwargs = {}

    for var, val in namespace._get_kwargs():
        if (val is None and none_as_null) or var in ignore:
            continue

        kwargs[var] = val

    return kwargs


def run_cmd(cmd):
    if system() != 'Linux':
        print('[RUSH-CLI] Rush webserver is available only for Linux '
              f'but using {system()} instead')
        exit(1)

    arguments_parser = argparse.ArgumentParser(description='CLI for Rush-webserver')
    arguments_parser.add_argument('cmd', metavar='command')
    arguments_parser.add_argument('--addr')
    arguments_parser.add_argument('--daemon', default=False, type=bool)
    arguments_parser.add_argument('--profile')
    arguments_parser.add_argument('--file')

    parsed = arguments_parser.parse_args(cmd)
    handler = commands.aliases.get(parsed.cmd)

    if handler is None:
        print('[RUSH-CLI] No command is provided. Type --help to get help about cli')
        exit(1)

    handler_kwargs = get_kwargs_from_argparse_namespace(parsed, ignore=('cmd',))

    try:
        handler(**handler_kwargs)
    except TypeError:
        print('[RUSH-CLI] Got an unexpected argument')


if __name__ == '__main__':
    run_cmd(argv[1:])
