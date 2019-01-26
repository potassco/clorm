API Documentation
=================

The heart of the ClORM ORM is defining the mapping from *ground predicates* to
member variables of a Python object. There are two aspects of this: *fields*
that define how *logical terms* are mapped to Python objects, and *predicate*
definitions that define predicate and function names, their arities and the
field for each of these parameter.

Fields
------

Fields provide a specification for how do convert ``Clingo.Symbol`` objects into
more intuitive Python objects.

.. autoclass:: clorm.orm.RawField
    :members:

.. autoclass:: clorm.orm.StringField

.. autoclass:: clorm.orm.ConstantField

.. autoclass:: clorm.orm.IntegerField

Predicates and Complex Terms
----------------------------

In logical terminology predicates and complex terms are both instances of *non
logical symbols*. The ClORM implementation captures this in the
``NonLogicalSymbol`` class with ``Predicate`` and ``ComplexTerm`` simply being
aliases.

.. autoclass:: clorm.orm.NonLogicalSymbol
    :members:

    .. autoattribute:: Field

.. autoclass:: clorm.orm.Predicate
    :members:

.. autoclass:: clorm.orm.ComplexTerm
    :members:


Calling Python From an ASP Program
----------------------------------

.. autoclass:: clorm.orm.Signature
    :members:

Integration with Clingo
-----------------------

.. automodule:: clorm.monkey
    :members:
