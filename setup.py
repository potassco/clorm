#!/usr/bin/env python

import os
import sys
import re
from setuptools import setup

# Utility functions so that we can populate the package description and the
# version number automatically.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def find_version(fname):
    version_file = read(fname)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(
    name="Clorm",
    version=find_version("clorm/__init__.py"),
    author="David Rajaratnam",
    author_email="daver@gemarex.com.au",
    description="Clingo ORM (CLORM) provides a ORM interface for interacting with the Clingo Answer Set Programming (ASP) solver",
    license="MIT",
    url="https://github.com/potassco/clorm",
    packages=["clorm","clorm.orm","clorm.util","clorm.lib"],
    package_data={"clorm": ["py.typed"]},
    zip_safe=False,  # https://mypy.readthedocs.io/en/latest/installed_packages.html
    install_requires=['clingo'] if sys.version_info >= (3, 8) else ['clingo', 'typing_extensions'],
    long_description=read("README.rst"),
)
