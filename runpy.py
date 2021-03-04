import sys
import importlib


if len(sys.argv) < 2:
    print('[USAGE] python3 runpy.py <path to file to run>')
    sys.exit(1)
    
path_to_module = sys.argv[1]
importlib.import_module(path_to_module)
