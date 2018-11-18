#!/usr/bin/env python

import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="asphelper",
    version="0.0.1",
    author="David Rajaratnam",
    author_email="daver@gemarex.com.au",
    description="Support utilities for the Clingo Answer Set Programming (ASP) solver",
    license="MIT",
    url="https://github.com/daveraja/asphelper",
    packages=["asphelper","tests"],
    long_description=read("README.rst"),
)
