API Documentation
=================

The heart of the Clorm ORM involves defining the mapping from *ground
predicates* to member variables of a Python object. There are two aspects to
this: *fields*, that define how *logical terms* are mapped to Python objects,
and *predicate* definitions, that define predicate and function names, their
arities and the field for each of the parameter.

.. _api_fields:

Fields
------

Fields provide a specification for how to convert ``Clingo.Symbol`` objects into
more intuitive Python objects.

.. autoclass:: clorm.RawField
   :members: cltopy, pytocl, unifies, default, index

.. autoclass:: clorm.StringField

.. autoclass:: clorm.ConstantField

.. autoclass:: clorm.IntegerField

.. autofunction:: clorm.refine_field

.. _api_predicates:

Predicates and Complex Terms
----------------------------

In logical terminology predicates and complex terms are both instances of *non
logical symbols*. The Clorm implementation captures this in the
``NonLogicalSymbol`` class with ``Predicate`` and ``ComplexTerm`` simply being
aliases.

.. autoclass:: clorm.NonLogicalSymbol
   :members:

   .. attribute:: Field

      A RawField sub-class corresponding to a Field for this class


   .. attribute:: meta

      The meta data (definitional information) for the Predicate/Complex-term


.. autoclass:: clorm.Predicate
   :members:

.. autoclass:: clorm.ComplexTerm
   :members:

.. autofunction:: clorm.define_nls

.. _api_factbase:

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

.. _api_calling_python_from_asp:

Calling Python From an ASP Program
----------------------------------

Clorm provides a number of decorators that can make it easier to call Python
from within an ASP program. The basic idea is that Clorm provides all the
information required to convert data between native Python types and
clingo.Symbol objects. Therefore functions can be written by only dealing with
Python data and the Clorm decorators will wrap these functions with the
appropriate data conversions based on a given signature.

.. autofunction:: clorm.make_function_asp_callable

.. autofunction:: clorm.make_method_asp_callable

It may also be useful to deal with a predeclared type cast signature.

.. autoclass:: clorm.TypeCastSignature
   :members:

From Clingo 5.4 onwards, the Clingo grounding function allows a `context`
parameter to be specified. This parameter defines a context object for the
methods that are called by ASP using the @-syntax.

.. autoclass:: clorm.ContextBuilder
   :members:

.. _api_clingo_integration:

Integration with the Solver
---------------------------

To simplify the interaction with the Clingo solver, Clorm provides a ``clingo``
replacement module that offers better integration with Clorm facts and fact
bases. This module simply wraps and extends a few key Clingo classes.

Instead of:

.. code-block:: python

   import clingo

use:

.. code-block:: python

   import clorm.clingo

For convenience the ``clingo.Control`` class can also be `monkey patched
<https://en.wikipedia.org/wiki/Monkey_patch>`_ so that it can used seemlessly
with existing code bases.

.. code-block:: python

   from clorm import monkey; monkey.patch()
   import clingo

Here we document only the extended classes and the user is referred to the
`Clingo API <https://potassco.org/clingo/python-api/current/clingo.html>`_
documentation for more details.

.. autoclass:: clorm.clingo.Control
   :members:

.. autoclass:: clorm.clingo.Model
   :members:

.. autoclass:: clorm.clingo.SolveHandle
   :members:

Experimental Features
---------------------

The following can change between Clorm minor versions.

JSON Encoding and Decoding
^^^^^^^^^^^^^^^^^^^^^^^^^^

Clorm allows clingo.Symbols, Predicates, and FactBases to be translated to/from
JSON.

.. autoclass:: clorm.json.FactBaseCoder
   :members:

.. autofunction:: clorm.json.symbol_encoder

.. autofunction:: clorm.json.symbol_decoder
