ASPHelper is a python library to help when interfacing with the Clingo ASP
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

