Motivation
==========

Object Relational Mapping (ORM)
-------------------------------

`ORM <https://en.wikipedia.org/wiki/Object-relational_mapping>`_ interfaces are
a common way (especially in Python) of interacting with relational databases and
there are some well-known Python ORMs (e.g., SQLAlchemy and
Peewee). Fundamentally all ORMs provide a way of matching rows in a database
table (or database view) to Python objects whose member variables correspond to
the fields of the database table.

As well as mapping table rows to program objects, ORMs also provide facilities
for building SQL queries using high-level primitives; rather than dealing with
raw SQL strings.

An ORM Interface for Clingo
---------------------------

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
ASP to Python translations are all generated automatically from the ORM class
definitions.

Hence, we would argue that a Clingo ORM interface can make it easier to
integrate Clingo and Python and to write Python code that is more readable and
easier to maintain.
