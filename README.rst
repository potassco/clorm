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



Clingo supportcan also be run as a library and called from

high-level Python abstraction for asserting and extracting
facts from the Clingo  solver.


is a python library to help when interfacing with the Clingo ASP
reasoner. It is not a replacement for the existing Clingo Python interface but
instead provides some helper functions and additional high-level abstractions.

The heart of ASPHelper is an Object Relational Interface (ORM) style interface
for mapping between ground ASP facts and Python object instances. The ORM
interface is inspired by the well-known Peewee ORM used for interfacing Python
with relational databases.

A simple example:

    from asphelper.orm import BasePredicate, NumberField, StringField, SimpleField

    class Employee(BasePredicate):
       id = NumberField()
       name = StringField()
       role = SimpleField()

    e1 = Employee(id=1, name="Dave", role="developer")

