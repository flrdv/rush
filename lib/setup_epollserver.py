from setuptools import setup, Extension
from Cython.Build import cythonize

ext = Extension(
    name='epollserver',
    sources=['pyepollserver.py']
)

setup(
    name='epollserver',
    ext_modules=cythonize(ext)
)
