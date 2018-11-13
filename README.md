ASPHelper is a library for interfacing Python and the Clingo ASP reasoner. It is
not a replacement for the existing Clingo Python interface but instead provides
a higher level of abstraction as well as some useful extensions.

The heart of ASPHelper is an Object Relational Interface (ORM) style interface
for mapping ASP predicates and Python classes. The ORM interface is inspired by
the well-known Peewee ORM used for interfacing Python with relational databases.

A simple example:

    from asphelper.orm import BasePredicate, NumberField, StringField, SimpleField

    class Employee(BasePredicate):
       name = StringField()
       level = NumberField()

    e1 = Employee(name = "dave", level=1)

