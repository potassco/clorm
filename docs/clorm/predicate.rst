Mapping Predicates
==================

The heart of an ORM is defining the mapping between the predicates and Python
objects. In ClORM this is acheived by sub-classing the ``Predicate`` class and
specifying term definitions that map to the ASP predicate parameters.

The Basics
----------

It is easiest to explain this mapping by way of a simple example. Consider the
following ground atoms for the predicates ``address/2`` and ``pets/2``. This
specifies that the address of the entity ``dave`` is ``UNSW Sydney`` and
``date`` has 1 pet.

.. code-block:: prolog

   address(dave, "UNSW Sydney").
   pets(dave, 1).

First, it is worth highlighting a few points about ASP syntax. All predicates
must start with a lower-case letter and consist of only alphanumeric
characters. ASP supports three basic types of *terms* (i.e., the parameters of a
predicate); a *constant*, a *string*, and an *integer*. Like the predicate name
requirements, constants consist of only alphanumeric characters with a starting
lower-case character, a string occurs in quotes and can contain arbitrary
characters.

ASP syntax also supports *complex terms* which we will discuss later.

Note: ASP does not support real number values.

The following Python code provides the mapping to the ASP predicates:

.. code-block:: python

   from clorm import *

   class Address(Predicate):
      entity = ConstantTermDefn()
      details = StringTermDefn()

   class Pets(Predicate):
      entity = ConstantTermDefn()
      num = IntegerTermDefn(default=0)

With the above class definitions we can instantiate some objects:

.. code-block:: python

   fact1 = Address(entity="bob", details="Sydney uni")
   fact2 = Pets(entity="bob")
   fact3 = Pets(entity="bill", num=2)

When this Python code is imported into the Clingo solver it will correspond to
the following two *ground atoms* (i.e., facts):

.. code-block:: prolog

   address(bob, "Sydney uni").
   pets(bob, 0).
   pets(bill, 2).

There are some things to note here:

* Predicate names: by default the name of the predicate is determined from the
  class name with the first letter translated to lower-case.
* Term definition order: the order of declared term defintions in the predicate
  class is important.
* Term names: besides the Python keywords, ClORM also disallows the following
  reserved words: ``raw``, ``meta``, ``clone``, ``TermDefn`` as these are used as
  properties or functions of a ``Predicate`` object.
* Constant vs string: ``"bob"`` and ``"Sydney uni"`` are both Python strings but
  because of the declaration of ``entity`` as a ``ConstantTermDefn`` this
  ensures that the Python string ``"bob"`` is treated as an ASP constant. Note
  however that currently it is the users responsibility to ensure that the
  Python string passed to a constant term satisfies the syntactic restriction.
* The use of a default value: all term types support the specification of a
  default value.


Overriding the Predicate Name
-----------------------------

There are many reasons why you might not want to use the default predicate name
mapping. For example, the Python class name that would produce the desired
predicate name may already be taken. Alternatively, you might want to
distinguish between predicates which the same name but different arities; having
predicates with the same name but a different arity is a legitimate and common
practice with ASP programming.

Overriding the default predicate name requires declaring a ``Meta`` sub-class
for the predicate definition.

.. code-block:: python

   from clorm import *

   class Address2(Predicate):
      entity = ConstantTermDefn()
      details = StringTermDefn()

      class Meta:
          name = "address"

    class Address3(Predicate):
      entity = ConstantTermDefn()
      details = StringTermDefn()
      country = StringTermDefn()

      class Meta:
          name = "address"

Instantiating these classes:

.. code-block:: python

   shortaddress = Address2(entity="dave", details="UNSW Sydney")
   longaddress = Address3(entity="dave", details="UNSW Sydney", country="AUSTRALIA")

will produce the following matching ASP facts:

.. code-block:: prolog

   address(dave, "UNSW Sydney").
   address(dave, "UNSW Sydney", "AUSTRALIA").

Unary Predicates
----------------

A unary predicate is a predicate with no parameters and is also a legitimate and
reasonable thing to see in an ASP program. Defining a corresponding Python class
is straightforward:

.. code-block:: python

   from clorm import *

   class AUnary(Predicate):
       pass

   fact = AUnary()

Here every instantiation of ``AUnary`` corresponds to the ASP fact:

.. code-block:: prolog

    aUnary.

Term Definitions
-----------------

ClORM provides a number of standard definitions that specify the mapping between
Clingo's internal representation (some form of ``Clingo.Symbol``) to more
natural Python representations.  ASP has three *simple terms*: *integer*,
*string*, and *constant*, and ClORM provides three definition classes to provide
a mapping to these terms: ``IntegerTermDefn``, ``StringTermDefn``, and
``ConstantTermDefn``.

These classes do not represent instances of the actual terms but rather they
implement functions to perform the necessary data conversions. When instantiated
as part of a predicate definition they also specify a number of options.

Simple Term Definition Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The are currently two options when specifying the Python term definitions for a
predicate. We have already seen the ``default`` option, but there is also the
``index`` option.

Specifying ``index = True`` can affect the behaviour when a ``FactBase`` is
created. We introduce fact bases in the next chapter, surfice to say they are
simply a convenience container for storing sets of facts. They can be thought of
as mini-databases and have some indexing support for improved query performance.

We will discuss fact bases and the index options in the following chapter.

Sub-classing Term Definitions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All term definitions inherit from a base class ``RawTermDefn`` and it's possible
to define arbitrary conversions by sub-classing ``RawTermDefn``, or one it's
existing sub-classes.

By sub-classing a sub-class it is possible to form a data translation chain. To
understand why this is useful it is first necessary to appreciate that because
the ASP language only has three simple term types it is often necessary to
perform some form of data encoding.

As an example, in an application you may want to have a date term for an event
tracking application. So for the Python code you may want to use a Python
``datetime.date`` object. It then becomes a question of how to encode this data
in ASP.

A useful encoding would be to encode a date as a string in **YYYYMMDD**
format. Dates encoded in this format satisfy some useful properties such as the
comparison operators will produce the expected results (e.g., ``"20180101" <
"20180204"``). It also doesn't satisfy some unwanted properties. For example,
encoding the date in the same way as an integer would allow incrementing or
subtracting a date encoded number, which could lead to unwanted values (e.g.,
``20180131 + 1 = 20180132`` does not correspond to a valid date).

Adopting a date encoded string we can consider a fact within a booking
application:

.. code-block:: prolog

    booking("20181231", "NYE party").

This fact can be captured by the following Python ``Predicate`` sub-class
definition:

.. code-block:: python

   from clorm import *

   class Booking(Predicate):
      date = IntegerTermDefn()
      description = StringTermDefn()

It is now up to the user of the ``Booking`` class to perform the necessary
translations to and from a Python ``datetime.date`` objects when necessary:

.. code-block:: python

   import datetime
   nye = datetime.date(2018, 12, 31)
   nyeparty = Booking(date=int(nye.strftime("%Y%m%d")), description="NYE Party")

Here the Python ``nyeparty`` variable corresponds to the encoded ASP event, with
the ``date`` term capturing the string encoding of the date.

In the opposite direction to extract the date it is necessary to turn the date
encoded string into an action ``datetime.date`` object:

.. code-block:: python

   nyedate = datetime.datetime.strptime(str(nyepart.date), "%Y%m%d")

The problem with the above code is that the process of creating and using the
date in the ``Booking`` object is cumbersome and error-prone. You have to
remember to make the correct translation both in creating and reading the
date. Furthermore the places in the code where these translations are made may
be far apart, leading to potential problems when code needs to be refactored.

One solution to this problem is to sub-class the ``StringTermDefn`` and provide
an extra data translation step.

.. code-block:: python

   import datetime
   from clorm import *

   class DateTermDefn(StringTermDefn):
       pytocl = lambda dt: dt.strftime("%Y%m%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

   class Booking(Predicate):
       date=DateTermDefn()
       description = StringTermDefn()

The ``pytocl`` definition specifies the conversion that takes place in the
direction of converting Python data to Clingo data, and ``cltopy`` handles the
opposite direction. Because the ``DateTermDefn`` inherits from ``StringTermDefn``
therefore the ``pytocl`` function must output a Python string object. In the
opposite direction, ``cltopy`` must be passed a Python string object and
performs the desired conversion, in this case producing a ``datetime.date``
object.

Importantly, by using the sub-classed ``DateTermDefn`` the conversion functions
are all captured within the one class definition and interacting with the
objects can be done in a more natural manner.

.. code-block:: python

    nye = datetime.date(2018,12,31)
    nyeparty = Booking(date=nye, description="NYE Party")

    print("Event {}: date {} type {}".format(nyeparty, nyeparty.date, type(nyeparty.date)))

will print the expected output:

.. code-block:: bash

    Event booking(20181231,"NYE Party"): date "2018-12-31" type <class 'datetime.date'>


Dealing with Complex Terms
--------------------------

So far we have shown how to create Python definitions that match predicates with
simple terms or some sub-class that reduces to a simple term. However, in ASP it
is common to also use complex terms (also called *functions*) within a
predicate.

.. code-block:: none

    booking(20181231, location("Sydney", "Australia)).

or a tuple

.. code-block:: none

    booking2(20181231, ("Sydney", "Australia)).

To support this flexibility ClORM introduces a ``ComplexTerm`` class.  A complex
term is defined identically to a predicate, but in this case ``ComplexTerm``
needs to be sub-classed. Just like with simple terms, a term definition is
necessary to specify the translation from a ``Clingo.Symbol`` object to the
``ComplexTerm`` object.

While it is possible to manually specify this translation by sub-classing
``RawTermDefn`` and specifying the translation functions, fortunately it is
possible to generate such a class automatically from a ``ComplexTerm``
sub-class. This definition is exposed as a ``TermDefn`` property.

.. code-block:: python

   from clorm import *

   class Location(ComplexTerm):
      city = StringTermDefn()
      country = StringTermDefn()

   class Booking(Predicate):
       date=IntegerTermDefn()
       location=Location.TermDefn()


   class LocationTuple(ComplexTerm):
      city = StringTermDefn()
      country = StringTermDefn()
      class Meta:
         istuple = True

   class Booking2(Predicate):
       date=IntegerTermDefn()
       location=LocationTuple.TermDefn(
		default=LocationTuple(city="Sydney", country="Australia"))

The ``Booking`` and ``Booking2`` Python classes correspond to the
signature of the above example predicates ``booking/2`` and ``booking2/2``.

Note: as with the simple term definitions it is possible to provide an optional
``default`` parameter. However, currently, the ``index`` parameter is not
supported.


Dealing with Raw Clingo Symbols
-------------------------------

As well as supporting simple and complex terms it is sometimes useful to deal
with the objects created through the underlying Clingo Python API.

.. _raw-symbol-label:

Raw Clingo Symbols
^^^^^^^^^^^^^^^^^^

The Clingo API uses ``clingo.Symbol`` objects for dealing with facts; and there
are a number of functions for creating the appropriate type of symbol objects
(i.e., ``clingo.Function()``, ``clingo.Number()``, ``clingo.String()``).

In essence the ClORM ``Predicate`` and ``ComplexTerm`` classes simply provide a
more convenient and intuitive way for constructing and dealing with these
``clingo.Symbol`` objects. In fact the underlying symbols can be accessed using
the ``raw`` property of a ``Predicate`` or ``ComplexTerm`` object.

.. code-block:: python

   from clorm import *    # Predicate, ConstantTermDefn, StringTermDefn
   from clingo import *   # Function, String

   class Address(Predicate):
      entity = ConstantTermDefn()
      details = StringTermDefn()

   address = Address(entity="dave", details="UNSW Sydney")

   raw_address = Function("address", [Function("dave",[]), String("UNSW Sydney")])

   assert address.raw == raw_address

ClORM ``Predicate`` objects can also be constructed from the raw symbol
objects. So assuming the above python code.

.. code-block:: python

   address_copy = Address(raw=raw_address)

Note: not every raw symbol will *unify* with a given ``Predicate`` or
``ComplexTerm`` class. If the raw constructor fails to unify a symbol with a
predicate definition then a ``ValueError`` exception will be raised.

Integrating Clingo Symbols into a Predicate Definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are some cases when it might be convenient to combine the simplicity and
the structure of the ClORM predicate interface with the flexibility of the
underlying Clingo symbol API. For this it is possible to use the
``RawTermDefn`` base class itself.

For example when modeling dynamic domains it is often useful to provide a
predicate that defines what *fluents* are true at a given time point, but to
allow the fluents themselves to have an arbitrary form.

.. code-block:: prolog

   time(1..5).

   true(X,T+1) :- fluent(X), not true(X,T).

   fluent(light(on)).
   fluent(robotlocation(roby, kitchen)).

   true(light(on), 0).
   true(robotlocation(roby,kitchen), 0).

In this example the two instances of the ``true`` predicate have a different
signature for the first term (i.e., ``light/1`` and ``robotlocation/2``). While
the definition of the fluent is important at the ASP level, however, at the
Python level we may not be interested in the structure of the fluent, only
whether it is true or not. Hence we can treat the fluents themselves as raw
Clingo symbol objects.

.. code-block:: python

   from clorm import *

   class True(Predicate):
      fluent = RawTermDefn()
      time = IntegerTermDefn()

Accessing the value of the ``fluent`` simply returns the raw Clingo symbol. Also
the ``RawTermDefn`` has the useful property that it will unify with any
``Clingo.Symbol`` object.


