from os import listdir
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf8") as long_desc_fd:
    long_description = long_desc_fd.read()

with open('version', 'r') as version_fd:
    version = version_fd.read().strip('\n')

"""
IDK why, but this is the only way to add rush/defaultpages
to a wheel package
"""
defaultpages_content = map(lambda filename: 'rush/defaultpages/' + filename,
                           listdir('rush/defaultpages'))

setup(
    name="rush",
    version=version,
    author="floordiv",
    description="Webserver that I'm trying to do as fast as fuck",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/floordiv/rush",
    packages=find_packages(),
    include_package_data=True,
    data_files=[('', defaultpages_content)],
    project_urls={
        "Bug Tracker": "https://github.com/floordiv/rush/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux only",
    ],
    python_requires=">=3.6",
)
