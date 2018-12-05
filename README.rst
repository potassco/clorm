Clingo ORM (CLORM)
==================

CLORM is a Python library that provides an Object Relational Mapping (ORM)
interface to the Clingo Answer Set Programming (ASP) solver.

`ASP <https://en.wikipedia.org/wiki/Answer_set_programming>`_ is a AI/logic
based language for modelling and solving combinatorial optimisation
problems. ASP has a Prolog-style language for modelling problems in terms of
predicates and the relations between them. The solver then generates solutions
(called *models* or *answer sets*) consisting of a sets of ground facts that are
(minimally) consistent with the defintions.

`Clingo <https://potassco.org>`_ is the leading open-source ASP solver. It can
be run as a stand-alone executable or integrated as a library into other
languages. It has very good support for Python with an extensive API for
interacting with the solving.

Clingo supports Python in two ways:

* calling Python functions from within an ASP program,
* running Clingo from within a Python application.

While the Python API is both extensive and flexible it is fairly low-level when
it comes to getting data into, and out of, the solver. This also means that as
you ASP program evolves and changes, adapting your Python code to match your ASP
code become very tedious. CLORM is intended to help by providing a higher-level
ORM interface to make it easy to match the ASP facts to Python objects.

`ORM <https://en.wikipedia.org/wiki/Object-relational_mapping>`_ interfaces are
a common way of interacting with relational databases and there are some
well-known Python ORM. My only have (limited) experience with the lightweight
Peewee ORM so some aspects of the CLORM API will have a Peewee-like flavour.

Use Case
--------

The basic use case is for a Python-based application that needs to interact with
the Clingo reasoner. A typical such application would be Python web-app with a
database backend that supplies data for some form of high-level reasoning (e.g.,
business logic). The database is queried and the results of the query are
asserted to the Clingo reasoner. Clingo then produces a solution (or sets of
possibly solutions) which can be used in the application or simply inserted back
to the database.

Quick Start
-----------

A simple example:

.. code-block:: python

    from clorm import Predicate, NumberField, StringField, SimpleField

    class Employee(BasePredicate):
       id = NumberField()
       name = StringField()
       role = SimpleField()

    e1 = Employee(id=1, name="Dave", role="developer")

TODO
----
* clean up the API
* add Sphinx documentation
* add examples

Components to add:

* a library of resuable ASP integration components.
* a debug library.

