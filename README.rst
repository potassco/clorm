Clingo ORM (Clorm)
==================

Clorm is a Python library that provides an Object Relational Mapping (ORM)
interface to the Clingo Answer Set Programming (ASP) solver. The goal of this
library is to make it easier to integrate Clingo within a Python application. It
is designed to supplement and not replace the existing Clingo API.

When integrating an ASP program into an application you typically want to model
the domain as a statically written ASP program, but then to generate problem
instances and process the results dynamically. Clorm makes this integration
cleaner, both in terms of code readability but also by making it easier to
refactor the python code as the ASP program evolves.

The documentation is available online `here <https://clorm.readthedocs.io>`_.

Note: Clorm only works with Python 3.x.

Installation
------------

The easiest way to install Clorm is with Anaconda. Assuming you have already
installed some variant of Anaconda, first you need to install Clingo:

.. code-block:: bash

    $ conda install -c potassco clingo

Then install Clorm:

.. code-block:: bash

    $ conda install -c daveraja clorm

Quick Start
-----------

The following example highlights the basic features of Clorm. The ASP and Python
parts of this example are located in the ``examples`` sub-directory in the git
repository. The ASP program is ``quickstart.lp`` and the Python program is
``quickstart.py``.

Imagine you are running a courier company and you have drivers and items that
need to be delivered on a daily basis. An item is delivered during one of four
time slots, and you want to assign a driver to deliver each item, while also
ensuring that all items are assigned and drivers aren't double-booked for a time
slot.

You also want to apply some optimsation criteria. Firstly, you want to minimise
the number of drivers that you use (for example, because bringing a driver on
for a day has some fixed cost). Secondly, you want to deliver items as early in
the day as possible.

The above crieria can be encoded with the following simple ASP program:

.. code-block:: prolog

   time(1..4).

   1 { assignment(I, D, T) : driver(D), time(T) } 1 :- item(I).
   :- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

   working_driver(D) :- assignment(_,D,_).

   #minimize { 1@2,D : working_driver(D) }.
   #minimize { T@1,D : assignment(_,D,T) }.


This ASP program encodes the problem domain and can be used to solve the problem
for arbitrary instances (i.e., arbitrary combinations of drivers and items).

We now use a Python program to dynamically generate the problem instance and to
process the generated solutions. Each solution will be an assignment of drivers
to items for a time slot.

First the relevant libraries need to be imported.


.. code-block:: python

   from clorm import Predicate, ConstantField, IntegerField, FactBaseBuilder, ph1_
   from clorm.clingo import Control

Note: Importing from ``clorm.clingo`` instead of ``clingo``.

   While it is possible to use Clorm with the raw clingo library, a wrapper
   library is provided to make the integration seemless. This wrapper (should)
   behave identically to the original module, except that it extends the
   functionality to offer integration with Clorm objects. It is also possible to
   `monkey patch <https://en.wikipedia.org/wiki/Monkey_patch>`_ Clingo if this
   is your preferred approach (see the `documentation
   <https://clorm.readthedocs.io/en/latest/>`_).

The next step is to define a data model that maps the Clingo predicates to
Python classes. Clorm introduces two basic concepts for defining the data model:
``Predicate`` and ``FactBase``. ``Predicate`` maps the ASP predicates to Python
classes and must be sub-classed, while ``FactBase`` provides a container for
storing facts.

A helper class ``FactBaseBuilder`` is provided for alternative ways of creating
FactBases (e.g., building a fact base from raw Clingo ``Symbol`` objects).


.. code-block:: python

   fbb = FactBaseBuilder()

   @fbb.register
   class Driver(Predicate):
       name=ConstantField()

   @fbb.register
   class Item(Predicate):
       name=ConstantField()

   @fbb.register
   class Assignment(Predicate):
       item=ConstantField()
       driver=ConstantField(index=True)
       time=IntegerField()

The above code defines three classes to match the ASP program's input and output
predicates.

``Driver`` maps to the ``driver/1`` predicate, ``Item`` maps to ``item/1``, and
``Assignment`` maps to ``assignment/3``. A predicate may contain zero or more
*fields* (using database terminology). Fields can be thought of as *term
definitions* as they define how a logical *term* is converted to, and from, a
Python object. The number of fields must match the predicate arity and the order
in which they are declared must also match the position of each term in the ASP
predicate.

The ``FactBaseBulider`` provides a decorator that registers the predicate class
with the builder. Once a predicate class is registered the builder will use this
class to try and unify against Clingo symbols. It also ensures that the fact
base is built with the appropriate indexes as specified by ``index=True`` for
the field. In the example, the ``driver`` field is indexed allowing for faster
queries when searching for specific drivers. As with a traditional database
indexing improves query performance but should be used sparingly.

Having defined the data model we now show how to dynamically add a problem
instance, solve the resulting ASP program, and print the solution.

First we create the Clingo ``Control`` object and load the ASP program.

.. code-block:: python

    ctrl = Control()
    ctrl.load("quickstart.lp")


Next we generate a problem instance by generating a lists of ``Driver`` and
``Item`` objects. These items are added to an input fact base.

.. code-block:: python

    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = FactBase(drivers + items)

The ``Driver`` and ``Item`` constructors use named parameters that match the
declared field names. Note: while you can use positional arguments to initialise
instances, doing so will potentially make the code harder to refactor. So in
general you should avoid using positional arguments except for a few cases (eg.,
simple pairs where the order is unlikely to change).

These facts can now be added to the control object and the combined ASP program
grounded.

.. code-block:: python

    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

Next we run the solver to generate solutions. The solver is run with a callback
function that is called each time a solution (technically an *answer set* or
simply a *model*) is found.

.. code-block:: python

    solution=None
    def on_model(model):
        nonlocal solution
        solution = model.facts(fbb, atoms=True)

    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")

The ``on_model()`` callback is triggered for every new model. Because of the ASP
optimisation statements this callback can potentially be triggered multiple times
before an optimal model is found. Also, note that if the problem is
unsatisfiable then it will never be called and you should always check for this
case.

The line ``solution = model.facts(fbb, atoms=True)`` extracts only instances of
the predicates that were registered with the ``FactBaseBuilder``. In this case
it ignores the ``working_driver/1`` instances. These facts are stored and
returned in a fact base.

The final part of our Python program involves querying the solution to print out
the relevant parts. To do this we call the ``FactBase.select()`` member function
that returns a suitable ``Select`` object.

.. code-block:: python

    query=solution.select(Assignment).where(Assignment.driver == ph1_).order_by(Assignment.time)

A Clorm query can be viewed as a simplified version of a traditional database
query, and the function call syntax will be familiar to users of Python ORM's
such as SQLAlchemy or Peewee.

Here we want to find ``Assignment`` instances that match the ``driver`` field to
a special placeholder object ``ph1_`` and to return the results sorted by the
assignment time. The value of ``ph1_`` will be provided when the query is
actually executed; which allows the query to be re-run multiple times with
different values.

In particular, we now iterate over the list of drivers and execute the query for
each driver and print the result.

.. code-block:: python

    for d in drivers:
        assignments = query.get(d.name)
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))

Calling ``query.get(d.name)`` executes the query for the given driver. Because
``d.name`` is the first parameter it matches against the placeholder ``ph1_`` in
the query definition. Clorm has four predefined placeholders but more can be
created using the ``ph_`` function.

Running this example produces the following results:

.. code-block:: bash

    $ cd examples
    $ python quickstart.py
    Driver dave must deliver:
             Item item5 at time 1
             Item item4 at time 2
    Driver morri must deliver:
             Item item1 at time 1
             Item item2 at time 2
             Item item3 at time 3
    Driver michael is not working today

The above example shows some of the main features of Clorm and how to match the
Python data model to the defined ASP predicates. For more details about how to
use Clorm see the `documentation <https://clorm.readthedocs.io/en/latest/>`_.

Other Clorm Features
--------------------

Beyond the basic features outlined above there are many other features of the
Clorm library. These include:

* You can define new sub-classes of ``RawField`` for custom data
  conversions. For example, you can define a ``DateField`` that represents dates
  in clingo in YYYY-MM-DD format and then use it in a predicate definition.

.. code-block:: python

    from clorm import StringField          # StringField is a sub-class of RawField
    from datetime import datetime

    class DateField(StringField):
        pytocl = lambda dt: dt.strftime("%Y%m%d")
        cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

    class DeliveryDate(Predicate):
        item=ConstantField()
        date=DateField()

* Clorm supports predicate definitions with complex-terms; using a
  ``ComplexTerm`` class (which is in fact an alias for Predicate) and Python
  tuples. Every defined complex term has an associated ``RawField`` sub-class
  that can be accessed as a ``Field`` property of the complex term class.

.. code-block:: python

    from clorm import ComplexTerm

    class Event(ComplexTerm):
        date=DateField
	name=StringField

    class Log(Predicate):
        event=Event.Field()
	level=IntegerField()

.. code-block:: prolog

    log(event("20190405", "goto shops"), 0).

* Field definitions can be specified as part of a function signature to perform
  automatic type conversion for writing Python functions that can be called from
  an ASP program using the @-syntax.

  Here function ``add`` is decorated with an automatic data conversion signature
  that accepts two input integers and expects an output integer.

.. code-block:: python

    @make_function_asp_callable(IntegerField, IntegerField, IntegerField)
    def add(a,b): a+b

.. code-block:: prolog

    f(@add(5,6)).    % grounds to f(11).

* Function signatures follow the functionality of the clingo API (so you can
  specify tuples and provide functions that return list of items).

  However, the behaviour of the clingo API is ad-hoc when it comes to automatic
  data conversion. That is, it will automatically convert numbers and strings,
  but cannot deal with other types such as constants or more complex terms.

  The Clorm mechanism of a data conversion signatures provide a more principled
  and transparent approach; it can deal with arbitrary conversions and all data
  conversions are clear since they are specified as part of the signature.


Development
-----------
* Python version: Clorm was developed using Python 3.7 and has been tested with Python 3.6.
* Clingo version: Clorm has been tested with Clingo version 5.3 and 5.4 (development release)

TODO
----
* add more examples
* build library of resuable ASP integration components (started - still unsure
  how useful it would be).
* add a debug library? -- only vague ideas at this stage.

Alternatives
------------

I think an ORM interface provides a natural fit for getting data into and out of
the Clingo solver. However, there will be other opinions on this. Also, data IO
is only one aspect of how you might want to interact with the ASP solver.

So, here are some other projects for using Python and Clingo:

* `PyASP <https://github.com/sthiele/pyasp>`_
* `Clyngor <https://github.com/aluriak/clyngor>`_


