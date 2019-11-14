.. clorm documentation master file, created by
   sphinx-quickstart on Sat Dec 22 18:49:32 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Clorm: An ORM API for Clingo
============================

Introduction
------------

Clorm is a Python library that provides an Object Relational Mapper (ORM)-like
interface to the Clingo Answer Set Programming (ASP) solver. It allows *facts*
to be asserted to, and extracted from, the ASP solver in an intuitive and easy
to use way. The goal of this library is to supplement the existing Clingo API to
make it easier to build and maintain Python applications that integrate with
Clingo.

When integrating an ASP program into a larger application a typical requirement
is to model the problem domain as a statically written ASP program, but then to
generate problem instances and process the results dynamically. Clorm makes this
integration cleaner, both in terms of code readability but also by making it
easier to refactor the python code as the ASP program evolves.

- Works with Python 3.5+ (developed on 3.6 and 3.7)
- Tested with Clingo 5.3 and 5.4 (dev release)


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   clorm/installation
   clorm/background
   clorm/quickstart
   clorm/predicate
   clorm/factbase
   clorm/integration
   clorm/embedding
   clorm/advanced
   clorm/experimental
   clorm/api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
