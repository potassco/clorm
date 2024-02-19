API Documentation
=================

The heart of the Clorm ORM involves defining the mapping from *ground
predicates* to member variables of a Python object. There are two aspects to
this: *fields*, that define how *logical terms* are mapped to Python objects,
and *predicate* definitions, that define predicate and function names, their
arities and the appropriate field for each of the parameters.

.. _api_fields:

Fields
------

Fields provide a specification for how to convert ``clingo.Symbol`` objects into the
appropriate/intuitive Python object. As of Clorm version 1.5, the preferred mechanism to
specify fields is to use standard Python type annotations. The primitive logical terms
*integer* and *string* are specified using the standard Python type ``int`` and ``str``
respectively, while logical *constant* terms are specified using a specially defined type:


.. autoclass:: clorm.ConstantStr

Internally within Clorm the type specifiers are mapped to a set of special classes that contain
the functions for converting between Python and the ``clingo.Symbol`` objects. These special
classes are referred to as *field definitions* and are subclassed from a common base class
:class:`~clorm.BaseField`.

.. autoclass:: clorm.BaseField
   :members: cltopy, pytocl, default, has_default, has_default_factory, index

For sub-classes of :class:`~clorm.BaseField` the abstract member functions
:py:meth:`~clorm.BaseField.cltopy` and :py:meth:`~clorm.BaseField.pytocl` must be implemented
to provide the conversion from Clingo to Python and Python to Clingo (respectively).

Clorm provides three standard sub-classes corresponding to the string, constant, and integer
primitive logical terms: :class:`~clorm.StringField`, :class:`~clorm.ConstantField`, and
:class:`~clorm.IntegerField`.

.. autoclass:: clorm.StringField

.. autoclass:: clorm.ConstantField

.. autoclass:: clorm.IntegerField


Special Fields
^^^^^^^^^^^^^^

Clorm provides a number of fields for some special cases. The :class:`~clorm.SimpleField` can
be used to define a field that matches to any primitive type. Note, however that special care
should be taken when using :class:`~clorm.SimpleField`. While it is easy to disambiguate the
Clingo to Python direction of the translation, it is harder to disambiguate between a string
and constant when converting from Python to Clingo, since strings and constants are both
represented using ``str``.  For this direction a regular expression is used to perform the
disambiguation, and the user should therefore be careful not to pass strings that look like
constants if the intention is to treat it like a logical string.

.. autoclass:: clorm.SimpleField

A :class:`~clorm.RawField` is useful when it is necessary to match any term, whether it is a
primitive term or a complex term. This encoding provides no traslation of the underlying Clingo
Symbol object and simply wraps it in a special :class:`~clorm.Raw` class.

.. autoclass:: clorm.Raw
   :members: symbol

.. autoclass:: clorm.RawField

Finally, there are a number of function generators that can be used to define some special
cases; refining or combining existing fields or allowing for a complicated pattern of
fields. While Clorm doesn't explicitly allow recursive terms to be defined it does provide a
number of encodings of list like terms. Note, it is sometimes possible to avoid the explicit
use of these functions and instead to rely on some predefined type annotation mappings.


.. autofunction:: clorm.refine_field

.. autofunction:: clorm.define_enum_field

.. autofunction:: clorm.combine_fields

.. autofunction:: clorm.define_nested_list_field

.. autofunction:: clorm.define_flat_list_field

.. _api_predicates:

Predicates and Complex Terms
----------------------------

In logical terminology predicates and terms are both considered *non logical
symbols*; where the logical symbols are the operator symbols for *conjunction*,
*negation*, *implication*, etc. While simple terms (constants, strings, and
integers) are handled by Clorm as special cases, complex terms and predicates
are both encapsulated in the ``Predicate`` class, with ``ComplexTerm`` simply
being an alias to this class.

.. autoclass:: clorm.Predicate
   :members:

   .. attribute:: Field

      A RawField sub-class corresponding to a Field for this class


   .. attribute:: meta

      Meta data (definitional information) for the predicate/complex-term. This
      includes:

      .. attribute:: name

         The name of the ASP predicate/complex-term. Empty if it is a tuple.

      .. attribute:: is_tuple

         Is the ASP predicate/complex-term a tuple.

      .. attribute:: arity

         Arity of the predicate/complex-term.

.. autoclass:: clorm.ComplexTerm
   :members:

.. autofunction:: clorm.simple_predicate


.. _api_factbase:

Fact Bases and Queries
------------------------

``Predicate`` instances correspond to facts. A ``FactBase`` provides a container
for storing facts. It allows predicate fields to be indexed and provides a basic
query mechanism for accessing elements.

.. autoclass:: clorm.FactBase
   :members:

A ``FactBase`` can generate formatted ASP facts using the function
:py:meth:`FactBase.add()<clorm.FactBase.add>`. This string of facts can be
passed to the solver or written to a file to be read. Mirroring this
functionality an ASP string or file containing facts can also be read directly
into a ``FactBase`` (without the indirect process of having to create a
``clingo.Control`` object).

.. autofunction:: clorm.parse_fact_string

.. autofunction:: clorm.parse_fact_files

One of the more important features of a ``FactBase`` is its ability to be
queried. There are a number of classes and functions to support the
specification of fact base queries.

.. autoclass:: clorm.Placeholder

.. autoclass:: clorm.Select

   .. automethod:: where

   .. automethod:: order_by

   .. automethod:: get

   .. automethod:: get_unique

   .. automethod:: count

.. autoclass:: clorm.Delete

   .. automethod:: where

   .. automethod:: execute


.. autoclass:: clorm.Query

   .. automethod:: join

   .. automethod:: where

   .. automethod:: order_by

   .. automethod:: group_by

   .. automethod:: select

   .. automethod:: distinct

   .. automethod:: bind

   .. automethod:: tuple

   .. automethod:: heuristic

   .. automethod:: all

   .. automethod:: singleton

   .. automethod:: count

   .. automethod:: first

   .. automethod:: delete

   .. automethod:: modify

   .. automethod:: replace

   .. automethod:: query_plan

.. autoclass:: clorm.PredicatePath


Query Support Functions
-----------------------

The following functions support the query specification.

.. autofunction:: clorm.path

.. autofunction:: clorm.alias

.. autofunction:: clorm.cross

.. autofunction:: clorm.ph_

.. autofunction:: clorm.not_

.. autofunction:: clorm.and_

.. autofunction:: clorm.or_

.. autofunction:: clorm.in_

.. autofunction:: clorm.notin_






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

Clorm provides some helper functions to get clorm facts into and out of the
solver (ie a `clingo.Control` object).

.. autofunction:: clorm.control_add_facts

.. autofunction:: clorm.symbolic_atoms_to_facts

.. autofunction:: clorm.unify


To further simplify the interaction with the solver, Clorm provides a ``clingo``
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

