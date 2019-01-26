API Documentation
=================

The heart of the ClORM ORM is defining the mapping from *ground predicates* to
member variables of a Python object. There are two aspects of this: *term
definitions* that define how *ASP terms* are mapped to Python objects, and
*predicate* definitions that define predicate and function names, their arities
and the term definitions for each of these parameter.

Term Definitions
-----------------

Term definitions provide a specification for how do convert ``Clingo.Symbol``
objects into more intuitive Python objects.

.. autoclass:: clorm.orm.RawTermDefn
    :members:

.. autoclass:: clorm.orm.StringTermDefn

.. autoclass:: clorm.orm.ConstantTermDefn

.. autoclass:: clorm.orm.IntegerTermDefn

Predicates and Complex Terms
----------------------------

In logical terminology predicates and complex terms are both instances of *non
logical symbols*. The ClORM implementation captures this in the
``NonLogicalSymbol`` class with ``Predicate`` and ``ComplexTerm`` simply being
aliases.

.. autoclass:: clorm.orm.NonLogicalSymbol
    :members:

.. autoclass:: clorm.orm.Predicate
    :members:

.. autoclass:: clorm.orm.ComplexTerm
    :members:
       
    ..autoattribute:: meta

Calling Python From an ASP Program
----------------------------------

.. autoclass:: clorm.orm.Signature
    :members:

Integration with Clingo
-----------------------

.. automodule:: clorm.monkey
    :members:
