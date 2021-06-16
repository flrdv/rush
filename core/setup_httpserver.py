from setuptools import setup, Extension
from Cython.Build import cythonize

ext = Extension(
    name='httpserver',
    sources=['httpserver.py']
)

setup(
    name='httpserver',
    ext_modules=cythonize(ext)
)
