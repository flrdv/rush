from setuptools import setup, Extension
from Cython.Build import cythonize

ext = Extension(
    name='httpserver',
    sources=['pyhttpserver.py']
)

setup(
    name='httpserver',
    ext_modules=cythonize(ext)
)
