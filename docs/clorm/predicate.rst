Predicates and Fields
=====================

The heart of an ORM is defining the mapping between the predicates and Python
objects. In Clorm this is acheived by sub-classing the ``Predicate`` class and
specifying fields that map to the ASP predicate parameters.

The Basics
----------

It is easiest to explain this mapping by way of a simple example. Consider the
following ground atoms for the predicates ``address/2`` and ``pets/2``. This
specifies that the address of the entity ``dave`` is ``"UNSW Sydney"`` and
``dave`` has 1 pet.

.. code-block:: prolog

   address(dave, "UNSW Sydney").
   pets(dave, 1).


.. note::

   A note on ASP syntax. All predicates must start with a lower-case letter and
   consist of only alphanumeric characters (and underscore). ASP supports three
   basic types of *terms* (i.e., the parameters of a predicate); a *constant*, a
   *string*, and an *integer*. Like the predicate names, constants consist of
   only alphanumeric characters (and underscore) with a starting lower-case
   character. This is different to a string, which is quoted and can contain
   arbitrary characters including spaces.

   ASP syntax also supports *complex terms* (also called *functions* but we will
   avoid this usage to prevent confusion with Python functions) which we will
   discuss later. Note, however that ASP does not support real number values.

To provide a mapping that satisfies the above predicate we need to sub-class the
``Predicate`` class and use the ``ConstantField`` and ``StringField``
classes. These field classes, including the ``IntegerField``, are all
sub-classes of the base ``RawField`` class.

.. code-block:: python

   from clorm import Predicate, ConstantField, StringField

   class Address(Predicate):
      entity = ConstantField
      details = StringField

   class Pets(Predicate):
      entity = ConstantField
      num = IntegerField(default=0)

Typically, when instantiating a predicate all field values must be provided. The
exception is when the field has been defined with a default value, such as with
the above definition for the ``num`` field of the ``Pets``. So, with the above
class definitions we can instantiate some objects:

.. code-block:: python

   fact1 = Address(entity="bob", details="Sydney uni")
   fact2 = Pets(entity="bob")
   fact3 = Pets(entity="bill", num=2)

These object correspond to the following ASP *ground atoms* (i.e., facts):

.. code-block:: prolog

   address(bob, "Sydney uni").
   pets(bob, 0).
   pets(bill, 2).

There are some things to note here:

* *Predicate names*: ASP uses standard logic-programming syntax, which requires
  that the names of all predicate/complex-terms must begin with a lower-case
  letter and can contain only alphanumeric characters or underscore. Unless
  overriden, Clorm will automatically generate a predicate name for a
  ``Predicate`` sub-class by transforming the class name based on some simple rules:

  * If the first letter is a lower-case character then this is a valid predicate
    name so the name is left unchanged (e.g., ``myPredicate`` =>
    ``myPredicate``).

  * Otherwise, replace any sequence of upper-case only characters that occur at
    the beginning of the string or immediately after an underscore with
    lower-case equivalents. The sequence of upper-case characters can include
    non-alphabetic characters (eg., numbers) and this will still be treated as a
    single sequence of upper-case characters.

  * The above criteria covers a number of common naming conventions:

    * Snake-case: ``My_Predicate`` => ``my_predicate``, ``MY_Predicate`` =>
      ``my_predicate``, ``My_Predicate_1A`` => ``my_predicate_1a``,

    * Camel-case: ``MyPredicate`` => ``myPredicate``, ``MyPredicate1A`` =>
      ``myPredicate1A``.

    * Acronym: ``TCP1`` => ``tcp1``.

* *Field order*: the order of declared term defintions in the predicate
  class is important.

* *Field names*: besides the Python keywords, Clorm also disallows the following
  reserved words: ``raw``, ``meta``, ``clone``, ``Field`` as these are used as
  properties or functions of a ``Predicate`` object.

* *Constant vs string*: In the above example ``"bob"`` and ``"Sydney uni"`` are
  both Python strings but because of the ``entity`` field is declared as a
  ``ConstantField`` this ensures that the Python string ``"bob"`` is treated as
  an ASP constant. Note, currently it is the users' responsibility to ensure
  that the Python string passed to a constant term satisfies the syntactic
  restriction.

* The use of a *default value*: all term types support the specification of a
  default value.

* If the specified default is a function then this function will be called (with
  no arguments) when the predicate/complex-term object is instantiated. This can
  be used to generated unique ids or a date/time stamp.

Overriding the Predicate Name
-----------------------------

As mentioned above, by default the predicate name is calculated from the
corresponding class name by transforming the class name to match a number of
common naming conventions. However, it is also possible to over-ride the default
predicate name with an explicit name.

There are many reasons why you might not want to use the default predicate name
mapping. For example, the Python class name that would produce the desired
predicate name may already be taken. Alternatively, you might want to
distinguish between predicates with the same name but different arities. Note:
having predicates with the same name and different arities is a legitimate and
common practice with ASP programming.

Overriding the default predicate name requires declaring a ``Meta`` sub-class
for the predicate definition.

.. code-block:: python

   from clorm import *

   class Address2(Predicate):
      entity = ConstantField
      details = StringField

      class Meta:
          name = "address"

    class Address3(Predicate):
      entity = ConstantField
      details = StringField
      country = StringField

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

The important thing to note here is that every instantiation of ``AUnary``
will correspond to the same ASP fact:

.. code-block:: prolog

    aUnary.

Complex Terms
-------------

So far we have shown how to create Python definitions that match predicates with
simple terms. However, in ASP it is common to also use complex terms within a
predicate, such as:

.. code-block:: prolog

    booking("2018-12-31", location("Sydney", "Australia")).

The Clorm ``Predicate`` class definition is able to support the flexiblity
required to deal with complex terms. A ``ComplexTerm`` class is introduced
simply as an alias for the ``Predicate`` class.

.. code-block:: python

   from clorm import Predicate, ComplexTerm, StringField

   class Location(ComplexTerm):
      city = StringField
      country = StringField

The definition for a complex term can be included within a new ``Predicate``
definition by using the ``Field`` property of the ``ComplexTerm`` sub-class.

.. code-block:: python

   class Booking(Predicate):
       date=StringField
       location=Location.Field

This ``Field`` property returns a ``RawField`` sub-class that is generated
automatically when the ``Predicate`` sub-class is defined. It provides the
functions to automatically convert to, and from, the Predicate sub-class
instances and the Clingo symbol objects.

The predicate class containing complex terms can be instantiated in the obvious
way:

.. code-block:: python

   bk=Booking(date="2018-12-31", location=Location(city="Sydney",country="Australia"))

Note: as with the field definition for simple terms it is possible to specify a
complex field definition with ``default`` or ``index`` parameters. For example,
the above ``Booking`` class could be replaced with:

.. code-block:: python

   class Booking(Predicate):
       date=StringField
       location=Location.Field(index=True,
		default=LocationTuple(city="Sydney", country="Australia"))


Note: From a code readability and conceptual stand point it may be convenient to
treat predicates and complex terms as separate classes, however there are cases
where this separation breaks down. For example when dealing with the
*reification* of facts there is nothing to be gained by providing two
definitions for the predicate and complex term versions of the same non logical
term:

.. code-block:: prolog

    p(q(1)).
    q(1) :- p(q(1)).

In this example ``q/1`` is both a complex term and predicate and when providing
the Python Clorm mapping it is simpler not to separate the two versions:

.. code-block:: python

   class Q(Predicate):
      a = IntegerField

   class P(Predicate):
      a = Q.Field


Negative Facts
--------------

ASP follows standard logic programming syntax and treats the ``not`` keyword as
**default negation** (also **negation as failure**). Using default negation is
important to ASP programming as it can lead to more readable and compact
modelling of a problem.

However, there may be times when having an explicit notion of negation is also
useful, and ASP/Clingo does have support for **classical negation**; indicated
syntactically using the ``-`` symbol:

.. code-block:: prolog

    { a(1..2); b(1..2) }.
    -b(N) :- a(N).
    -a(N) :- b(N).

The above program chooses amongst the ``a/1`` and ``b/1`` predicates, then for
every positive ``a/1`` fact, the corresponding ``b/1`` fact is negated and
vice-versa. This will generate nine stable models. For example, if ``a(2)`` and
``b(1)`` are chosen, then the corresponding negative literals will be ``-b(2)``
and ``-a(1)`` respectively.

Note: Clingo supports negated literals as well as terms. However, tuples cannot be negated.

.. code-block:: prolog

   f(-g(a)).   % This is valid
   f(-(a,b)).  % Error!!!

Clorm supports negation for any fact or term that can be negated by
Clingo. Specifying a negative literal simply involves setting ``sign=False``
when instantiating the Predicate (or ComplexTerm). Note: unlike the field
parameters, the ``sign`` parameter must be specified as a named parameter and
cannot be specified using positional arguments.

.. code-block:: python

   class P(Predicate):
       a = IntegerField

   neg_p1 = P(a=1,sign=False)
   neg_p1_alt = P(1,sign=False)
   assert neg_p1 == neg_p1_alt

Once instantiated, checking whether a fact (or a complex term) is negated can be
determined using the ``sign`` attribute of Predicate instance.

.. code-block:: python

   assert neg_p1.sign == False

Finally, for finer control of the unification process, a Predicate/ComplexTerm
can be specified to only unify with either positive or negative facts/terms by
setting a ``sign`` meta attribute declaration.

.. code-block:: python

   class P_pos(Predicate):
       a = IntegerField
       class Meta:
          sign = True
	  name = "p"

   class P_neg(Predicate):
       a = IntegerField
       class Meta:
          sign = False
	  name = "p"

   % Instatiating facts
   pos_p = P_pos(1)                     % Ok
   neg_p_fail = P_pos(1,sign=False)     % throws a ValueError

   neg_p = P_neg(1)                     % Ok
   pos_p_fail = P_neg(1,sign=False)     % throws a ValueError

   % Unifying against raw Clingo positive and negative facts
   raws = [Function("p",Number(1)), Function("p",Number(1),positive=False)]
   fb = unify([P_pos,P_neg], raw)
   assert fb.select(F_pos).get() == [pos_p]
   assert fb.select(F_neg).get() == [neg_p]

Field Definitions
-----------------

Clorm provides a number of standard definitions that specify the mapping between
Clingo's internal representation (some form of ``Clingo.Symbol``) to more
natural Python representations.  ASP has three *simple terms*: *integer*,
*string*, and *constant*, and Clorm provides three standard definition classes
to provide a mapping to these fields: ``IntegerField``, ``StringField``, and
``ConstantField``.

Clorm also provides a ``SimpleField`` class that can match to any simple
term. This is useful when the parameter of a defined predicate can contain
arbitrary simple term types. Clorm takes care of converting the ASP string,
constant or integer to a Python string or integer object. Note that both ASP
strings and constants are both converted to Python string objects.

In order to convert from a Python string object to an ASP string or constant,
``SimpleField`` uses a regular expression to determine if the string matches the
pattern of a constant and treats it accordingly. For this reason ``SimpleField``
should be used with care in order to ensure expected behaviour, and using the
distinct field types is often preferable.

.. note::

   It is worth highlighting that in the above predicate declarations, the field
   classes do not represent instances of the actual fields. For example, the
   date string "2018-12-31" is not stored in a ``StringField`` object. Rather
   the field classes provide the implementation of the functions that perform
   the necessary data conversions. Instantiating a field class in a predicate
   definition is only necessary to allow options to be specified, such as
   default values or indexing.

Simple Term Definition Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are currently two options when specifying the Python fields for a
predicate. We have already seen the ``default`` option, but there is also the
``index`` option.

Specifying ``index = True`` can affect the behaviour when a ``FactBase``
container objects are created. While the ``FactBase`` class will be discussed in
greater detail in the next chapter, here we simply note that it is a convenience
container for storing sets of facts. They can be thought of as mini-databases
and have some indexing support for improved query performance.

Sub-classing Field Definitions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All field classes inherit from a base class ``RawField`` and it's possible to
define arbitrary data conversions by sub-classing ``RawField``. Clorm provides
the standard sub-classes ``StringField``, ``ConstantField``, and
``IntegerField``. Clorm also automatically generates an appropriate sub-class
for every ``ComplexTerm`` definition.

However, it is sometimes also useful to explicitly sub-class the ``RawField``
class, or sub-class one of its sub-classes. By sub-classing a sub-class it is
possible to form a *data conversion chain*. To understand why this is useful we
consider an example of specifying a date field.

Consider the example of an application that needs a date term for an event
tracking application. From the Python code perspective it would be natural to
use Python ``datetime.date`` objects. However, it then becomes a question of how
to encode these Python date objects in ASP (noting that ASP only has three
simple term types).

A useful encoding would be to encode a date as a string in **YYYYMMDD** format
(or **YYYY-MM-DD** for greater readability). Dates encoded in this format
satisfy some useful properties such as the comparison operators will produce the
expected results (e.g., ``"20180101" < "20180204"``). A string is also
preferable to using a similiarly encoded integer value.  For example, encoding
the date in the same way as an integer would allow incrementing or subtracting a
date encoded number, which could lead to unwanted values (e.g., ``20180131 + 1 =
20180132`` does not correspond to a valid date).

So, adopting a date encoded string we can consider a date based fact for the
booking application that simply encodes that there is a New Year's eve party on
the 31st December 2018.

.. code-block:: prolog

   booking("2018-12-31", "NYE party").

Using Clorm this fact can be captured by the following Python ``Predicate``
sub-class definition:

.. code-block:: python

   from clorm import *

   class Booking(Predicate):
      date = StringField
      description = StringField

However, since we encoded the date as simply a ``StringField`` it is now up to
the user of the ``Booking`` class to perform the necessary translations to and
from a Python ``datetime.date`` objects when necessary. For example:

.. code-block:: python

   import datetime
   nye = datetime.date(2018, 12, 31)
   nyeparty = Booking(date=int(nye.strftime("%Y-%m-%d")), description="NYE Party")

Here the Python ``nyeparty`` variable corresponds to the encoded ASP event, with
the ``date`` term capturing the string encoding of the date.

In the opposite direction to extract the date it is necessary to turn the date
encoded string into an actual ``datetime.date`` object:

.. code-block:: python

   nyedate = datetime.datetime.strptime(str(nyepart.date), "%Y-%m-%d")

The problem with the above code is that the process of creating and using the
date in the ``Booking`` object is cumbersome and error-prone. You have to
remember to make the correct translation both in creating and reading the
date. Furthermore the places in the code where these translations are made may
be far apart, leading to potential problems when code needs to be refactored.

The solution to this problem is to create a sub-class of ``RawField`` that
performs the appropriate data conversion. However, sub-classing ``Rawfield``
directly requires dealing with raw Clingo ``Symbol`` objects. A better
alternative is to sub-class the ``StringField`` class so you need to only deal
with the string to date conversion.

.. code-block:: python

   import datetime
   from clorm import *

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y-%m-%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y-%m-%d").date()

   class Booking(Predicate):
       date=DateField
       description = StringField

The ``pytocl`` definition specifies the conversion that takes place in the
direction of converting Python data to Clingo data, and ``cltopy`` handles the
opposite direction. Because the ``DateField`` inherits from ``StringField``
therefore the ``pytocl`` function must output a Python string object. In the
opposite direction, ``cltopy`` must be passed a Python string object and
performs the desired conversion, in this case producing a ``datetime.date``
object.

With the newly defined ``DateField`` the conversion functions are all captured
within the one class definition and interacting with the objects can be done in
a more natural manner.

.. code-block:: python

    nye = datetime.date(2018,12,31)
    nyeparty = Booking(date=nye, description="NYE Party")

    print("Event {}: date {} type {}".format(nyeparty, nyeparty.date, type(nyeparty.date)))

will print the expected output:

.. code-block:: bash

    Event booking(20181231,"NYE Party"): date "2018-12-31" type <class 'datetime.date'>


.. note::

   The ``pytocl`` and ``cltopy`` functions can potentially be passed bad
   input. For example when converting a clingo String symbol to a date object
   the passed string may not correspond to an actual date. In such cases these
   functions can legitamately throw either a ``TypeError`` or a ``ValueError``
   exception. These exceptions will be treated as a failure to unify when trying
   to unify clingo symbols to facts. However, any other exception is passed
   through as a genuine error. This should be kept in mind if you are writing
   your own field class.

Restricted Sub-class of a Field Definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Another reason to sub-class a field definition is to restrict the set of values
that the field can hold. For example you could have an application where an
argument of a predicate is restricted to a specific set of constants, such as
the days of the week.

.. code-block:: prolog

    cooking(monday, "Jane"). cooking(tuesday, "Bill"). cooking(wednesday, "Bob").
    cooking(thursday, "Anne"). cooking(friday, "Bill").
    cooking(saturday, "Jane"). cooking(sunday, "Bob").

When defining a predicate corresponding to cooking/2 it is possible to simply use a
``ConstantField`` field for the days.

.. code-block:: python

   class Cooking1(Predicate):
      dow = ConstantField
      person = StringField
      class Meta: name = "cooking"

However, this would potentiallly allow for creating erroneous instances that
don't correspond to actual days of the week (for example, with a spelling
mistake):

.. code-block:: python

   ck = Cooking1(dow="mnday",person="Bob")

In order to avoid these errors it is necessary to subclass the ``ConstantField``
in order to restrict the set of values to the desired set. Clorm provides a
helper function ``refine_field`` for this use-case. It dynamically defines a new
class that restricts the values of an existing field class.

.. code-block:: python

   DowField = refine_field("DowField", ConstantField,
      ["sunday","monday","tuesday","wednesday","thursday","friday","saturday"])

   class Cooking2(Predicate):
      dow = DowField
      person = StringField
      class Meta: name = "cooking"

   try:
      ck = Cooking2(dow="mnday",person="Bob")  # raises a TypeError exception
   except TypeError:
      print("Caught exception")

.. note::

   The ``refine_field`` function can also be called with only two arguments,
   rather than three, by ignoring the name for the generated class. In this case
   an anonymously generated name will be used.

As well as explictly specifying the set of refinement values, ``refine_field``
also provides a more general approach where a function/functor/lambda can be
provided. This function must take a single input and return ``True`` if that
value is valid for the field. For example, to define a field that accepts only
positive integers:

.. code-block:: python

   PosIntField = refine_field("PosIntField", NumberField, lambda x : x >= 0)

Finally, it should be highlighted that this mechanism for defining a field
restriction works not just for validating the inputs into an ASP program. It can
also be used to filter the outputs of the ASP solver as the invalid field values
will not *unify* with the predicate.

For example, in the above program you can separate the cooks on the weekend
from the weekday cooks.

.. code-block:: python

   WeekendField = refine_field("WeekendField", ConstantField,
      ["sunday","saturday"])
   WeekdayField = refine_field("WeekdayField", ConstantField,
      ["monday","tuesday","wednesday","thursday","friday"])

   class WeekendCooking(Predicate):
      dow = WeekendField
      person = StringField
      class Meta: name = "cooking"

   class WeekdayCooking(Predicate):
      dow = WeekdayField
      person = StringField
      class Meta: name = "cooking"


Using Positional Arguments
--------------------------

So far we have shown how to create Clorm predicate and complex term instances
using keyword arguments that match their defined field names, as well as
accessing the arguments via the fields as named properties. For example:

.. code-block:: python

   from clorm import *

   class Contact(Predicate):
       cid=IntegerField
       name=StringField

   c1 = Contact(cid=1, name="Bob")

   assert c1.cid == 1
   assert c1.name == "Bob"

However, Clorm also supports creating and accessing the field data using
positional arguments:


.. code-block:: python

   c2 = Contact(2,"Bill")

   assert c2[0] == 2
   assert c2[1] == "Bill"

While Clorm does support the use of positional arguments for predicates,
nevertheless it should be used sparingly because it can lead to brittle code
that can be hard to debug, and can also be more difficult to refactor as the ASP
program changes. However, there are genuine use-cases where it can be convenient
to use positional arguments. In particular when defining very simple tuples,
where the position of arguments is unlikely to change as the ASP program
changes. We discuss Clorm's support for these cases in the following section.

Working with Tuples
-------------------

Tuples are a special case of complex terms that often appear in ASP
programs. For example:

.. code-block:: none

   booking("2018-12-31", ("Sydney", "Australia)).

For Clorm tuples are simply a ``ComplexTerm`` sub-class where the name of the
corresponding predicate is empty. While this can be set using an ``is_tuple``
property of the complex term's meta class, Clorm also provides specialised
support using the more intuitive syntax of a Python tuple. For example, a
predicate definition that unifies with the above fact can be defined simply
(using the ``DateField`` defined earlier):

.. code-block:: python

   class Booking(Predicate):
       date=DateField
       location=(StringField,StringField)

Here the ``location`` field is defined as a pair of string fields, without
having to explictly define a separate ``ComplexTerm`` sub-class that corresponds
to this pair. To instantiate the ``Booking`` class a Python tuple can also be
used for the values of ``location`` field. For example, the following creates a
``Boooking`` instance corresponding to the ``booking/2`` fact above:

.. code-block:: python

   bk = Booking(date=datetime.date(2018,12,31), location=("Sydney","Australia"))


While it is unnecessary to define a seperate ``ComplexTerm`` sub-class
corresponding to the tuple, internally this is in fact exactly what Clorm
does. Clorm will transform the above definition into something similar to the
following:

.. code-block:: python

   class SomeAnonymousName(ComplexTerm):
      city = StringField
      country = StringField
      class Meta:
         is_tuple = True

   class Booking(Predicate):
       date=DateField
       location=SomeAnonymousName.Field

Here the ``ComplexTerm`` has an internal ``Meta`` class with the property
``is_tuple`` set to ``True``. This means that the ``ComplexTerm`` will be
treated as a tuple rather than a complex term with a function name.

One important difference between the implicitly defined and explicitly defined
versions of a tuple is that the explicit version allows for field names to be
given, while the implicit version will have automatically generated
names. However, for simple implicitly defined tuples it would be more common to
use positional arguments anyway, so in many cases it can be the preferred
alternative. For example:

.. code-block:: python

   bk = Booking(date=datetime.date(2018,12,31), location=("Sydney","Australia"))

   assert bk.location[0] == "Sydney"

.. note::

   As mentioned previously, using positional arguments is something that should
   be used sparingly as it can lead to brittle code that is more difficult to
   refactor. It should mainly be used for cases where the ordering of the fields
   in the tuple is unlikely to change when the ASP program is refactored.

Debugging Auxiliary Predicates
------------------------------

When integrating an ASP program into a Python based application there will be a
set of predicates that are important for inputting a problem instance and
outputting a solution. Clorm is intended to provide a clean way of interacting
with these predicates.

However, there will typically be other auxiliary predicates that are used as
part of the problem formalisation. While they may not be important from the
Python application point of view they do become important during the process of
developing and debugging the ASP program. During this process it can be
cumbersome to build a detailed Clorm predicate definition for each one of these,
especially when all you need to do is print the predicate instances to the
screen, possibly sorted in some order.

Clorm solves this issue by providing a factory helper function
``simple_predicate()`` that returns a ``Predicate`` sub-class that will map to
any predicate instance with that name and arity.

For example this function could be used for the above booking example if we
wanted to extract the ``booking/2`` facts from the model but didn't care about
mapping the data types for the individual parameters. For example to match the
ASP fact:

.. code-block:: none

   booking("2018-12-31", ("Sydney", "Australia)).

instead of the explicit ``Booking`` definition above we could use the
``simple_predicate`` function:

.. code-block:: python

   from clorm.clingo import Symbol, Function, String
   from clorm import _simple_predicate

   Booking_alt = simple_predicate("booking",2)
   bk_alt = Booking_alt(String("2018-12-31"), Function("",[String("Sydney"),String("Australia")]))

Note, in this case in order to create these objects within Python it is
necessary to use the Clingo functions to explictly create ``clingo.Symbol``
objects.


Dealing with Raw Clingo Symbols
-------------------------------

As well as supporting simple and complex terms it is sometimes useful to deal
with the raw ``clingo.Symbol`` objects created through the underlying Clingo
Python API.

.. _raw-symbol-label:

Raw Clingo Symbols
^^^^^^^^^^^^^^^^^^

The Clingo API uses ``clingo.Symbol`` objects for dealing with facts; and there
are a number of functions for creating the appropriate type of symbol objects
(i.e., ``clingo.Function()``, ``clingo.Number()``, ``clingo.String()``).

In essence the Clorm ``Predicate`` and ``ComplexTerm`` classes simply provide a
more convenient and intuitive way of constructing and dealing with these
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

Clorm ``Predicate`` objects can also be constructed from the raw symbol
objects. So assuming the above python code.

.. code-block:: python

   address_copy = Address(raw=raw_address)

.. note::

   Not every raw symbol will *unify* with a given ``Predicate`` or
   ``ComplexTerm`` class. If the raw constructor fails to unify a symbol with a
   predicate definition then a ``ValueError`` exception will be raised.

Integrating Clingo Symbols into a Predicate Definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are some cases when it might be convenient to combine the simplicity and
the structure of the Clorm predicate interface with the flexibility of the
underlying Clingo symbol API. For this case it is possible to use the
``RawField`` base class itself.

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

In this example instances of the ``true/2`` predicate can have two distinctly
different signatures for the first term (i.e., ``light/1`` and
``robotlocation/2``). While the definition of the fluent is important at the ASP
level, however, at the Python level we may not be interested in the structure of
the fluent, only whether it is true or not. In such a case we can simply treat
the fluents themselves as raw Clingo symbol objects.

.. code-block:: python

   from clorm import *

   class True(Predicate):
      fluent = RawField
      time = IntegerField

Accessing the value of the ``fluent`` simply returns the raw Clingo symbol. Also
the ``RawField`` has the useful property that it will unify with any
``Clingo.Symbol`` object and therefore can be used to capture both the
``light/1`` and ``robotlocation/2`` complex terms.


Combining Field Definitions
---------------------------

The above example is useful for cases where you don't care about accessing the
details of individual fluents and therefore it makes sense to simply treat them
as a ``RawField`` complex term. However, the question naturally arises what to
do if you do want more fine-grained access to these fluents.

There are a few possible solutions to this problem, but one obvious answer is to
use a field that combines together multiple fields. Such a combined field could
be specified manually by explicitly defining a RawField sub-class. However, to
simplify this process the ``combine_fields()`` factory function has been
provided that will return such a combined RawField sub-class.

With reference to the ASP code of the previous example we could add the
following Python integration:

.. code-block:: python

   from clorm import Predicate, ComplexTerm, IntegerField, ConstantField combine_fields

   class Light(ComplexTerm):
      status=ConstantField

   class RobotLocation(ComplexTerm):
      robot=ConstantField
      location=ConstantField
      class Meta: name = "robotlocation"

   class True(Predicate):
      fluent = combine_fields("FluentField",[Light,RobotLocation])
      time = IntegerField


The ``combine_fields()`` function takes two arguments; the first is an optional
field name argument and the second is a list of the sub-fields to combine. Note:
when trying to unify a value with a combined field the raw symbol values will be
unified with the underlying field definitions in the order that they are listed
in the call to ``combine_fields()``. This means that care needs to be taken if
the raw symbol values could unify with multiple sub-fields; it will only unify
with the first successful sub-field. In the above example this is not a problem
as the two fluent field definitions do not overlap.

.. code-block:: python

    from clorm import ph1_

    ctrl = Control(unifier=[True])
    ctrl.ground([("base",[])])

    solution=None
    with ctrl.solve(yield_=True) as sh:
        for m in sh:
            solution=m.facts(atoms=True)
            break
    if not solution:
        raise ValueError("No solution found")

    fquery = solution.select(True).where(True.time == ph1_)
    for h in fquery.get(0):
            f = h.fluent
            if isinstance(f,Light):
                print("\tLight is: {}".format(f.status))
            elif isinstance(f,RobotLocation):
                print("\tRobot {} is at {}".format(f.robot,f.location))


It should be noted that there is one disadvantage of using a combined field
instead of ``RawField``. Clingo defines a total ordering over all Symbol
objects. This means that it is always possible to specify an ``.order_by()``
criteria if the term definition is for a ``RawField``. On the other hand Python
does not define an ordering over all objects. For example trying to sort a list
containing integers and strings will fail and throw an exception. In such cases
where there is no Python ordering between converted values then a query
specifying an ``.order_by()`` criteria will also throw an exception.


Dealing with Nested Lists
-------------------------

ASP does not have an explicit representation for lists. However a common
convention for encoding lists is using a nesting of head-tail pairs; where the
head of the pair is the element of the list and the tail is the remainder of the
list, being another pair or an empty tuple to indicate the end of the list.

For example encoding a list of "nodes" [1,2,c] for some predicate ``p``, might
take the form:

.. code-block:: prolog

   p(nodes,(1,(2,(c,())))).

While, such an encoding can be problematic and can lead to a grounding blowout,
nevertheless when used with care can be very useful.

Unfortunately, getting facts containing these sorts of nested lists into and out
of Clingo can be very cumbersome. To help support this type of encoding Clorm
provides the ``define_nested_list_field()`` function. This factory function
takes an element field class, as well as an optional new class name, and returns
a newly created ``RawField`` sub-class that can be used to convert to and from a
list of elements of that field class.

 .. code-block:: python

   from clorm import Predicate, ConstantField, SimpleField, \
      define_nested_list_field

   SNLField=define_nested_list("SNLField",SimpleField)

   class P(Predicate):
      param=ConstantField
      alist=SNLField

   p = P("nodes",[1,2,"c"])
   assert str(p) == "p(nodes,(1,(2,(c,()))))"

   p = P("nodes",[1,2,"c","A string"])
   assert str(p) == '''p(nodes,(1,(2,(c,("A string",())))))'''


