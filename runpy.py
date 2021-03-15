import sys
from subprocess import Popen


if len(sys.argv) < 2:
    print('[USAGE] python3 runpy.py <path to file to run>')
    sys.exit(1)

process = Popen(['python3', sys.argv[1]])
process.wait()
