API Documentation
=================

The heart of the ClORM ORM is defining the mapping from *ground predicates* to
member variables of a Python object. There are two aspects of this: *fields*
that define how *logical terms* are mapped to Python objects, and *predicate*
definitions that define predicate and function names, their arities and the
field for each of these parameter.

Fields
------

Fields provide a specification for how to convert ``Clingo.Symbol`` objects into
more intuitive Python objects.

.. autoclass:: clorm.RawField
    :members:

.. autoclass:: clorm.StringField

.. autoclass:: clorm.ConstantField

.. autoclass:: clorm.IntegerField

Predicates and Complex Terms
----------------------------

In logical terminology predicates and complex terms are both instances of *non
logical symbols*. The ClORM implementation captures this in the
``NonLogicalSymbol`` class with ``Predicate`` and ``ComplexTerm`` simply being
aliases.

.. autoclass:: clorm.NonLogicalSymbol
    :members:

    .. autoattribute:: Field

.. autoclass:: clorm.Predicate
    :members:

.. autoclass:: clorm.ComplexTerm
    :members:


Fact Bases and Queries
------------------------

``Predicate`` instances correspond to facts. A ``FactBase`` provides a container
for storing facts. It allows predicate fields to be indexed and provides a basic
query mechanism for accessing elements.

.. autoclass:: clorm.FactBase
    :members:

.. autoclass:: clorm.Placeholder

.. autoclass:: clorm.Select
    :members:

.. autoclass:: clorm.Delete
    :members:


Calling Python From an ASP Program
----------------------------------

.. autoclass:: clorm.Signature
    :members:


Integration with Clingo
-----------------------

.. automodule:: clorm.monkey
    :members:
