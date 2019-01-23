Mapping Predicates
==================

The heart of an ORM is defining the mapping between the predicates and Python
objects. In ClORM this is acheived by sub-classing the ``Predicate`` class and
defining the fields that map to the ASP predicate parameters.

The Basics
----------

It is easiest to explain this mapping by way of a simple example. Consider the
following ground atoms for the predicates ``address/2`` and ``pets/2``. This
specifies that the address of the entity ``dave`` is ``UNSW Sydney`` and
he/she/it has 1 pet.

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

ASP syntax also supports *complex terms* which we will discuss later. Note: ASP
does not support real number values.

The following Python code provides the mapping to the ASP predicates:

.. code-block:: python

   from clorm import *

   class Address(Predicate):
      entity = ConstantField()
      details = StringField()

   class Pets(Predicate):
      entity = ConstantField()
      num = IntegerField(default=0)

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
* Field order: the order of declared fields in the predicate class definition is
  important.
* Field names: besides the Python keywords that should not be used as keywords,
  ClORM also disallows three reserved words: ``raw``, ``meta``, and ``clone`` as
  these are used as properties or functions of a ``Predicate`` object.
* Constant vs string: ``"bob"`` and ``"Sydney uni"`` are both Python strings but
  because of the declaration of ``entity`` as a ``ConstantField`` this ensures
  that the Python string ``"bob"`` is treated as an ASP constant. Note:
  currently it is the users responsibility to ensure that the Python string
  passed to a constant field satisfies the syntactic restriction.
* The use of a default value: all the simple field types support the
  specification of a default value.


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
      entity = ConstantField()
      details = StringField()

      class Meta:
          name = "address"

    class Address3(Predicate):
      entity = ConstantField()
      details = StringField()
      country = StringField()

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

Simple Field
------------

``IntegerField``, ``StringField``, and ``ConstantField`` are all simple fields
as they correspond to the basic terms of ASP syntax; *integer*, *string*, and
*constant*.

Simple Field Options
^^^^^^^^^^^^^^^^^^^^

The are currently two options when specifying the Python field definitions for a
predicate. We have already seen the ``default`` option, but there is also the
``index`` option.

Specifying ``index = True`` can affect the behaviour when a ``FactBase`` is
created. We introduce fact bases in the next chapter, surfice to say they are
simply a convenience container for storing sets of facts. They can be thought of
as mini-databases and have some indexing support for improved query performance.

We will discuss fact bases and the index options in the following chapter.


Sub-classing Simple Fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

As we have seen the ASP language only supports three simple term types;
*constant*, *integer*, and *string*. Hence when translating any single valued
Python data type into ASP it must be encoded within one of these
types. Consequently, there may need to be some form of data format/type
translation when converting between ASP and Python.

As an example, in an application you may want to have a date field for an event
tracking application. So for the Python code you may want to use a Python
``datetime.date`` object. However, as ASP only supports the three simple term
types so using the date within the ASP code will mean some form of format
encoding.

An obvious encoding would be to encode a date as a string in **YYYYMMDD**
format. Dates encoded in this format satisfy some useful properties such as the
comparison operators will produce the expected results (e.g., ``"20180101" <
"20180204"``). Note: encoding the date in the same way as an integer would also
satisfy the above properties but would also allow for some unwanted
behaviour. In particular, incrementing or subtracting a date encoded number may
lead to a value with no corresponding date (e.g., ``20180131 + 1 = 20180132``
does not correspond to a valid date).

As a more concrete example, consider the following ASP encoded date in an event
booking application:

.. code-block:: prolog

    booking("20181231", "NYE party").

This could be encoded with the corresponding Python ``Predicate`` sub-class
definition:

.. code-block:: python

   from clorm import *

   class Booking(Predicate):
      date = IntegerField()
      description = StringField()

Since the standard Python way of dealing with dates is to use the
``datetime.date`` class so creating events using Python code would need to look
something like:

.. code-block:: python

   import datetime
   nye = datetime.date(2018, 12, 31)
   nyeparty = Booking(date=int(nye.strftime("%Y%m%d")), description="NYE Party")

Here the Python ``nyeparty`` variable corresponds to the encoded ASP event, with
the ``date`` field capturing the string encoding of the date.

Now imagine that at a latter point in your code you want to use the date stored
in the booking object. To do this you need to read the integer and translate it
back into a Python date object:

.. code-block:: python

   nyedate = datetime.datetime.strptime(str(nyepart.date), "%Y%m%d")

The problem with the above code is that the process of creating and using the
date in ``Booking`` object is cumbersome and error-prone. You have to remember
to make the correct translation both in creating and reading the
date. Furthermore the places in the code base where these translations are made
may be far apart, leading to potential problems when code needs to be
refactored.

To help with this problem ClORM allows the simple fields to be sub-classed and
input/output functions specified to perform the appropriate type conversions.

.. code-block:: python

   import datetime
   from clorm import *

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y%m%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

   class Booking(Predicate):
       date=DateField()
       description = StringField()

The ``pytocl`` definition specifies the conversion that takes place in the
direction of converting Python data to Clingo data, and ``cltopy`` handles the
opposite direction. Because the ``DateField`` inherits from ``StringField``
therefore the ``pytocl`` function must output a Python string object. In the
opposite direction, ``cltopy`` must be passed a Python string object and
performs the desired conversion, in this case producing a ``datetime.date``
object.

By using the sub-classed ``DateField`` the conversion functions are all captured
within the one class definition and the interacting with the objects can be done
in a more natural manner.

.. code-block:: python

    nye = datetime.date(2018,12,31)
    nyeparty = Booking(date=nye, description="NYE Party")

    print("Event {}: date {} type {}".format(nyeparty, nyeparty.date, type(nyeparty.date)))

will print the output:

.. code-block:: bash

    Event booking(20181231,"NYE Party"): date "2018-12-31" type <class 'datetime.date'>


Dealing with Complex Terms
--------------------------

So far we have shown how to create Python definitions that match predicates with
simple terms. However, in ASP it is common to also use complex terms (also
called *functions*) within a predicate.

.. code-block:: none

    booking(20181231, location("Sydney", "Australia)).

or a tuple

.. code-block:: none

    booking2(20181231, ("Sydney", "Australia)).

To support this flexibility ClORM introduces the ``ComplexTerm`` and
``ComplexField`` sub-classes. A complex term is defined identically to a
predicate, but in this case ``ComplexTerm`` needs to be
sub-classed. ``ComplexField`` is then used to associate the ``ComplexTerm``
definition with a specific field.

.. code-block:: python

   from clorm import *

   class Location(ComplexTerm):
      city = StringField()
      country = StringField()

   class Booking(Predicate):
       date=IntegerField()
       location=ComplexField(defn=Location)


   class LocationTuple(ComplexTerm):
      city = StringField()
      country = StringField()

      class Meta:
         istuple = True

   class Booking2(Predicate):
       date=IntegerField()
       location=ComplexFleid(defn=LocationTuple,
                             default=LocationTuple(city="Sydney", country="Australia"))

When specifying a ``ComplexField`` the ``defn`` parameter must be set to the
desired ComplexTerm class. A default value can also be set.

Dealing with Raw Clingo Symbols
-------------------------------

As well as allowing for complex terms ClORM also provides support for dealing
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

   from clorm import *    # Predicate, ConstantField, StringField
   from clingo import *   # Function, String

   class Address(Predicate):
      entity = ConstantField()
      details = StringField()

   address = Address(entity="dave", details="UNSW Sydney")

   raw_address = Function("address", [Function("dave",[]), String("UNSW Sydney")])

   assert address.raw == raw_address

ClORM ``Predicate`` objects can also be constructed from the raw symbol
objects. So assuming the above python code.

.. code-block:: python

   address_copy = Address(raw=raw_address)

Note: not every raw symbol will match (technically *unify*) with a given
``Predicate`` definition. It the raw constructor fails to unify a symbol with a
predicate definition a ``ValueError`` exception will be raised.

Integrating Clingo Symbols into a Predicate Definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are some cases when it might be convenient to combine the simplicity and
the structure of the ClORM predicate interface with the flexibility of the
underlying Clingo symbol API. For this ClORM introduces a ``RawField``.

For example when modeling dynamic domains we can use a predicate to define what
*fluents* are true at a given time point.

.. code-block:: prolog

   time(1..5).

   true(X,T+1) :- fluent(X), not true(X,T).

   fluent(light(on)).
   fluent(robotlocation(roby, kitchen)).

   true(light(on), 0).
   true(robotlocation(roby,kitchen), 0).

In this example the two instances of the ``true`` predicate have a different
signature for the first term. While the definition of the fluent is important at
the ASP level, however, at the Python level we may not be interested in what the
fluents are, only whether they are true or not. Hence we can treat the fluents
themselves as a raw Clingo symbol object.


.. code-block:: python

   from clorm import *

   class True(Predicate):
      fluent = RawField()
      time = IntegerField()

Accessing the value of the ``fluent`` simply returns the raw Clingo symbol. Also
the ``RawField`` has the property that it will unify with any symbol object.


