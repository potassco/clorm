Embedding Python into ASP
=========================

As well as providing an API for calling the Clingo solver from Python, Clingo
also supports embedding Python function calls within an ASP program. Clorm
builds on these Clingo features by providing an extended interface for calling
Python from an ASP program.

Specifying Type Cast Signatures
-------------------------------

When calling (external) Python functions from within an ASP program the Python
function is passed inputs encoded as objects of type ``Clingo.Symbol``. The
Clingo system then expects a return value of either a single ``Clingo.Symbol``
object or a list of ``Clingo.Symbol`` objects. It is the responsibility of the
programmer to perform any necessary data type conversions.

For convenience Clingo does provide *some* exceptions to this basic
procedure. These exceptions are to do with the output values where Clingo is
able to make some assumptions. In particular:

* Python integer values will be automatically converted to a ``clingo.Symbol``
  object using the ``clingo.Number()`` function. Similarly Python string values
  will be converted using the ``clingo.String()`` function.

* Python tuples will automatically be converted using the ``clingo.Function()``
  function, with an empty string as the name parameter, which is how Clingo
  internally represents tuples.

While this automatic data conversion behaviour of the Clingo API can be
convenient it is however a somewhat ad-hoc approach. In the first place while
there is some automatic conversion of the outputs of the Python function,
however, there is no automatic conversions for the inputs to the Python
function. Secondly it cannot deal with arbitrary outputs. For example, it is not
possible to specify that a Python string should be interpreted as a constant
object rather than a string object. Also complex terms other than a tuples
cannot be handled automatically.

To address these problems Clorm provides a more principled approach that allows
for the specification of a *type cast signature* that defines how to
automatically convert between the expected input and output types.

We explain Clorm's type casting features by way of a simple example. In
particular, consider a Python ``date_range`` function that is given two dates
(encoded in **YYYY-MM-DD** string format) and returns an enumerated list of
dates within this range. This can be called from Clingo by prefixing the
function with the ``@`` symbol:

.. code-block:: none

   date(@date_range("2019-01-01", 2019-01-05")).

The corresponding Python object needs to take the two input ``clingo.String``
symbols turn them into dates, compute the dates in the range, and return the
enumerated list of outputs converted back into ``clingo.String`` symbols.

.. code-block:: python

   from clingo import String
   from datetime import datetime, timedelta

   def date_range(start, end):
       pystart = datetime.strptime(start.string, "%Y-%m-%d").date()
       pyend = datetime.strptime(end.string, "%Y-%m-%d").date()

       inc = timedelta(days=1)
       tmp = []
       while pystart < pyend:
           tmp.append(pystart.strftime("%Y%m%d"))
	   pystart += inc
       return list(enumerate(tmp))

This function will be called by Clingo during the ASP program grounding
process that will generate the list of ground facts:

.. code-block:: none

   date((0,"2019-01-01")). date((1,"2019-01-02")).
   date((2,"2019-01-03")). date((3,"2019-01-04")).

Here the string objects that encode the two dates are first converted into
Python date objects. Then when the appropriate dates are calculated they are
translated back into strings and enumerated into list of pairs with the first
element of each pair being the enumeration index and the second element being
the date encoded string. Note: that the above Python code does takes advantage
of the automatic clingo API type conversions.

Clorm provides a way to simplify this data translation through the use of a
decorator that attaches a *type cast signature* to the function. Firstly the
conversion to and from date objects can be removed from the function and instead
declared as part of a ``DateField``, thus simplifying the function but also
making the code more re-usable.

.. code-block:: python

   from clorm import StringField
   from datetime import datetime, timedelta

   class DateField(StringField):
       pytocl = lambda dt: dt.strftime("%Y-%m-%d")
       cltopy = lambda s: datetime.datetime.strptime(s,"%Y-%m-%d").date()

The ``DateField`` sub-classes a ``StringField`` and provides the conversion
between string objects and dates.

.. code-block:: python

   @make_function_asp_callable(DateField, DateField, [(IntegerField, DateField)])
   def date_range(start, end):
       inc = timedelta(days=1)
       tmp = []
       while start < end:
           tmp.append(start)
	   start += inc
       return list(enumerate(tmp))

The important point is that the type cast signature provides a mechanism to specify arbitrary
data conversions both for the input and output data; including conversions generated from very
complex terms specified as Clorm ``Predicate`` sub-classes. Consequently, the programmer does
not have to explicitly write the type conversion code and even existing functions can be
decorated to be used as callable ASP functions.

Another point to note is that the Clorm specification is also able to use the simplified tuple
syntax from the Clingo API to specify the enumerated pairs.  In fact this code can be viewed as
a short-hand for an explicit declaration of a ``ComplexTerm`` tuple and internally Clorm
generates a signature equivalent to the following:

.. code-block:: python

   from clorm import Predicate, field

   class EnumDate(Predicate, name=""):
       idx: int
       dt: datetime.date = field(DateField)

   @make_function_asp_callable
   def date_range(start : DateField, end : DateField) -> [EnumDate.Field]:
      ...

There are two decorator functions that Clorm provides:

* ``make_function_asp_callable``: Wraps a normal function. Every function parameter is
  converted to and from the clingo equivalent.
* ``make_method_asp_callable``: Wraps a member function. The first paramater is the object's
  ``self`` parameter so is passed through and only the remaining parameters are converted to
  their clingo equivalents.

In summary, the Clorm type cast signature provides a principled approach for specifying
arbitrarily complex type conversions. Furthermore, by making this type conversion specification
explicit it is clear what conversions will be performed and therefore makes for clearer and
more re-usable code.

Specifying a Grounding Context
------------------------------

From Clingo 5.4 onwards, the Clingo grounding function allows a ``context``
parameter to be specified. This parameter defines a context object for the
methods that are called by ASP using the @-syntax.

While this context feature can be used in a number of different ways, one way is
simply as a convenient namespace for encapsulating the external Python functions
that are callable from within an ASP program. Clorm provides support for this
use-case through the use of a *context builder*.

``ContextBuilder`` allows arbitrary functions to be captured within a context
and assigned a data conversion signature (where the data conversion signature is
specified in the same way as the ``make_function_asp_callable`` and
``make_method_asp_callable`` functions). It also allows the function to be given
a different name when called from within the context.

Also like ``make_function_asp_callable`` and ``make_method_asp_callable``, the
context builder's ``register`` and ``register_name`` member functions can be
called as decorators or as normal functions. However, unlike the standalone
functions, a useful feature of the ``ContextBuilder`` member functions is that
when called as a decorator they do not decorate the original functions but
instead return the original function and only decorate the function when called
from within the context.

Consider the decorated ``date_range`` function defined earlier. One issue with
this function is that it can only be called from within an ASP program (unless
you use ``clingo.Symbol`` inputs and outputs). However, a function that
generates an enumerated date range is fairly useful in and of itself so it might
be desireable to be called from other Python functions.

The ``ContextBuilder`` can be used to solve this problem.

.. code-block:: python

   from clorm import ContextBuilder

   cb=ContextBuilder()

   # decorator that registers the function with the context builder
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
   cl_dr = ctx.date_range(clingo.String("2010-01-05"),clingo.String("2010-01-08"))

The above example shows how the original ``date_range`` function is untouched
but instead the context version is wrapped using the data conversion
signature. The created context can then be passed as an argument during the
grounding phase.

.. code-block:: python

   import clingo

   ctrl=clingo.Control()

   # Define an ASP program and import it into the control object
   prgstr="""date(@date_range("2010-10-10", "2010-10-13")."""

   with ctrl.builder() as b:
      clingo.parse_program(prgstr, lambda s: b.add(s))

   # Ground using the context defined earlier
   ctrl.ground([("base",[])],context=ctx)

   # Solve
   ctrl.solve()

The program defined in the string uses the ``date_range`` function defined by
the earlier context and when solved will produce the expected answer set:

.. code-block:: prolog

   date((0,"2010-10-10")). date((1,"2010-10-11")). date((2,"2010-10-12")).

Of course multiple functions can be registered with a ``ContextBuilder`` and it
can also be used as a form of code re-use to define multiple versions of a
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

