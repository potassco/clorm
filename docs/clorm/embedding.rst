Embedding Python into ASP
=========================

As well as providing an API for calling the Clingo solver from Python, Clingo
also supports embedding Python function calls into an ASP program. ClORM
supports calling Python from an ASP program in two ways: it can generate
templates to perform type conversion between Python and ASP data, and it
provides a library of re-usable components.

Python Function Signatures
--------------------------

When calling Python functions from an ASP program the Python function is passed
``Clingo.Symbol`` objects and is expected to return either a single
``Clingo.Symbol`` object or a list of ``Clingo.Symbol`` objects. It is the
responsibility of the programmer to perform these data type conversions.

For example, consider a Python function ``date_range`` that is given two dates
and returns a list of the dates within this range. This can be called from
Clingo by prefixing the function with the ``@`` symbol:

.. code-block:: none

   date(@date_range("20190101", 20190201")).

The corresponding Python object needs to take the two input ``Clingo.String``
symbols turn them into dates, compute the dates in the range, and return the
list of outputs converted back into ``Clingo.String`` symbols.

.. code-block:: python

   from clingo import String
   from datetime import datetime, timedelta

   def date_range(start, end):
       pystart = datetime.strptime(start.string, "%Y%m%d").date()
       pyend = datetime.strptime(end.string, "%Y%m%d").date()

       inc = timedelta(days=1)
       tmp = []
       while pystart < pyend:
           tmp.append(String(pystart.strftime("%Y%m%d")))
	   pystart += inc
       return tmp

ClORM provides a way to simplify this data translation by declaring a function
``Signature`` and then using the signature to generate wrapper Python code that
performs the required conversions. The code above can be replaced with:

.. code-block:: python

   from clorm import StringField
   from datetime import datetime, timedelta

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y%m%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

   drsig = Signature(DateField, DateField, [DateField])

   @drsig.wrap_function
   def date_range(start_end):
       inc = timedelta(days=1)
       tmp = []
       while start < end:
           tmp.append(start)
	   start += inc
       return tmp

This example uses the power of ClORM to sub-class the ``StringField`` so that
the date translation to a string is captured by a ``DateField``. The
``Signature`` object then captures the function signature which accepts two
dates and returns a list of dates. A Python *decorator* is provided to generate
the Python data conversion code.

The ``Signature`` object provides two types of wrappers:

* ``wrap_function``: Wraps a normal function. Every function parameter is
  converted to and from the clingo equivalent.
* ``wrap_method``: Wraps a member function. The first paramater is the object's
  ``self`` parameter so is passed through and only the remaining parameters are
  converted to their clingo equivalents.

While the above code is arguably easier to read than the raw version it does
require more lines of code; although in this case it could be argued that the
resulting simplified loop within the function can more easily be simplified by
turning in into a list comprehension statement.  In any case, as the objects
being dealt with become more complicated, the ClORM approach becomes more
appealing.

For example, if instead of a list of date encoded string, we want to return a
range as a list of enumerated dates (i.e., consisting of an integer-date pair
starting at 0) the corresponding ClORM version adds very little overhead.

.. code-block:: python

   from clorm import StringField, IntegerField, ComplexTerm
   from datetime import datetime, timedelta

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y%m%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

   class EnumDate(ComplexTerm):
       idx = IntegerField()
       date = DateField()

   drsig = Signature(DateField, DateField, [EnumDate.Field])

   def py_date_range(start_end):
       inc = timedelta(days=1)
       tmp = []
       while start < end:
           tmp.append(start)
	   start += inc
       return list(enumerate(tmp))

   date_range = drsig.wrap_function(py_date_range)

The above example shows that even with relatively complex data structures the
corresponding Python code remains compact and readable. It also highlights how
``Signature.wrap_function`` and ``Signature.wrap_method`` functions don't need
to be called as a decorator but can be called as a normal function. This makes
it extremely easy to maintain two versions of the function; one to be called
from Python code and another to be called from within Clingo.

Re-usable Components
--------------------

Building on the easy with which predicates and complex terms can be defined
using ClORM, a second goal of this project is to maintain a library of re-usable
ASP components.

While it remains to be seen whether or not there is a genuine need or desire for
a library of re-usable ASP components, we would argue that using such components
can make ASP programs easier to use and easier to debug. For example, a library
containing enumerated dates allows the ASP code to deal with the index (since it
establishes the ordering), but also make the inputs and outputs of the program
more readable because it explicitly includes the date represented in a human
readable form.

For details of the available libraries see :ref:`liborm`.
