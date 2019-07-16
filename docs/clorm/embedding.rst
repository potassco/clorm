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
subclasses. Consequently, the programmer does not have to waste time performing
type conversions and even existing functions could be decorated to be used as
callable ASP functions.

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

Specifying a Grounding Context
------------------------------

From Clingo 5.4 onwards, the Clingo grounding function allows a `context`
parameter to be specified. This parameter defines a context object for the
methods that are called by ASP using the @-syntax.

While this context feature can be used in a number of different ways, one way is
simply as a convenient namespace for encapsulating the external Python functions
that are callable from within an ASP program. Clorm provides support for this
use-case through the use of context builders.

``ContextBuilder`` allows arbitrary functions to be captured within a context
and assigned a data conversion signature (where the data conversion signature is
specified in the same way as the ``make_function_asp_callable`` and
``make_method_asp_callable`` functions). It also allows the function to be given
a different name when called from within the context.

Also like ``make_function_asp_callable`` and ``make_method_asp_callable``, the
context builder's ``register`` and ``register_name`` member functions can be
called as decorators or as normal functions. However, unlike the standalone
functions, a useful feature of the ``ContextBuilder`` member functions is that
when called as decorators they do not decorate the original functions but
instead return the original function and only decorate the function when called
from within the context.

Consider the decorated ``date_range`` function defined earlier. One issue with
this function is that it can only be called from within an ASP program (unless
you use clingo.Symbol inputs and outputs). However, a function that generates an
enumerated date range is fairly useful in itself so it might be desireable to be
called from other Python functions.

The ``ContextBuilder`` can be used to solve this problem.

.. code-block:: python

   from clorm import ContextBuilder

   cb=ContextBuilder()

   # decorator that registers the function with the context
   @cb.register(DateField, DateField, [(IntegerField, DateField)])
   def date_range(start, end):
       inc = timedelta(days=1)
       tmp = []
       while start < end:
           tmp.append(start)
	   start += inc
       return list(enumerate(tmp))

   # Use the function as normal to calculate a date range
   sd=datetime.date(2010,1,5)
   ed=datetime.date(2010,1,8)
   dr=date_range(sd,ed)

   ctx=cb.make_context()

   # Use the decorated version from within the context
   cl_dr = ctx.date_range(clingo.String("20100105"),clingo.String("20100108"))

The above example show how the original ``date_range`` function is untouched but
instead the context version is wrapped using the data conversion signature. The
created context can then be passed as an argument during the grounding phase.

.. code-block:: python

   import clingo

   ctrl=clingo.Control()

   # Define an ASP program and import it into the control object
   prgstr="""date(@date_range("20101010", "20101013")."""

   with ctrl.builder() as b:
      clingo.parse_program(prgstr, lambda s: b.add(s))

   # Ground using the context defined earlier
   ctrl.ground([("base",[])],context=ctx)

   # Solve
   ctrl.solve()

The program defined in the string uses the ``date_range`` function defined by
the earlier context and when solved will produce the expected answer set:

.. code-block:: prolog

   date("2001010"). date("2001011"). date("2001012").

Of course multiple functions can be registered with a ``ContextBuilder`` and it
can also be used as a from of code re-use to define multiple versions of a
function with different signatures.

.. code-block:: python

   def add(a,b): a+b

   # Register two versions using the same function - one to add numbers and one
   # to concat strings. Note: first argument is the new function name, last
   # argument is the function; the middle arguments define the signature.
   cb.register_name("addi", IntegerField, IntegerField, IntegerField, add)
   cb.register_name("adds", StringField, StringField, StringField, add)

   ctx=cb.make_context()

   n1=clingo.Number(1); n2=clingo.Number(2); n3=clingo.Number(3)
   s1=clingo.String("ab"); s2=clingo.String("cd"); s3=clingo.String("abcd")

   assert ctx.addi(n1,n2) == n3
   assert ctx.adds(s1,s2) == s3

Re-usable Components
--------------------

Building on the easy with which predicates and complex terms can be defined
using Clorm, a possible goal of this project is to maintain a library of
re-usable ASP components.

While it remains to be seen whether or not there is a genuine need or desire for
a library of re-usable ASP components, using such components could make ASP
programs easier to use and easier to debug. For example, a library containing
enumerated dates allows the ASP code to deal with the index (since it
establishes the ordering), but also make the inputs and outputs of the program
more readable because it explicitly includes the date represented in a human
readable form.

For details of the available libraries see :ref:`liborm`.
