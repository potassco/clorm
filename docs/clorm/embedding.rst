Embedding Python into ASP
=========================

As well as providing an API for calling the Clingo solver from Python, Clingo
also supports embedding Python function calls into an ASP program. Clorm
supports calling Python from an ASP program in two ways: it can generate
templates to perform type conversion between Python and ASP data, and it
provides a library of re-usable components.

Specifying Type Cast Signatures
-------------------------------

When calling (external) Python functions from within an ASP program the Python
function is passed inputs encoded as objects of type ``Clingo.Symbol``. The
clingo system then expects a return value of either a single ``Clingo.Symbol``
object or a list of ``Clingo.Symbol`` objects. It is the responsibility of the
programmer to perform any necessary data type conversions.

For convenience clingo does some provide some exceptions to this basic
procedure. These exceptions are to do with the output values where clingo is
able to make some assumptions. In particular:

* Python integer values will be automatically converted to clingo.Symbol object
  using the cling.Number() function. Similarly Python string values will be
  converted using the cling.String() function.

* Python tuples will automatically be converted using the clingo.Function()
  function, with an empty string as the first parameter which is how clingo
  innternally represents tuples.

While the automatic data conversion behaviour of the clingo API can be
convenient it is however a somewhat ad-hoc approach. In the first place there is
no automatic conversions for the inputs to the external function. Secondly it cannot deal with arbitrary outputs. For example, it is not possible to specify that a string should be interpreted as a constant object rather than a string object. Also complex terms other than a tuples cannot be automatically handled.

To address these problems Clorm tries to provide a more principled approach that
allows for a *type cast signature* that defines how to automatically convert
between the expected input and output types.

In order to explain Clorm's type casting features, consider a Python
``date_range`` function that is given two dates and returns an enumerated list
of dates within this range. This can be called from Clingo by prefixing the
function with the ``@`` symbol:

.. code-block:: none

   date(@date_range("20190101", 20190105")).

The corresponding Python object needs to take the two input ``Clingo.String``
symbols turn them into dates, compute the dates in the range, and return the
enumerated list of outputs converted back into ``Clingo.String`` symbols.

.. code-block:: python

   from clingo import String
   from datetime import datetime, timedelta

   def date_range(start, end):
       pystart = datetime.strptime(start.string, "%Y%m%d").date()
       pyend = datetime.strptime(end.string, "%Y%m%d").date()

       inc = timedelta(days=1)
       tmp = []
       while pystart < pyend:
           tmp.append(pystart.strftime("%Y%m%d"))
	   pystart += inc
       return list(enumerate(tmp))

When the ASP program is grounded it will produce the list of date objects:

.. code-block:: none

   date((0,"20190101")). date((1,"20190102")).
   date((2,"20190103")). date((3,"20190104")).

Here the string objects that encode the two dates are first converted into
actual Python date objects. When the appropriate date is calculated it is
translated back into a string where it is enumerated into list of pairs with the
first element of each pair being the enumeration index and the second element
being the string. Note: that this takes advantage of the automatic clingo API
type conversions.

Clorm provides a way to simplify this data translation through the use of a
decorator that attaches a *type cast signature* to the function. Firstly the
conversion to and from date objects can be removed from the function and instead
declared as part of a ``DateField``, thus simplifying the function but also
making the code more re-usable.

.. code-block:: python

   from clorm import StringField
   from datetime import datetime, timedelta

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y%m%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

The ``DateField`` sub-classes a ``clorm.StringField`` and provides the
conversion between string objects and dates.

.. code-block:: python

   @make_function_asp_callable
   def date_range(start : DateField, end : DateField) -> [(IntegerField, DateField)]:
       inc = timedelta(days=1)
       tmp = []
       while start < end:
           tmp.append(start)
	   start += inc
       return list(enumerate(tmp))

This decorator supports the specification of the type cast signature as part of
the function's **annotations** (a Python 3 feature) to provide a neater
specification. Note, the signature could equally be passed as decorator function
arguments:

.. code-block:: python

   @make_function_asp_callable(DateField, DateField, [(IntegerField, DateField)])
   def date_range:
       ...

The important point is that the type cast signature provides a mechanism to
specify arbitrary data conversions both for the input and output data; including
conversions generated from very complex terms specified as Clorm ``ComplexTerm``
subclasses. Consequently, the programmer does not have to waste time performing type conversions and even existing functions could be decorated to be used as callable ASP functions.

Another point to note is that the Clorm specification is also able to use the
simplified tuple syntax from the Clingo API to specify the enumerated pairs.  In
fact this code can be viewed as a short-hand for an explicit declaration of a
ComplexTerm tuple and internally Clorm does generate a signature equivalent to
the following:

.. code-block:: python

   class EnumDate(ComplexTerm):
       idx = IntegerField()
       dt = DateField()
       class Meta: is_tuple=True

   @make_function_asp_callable
   def date_range(start : DateField, end : DateField) -> [EnumDate.Field]:
      ...

There are two decorator functions are Clorm provides:

* ``make_function_asp_callable``: Wraps a normal function. Every function
  parameter is converted to and from the clingo equivalent.
* ``make_method_asp_callable``: Wraps a member function. The first paramater is
  the object's ``self`` parameter so is passed through and only the remaining
  parameters are converted to their clingo equivalents.

In summary, the Clorm type cast signature has two distinct advantages over the
built in clingo API for handling external functions. Firstly, it provides a
principled approach for specifying arbitrarily complex type conversions, unlike
the limited ad-hoc approach of the built-in clingo API. Secondly, by making this
type conversion specification explicit it is clear what conversions will be
performed and therefore makes for clearer and more re-usable code.

Re-usable Components
--------------------

Building on the easy with which predicates and complex terms can be defined
using Clorm, a second goal of this project is to maintain a library of re-usable
ASP components.

While it remains to be seen whether or not there is a genuine need or desire for
a library of re-usable ASP components, we would argue that using such components
can make ASP programs easier to use and easier to debug. For example, a library
containing enumerated dates allows the ASP code to deal with the index (since it
establishes the ordering), but also make the inputs and outputs of the program
more readable because it explicitly includes the date represented in a human
readable form.

For details of the available libraries see :ref:`liborm`.
