from os import listdir
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf8") as long_desc_fd:
    long_description = long_desc_fd.read()

with open('version', 'r') as version_fd:
    version = version_fd.read().strip('\n')

requirements = []

with open('requirements.txt', 'r') as requirements_fd:
    for requirement in requirements_fd:
        if requirement:
            requirements.append(requirement.strip())

"""
IDK why, but this is the only way to add rush/defaultpages
to a wheel package
"""
nonpython_files_dirs = [
    'rush/defaultpages',
    'rush/defaultpages/static'
]
nonpython_files = []

for nonpython_files_dir in nonpython_files_dirs:
    nonpython_files_dir = nonpython_files_dir.rstrip('/') + '/'
    nonpython_files.extend(map(lambda file: nonpython_files_dir + file,
                               listdir(nonpython_files_dir)))

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
    data_files=[('', nonpython_files)],
    project_urls={
        "Bug Tracker": "https://github.com/floordiv/rush/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux only",
    ],
    python_requires=">=3.6",
    install_requires=requirements
)
