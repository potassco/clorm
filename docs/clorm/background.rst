Motivation
==========

Object Relational Mapping (ORM)
-------------------------------

`ORM <https://en.wikipedia.org/wiki/Object-relational_mapping>`_ interfaces are
a common way of interacting with relational databases and there are some
well-known Python ORMs (e.g., SQLAlchemy and Peewee). Fundamentally all ORMs
provide a way of matching rows in a database table (or database view) to Python
objects whose member variables correspond to the fields of the database table.

As well as mapping table rows to program objects, ORMs also provide facilities
for building SQL queries using high-level primitives; rather than dealing with
raw SQL strings.

Answer Set Programming (ASP) and Clingo
---------------------------------------

`Answer Set Programming (ASP)
<https://en.wikipedia.org/wiki/Answer_set_programming>`_, not to be confused
with Microsoft Active Server Pages or ASP.NET, is an AI/logic based language for
modelling and solving combinatorial optimisation problems. ASP has a
Prolog-style language for specifying problems in terms of predicates and the
relations between them. The solver then generates solutions (called *models* or
*answer sets*) consisting of a sets of ground facts that are (minimally)
consistent with the defintions.

`Clingo <https://potassco.org>`_ is the leading open-source ASP solver. It can
be run as a stand-alone executable or integrated as a library into other
languages. It has very good support for Python with an extensive API for
interacting with the solver.

Clingo supports Python in two ways:

* running Clingo from within a Python application.
* calling Python functions from within an ASP program,

An ORM Interface to Clingo
--------------------------

While the Clingo Python API is both extensive and flexible it is also fairly
low-level when it comes to getting data into, and out of, the solver. As a
result there is typically a reasonable amount of code that needs to be written
in order to carry out even simple translations to and from Clingo. Furthermore
without strong discipline such code can become interspersed throughout the
Python code base.

This can be especially problematic as the ASP program evolves. Keeping the
corresponding Python translation code up to date can be a cumbersome and error
prone process. For example, simply swapping the position of a parameter in a
predicate and accidentally failing to update the corresponding Python code might
not cause an obvious error in the program, but instead could cause subtle errors
that are difficult to detect.

An ORM interface can help to alleviate these problems. The ORM definitions that
map ASP predicates to Python objects are defined in a single location and the
ASP to Python translation is made clear; since it is not written directly by
the developer but instead is generated from the ORM class definitions.

Hence a Clingo ORM interface can make it easier to integrate Clingo and Python
and to write Python code that is more readable and easier to maintain.
