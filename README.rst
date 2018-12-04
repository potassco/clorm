ASPHelper
=========

ASPHelper provides some utilities for making it easier to build Answer Set
Programming (ASP) applications that interact with Python.

ASP provides a logic based language for modelling and solving combinatorial
optimisation problems. The Potassco Suite is the leading (open-source) ASP tool
set. Within this tool set the Clingo solver is the main user-level
executable.

For more information on Clingo and ASP see the `Clingo home page <https://potassco.org>`_.

Clingo supports Python in two ways:

* calling Python functions from within an ASP program,
* running Clingo from within a Python application.

ASPHelper can help with both these aspects, although the primary goal of this
library is to make it easier to build Python applications that use Clingo.

ASPHelper consists of the following components:

* the core component is the Object Relational Mapper (ORM).


Use Case
--------

The basic use case is for a Python-based database application that needs to
perform some form of logical reasoning. The database stores a set of facts.  It
is queried and the results need to be asserted to Clingo. Clingo than solves the
reasoning problem and produces solutions (technically called "answer
sets"), where each solution consists of a set of facts. These facts need to be
extracted from Clingo and processed in some way, and possibly inserted back to
the database.

ORM
---

This is the core component of ASPHelper. An ORM provides a high-level interface
for inserting to, and querying, a database. A simplified version of this idea
can be applied to getting facts in and out of Clingo. The ASPHelper ORM-like
interface that is based heavily on the well-known Peewee ORM.

Quick Start
-----------

A simple example:

.. code-block:: python

    from asphelper.orm import BasePredicate, NumberField, StringField, SimpleField

    class Employee(BasePredicate):
       id = NumberField()
       name = StringField()
       role = SimpleField()

    e1 = Employee(id=1, name="Dave", role="developer")

TODO
----

* add Sphinx documentation
* add examples

Components to add:

* a library of resuable ASP integration components.
* a debug library.

