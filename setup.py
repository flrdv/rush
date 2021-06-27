from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf8") as fd:
    long_description = fd.read()

setup(
    name="rush",
    version="2.0.0",
    author="floordiv",
    description="Webserver that I'm trying to do as fast as fuck",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/floordiv/rush",
    packages=find_packages(),
    package_data={'': [
        'rush/defaultpages',
    ]},
    project_urls={
        "Bug Tracker": "https://github.com/floordiv/rush/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux only",
    ],
    python_requires=">=3.6",
)
