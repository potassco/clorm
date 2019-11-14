.. _experimental:

Experimental Features
=====================

.. warning::

   The following are experimental features that may change between minor library
   version increments. They shouldn't be considered part of the official Clorm
   API.

Reusable Components
-------------------

**This is a work in progress**

The goal is to slowly build up a comprehensive set of Clorm components
(definitions and functions) that could be used to build readable ASP programs
that can be easily integrated into Python applications.

Library components that are currently in the works:

- **date**: Contains definitions and functions for dealing with dates and
  enumerated dates.
- **timeslot**: This library will help to deal with blocks of time; for example
  dividing a day into 15 minute blocks.


JSON Encoding and Decoding
--------------------------

Clorm provides functions for encoding and decoding facts as JSON. The motivation
is to be able to pass around facts between different processes. For example, you
may want to generate a problem instance as part of a main web application but
then pass off the problem instance to a worker processes that actually calls the
solver.

.. note::

   The JSON encoding of the clingo.Symbol objects generated here is not the same
   as running clingo with the ``--outf=2`` argument. The output here is intended
   as an format for passing around facts between processes and not to be
   particularly human readable. In contrast the clingo output in more human
   readable but would require parsing to regenerate the original symbol objects.

The ``FactBaseCoder`` class is a helper class to be able to encode/decode JSON for
particular Predicate sub-classes. The predicates can be supplied at
construction.

.. code-block:: python

   from clorm import Predicate, IntegerField, StringField
   from clorm.json import FactBaseCoder

   class Afact(Predicate):
        aint = IntegerField()
	astr = StringField()

   fb_coder = FactBaseCoder([Afact])

Alternatively, the ``FactBaseCoder`` can also be used as a decorator to register
predicates.

.. code-block:: python

   from clorm import Predicate, IntegerField, StringField
   from clorm.json import FactBaseCoder

   fb_coder = FactBaseCoder()

   class Fun(ComplexTerm):
	aint = IntegerField()
        astr = StringField()

   class Tup(ComplexTerm):
	aint = IntegerField()
        astr = StringField()
        class Meta: is_tuple = True

   @fb_coder.register
   class Afact(Predicate):
	aint = IntegerField()
        afun = Fun.Field()

   @fb_coder.register
   class Bfact(Predicate):
	astr = StringField()
        atup = Tup.Field()

Once the fact coder has been created and the appropriate predicates registered,
it then provides ``encoder`` and ``decoder`` member functions that can be used
with the standard Python JSON functions.

Assuming the above code:

.. code-block:: python

   import json

   afact1 = Afact(aint=10, afun=Fun(aint=1, astr="a"))
   afact2 = Afact(aint=20, afun=Fun(aint=2, astr="b"))
   bfact1 = Bfact(astr="aa", atup=Tup(aint=1, astr="a"))
   bfact2 = Bfact(astr="bb", atup=Tup(aint=2, astr="b"))

   json_str = json.dumps([afact1,afact2,bfact1,bfact2], default=fb_coder.encoder)

   facts = json.loads(json_str, object_hook=fb_coder.decoder)

As a convenience the fact coder provides member functions: ``dump``, ``dumps``,
``load``, ``loads`` that call the respective json functions with the appropriate
encoder and decoder functions. So the above calls to the json functions can be
simplified to:

.. code-block:: python

   json_str = fb_coder.dumps([afact1,afact2,bfact1,bfact2])

   facts = fb_coder.loads(json_str)
