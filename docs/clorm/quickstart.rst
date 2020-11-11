Quick Start
===========

This section highlights the basic features of Clorm by way of a simple
example. This example covers:

* Defining a simple data model,
* Combining a statically written ASP program with dynamically generated data,
* Running the Clingo solver,
* Querying and processing the solution returned by the solver.

This example is located in the project's ``examples/quickstart`` sub-directory;
where the ASP program is ``quickstart.lp`` and the Python program is
``quickstart.py``. There is also a version ``embedded_quickstart.lp`` that can
be called directly from Clingo:

.. code-block:: bash

   $ clingo embedded_quickstart.lp

This document is about the Clingo ORM API and it is therefore assumed that the
reader is reasonably familiar with ASP syntax and how to write an ASP
program. However, if this is not the case it is worth going to the `Clingo docs
<https://potassco.org/doc/start>`_ for links to some good reference material.

While we assume that the reader is familiar with ASP, we do not assume that the
reader is necessarily familiar with the official Clingo Python API. Since Clorm
is designed to be used with the Clingo API we therefore provide some basic
explanations of the relevant steps necessary to run the Clingo solver. However,
for more detailed documentation see the `Clingo API
<https://potassco.org/clingo/python-api/current/clingo.html>`_.

An Example Scenario
-------------------

Imagine you are running a courier company and you have drivers that need to make
daily deliveries.  An item is delivered during one of four time slots, and you
want to assign a driver to deliver each item, while also ensuring that all items
are assigned and drivers aren't double-booked for a time slot.

You also want to apply some optimisation criteria. Firstly, you want to minimise
the number of drivers that you use (for example, because bringing on a driver
for a day has some fixed cost). Secondly, you want to deliver items as early in
the day as possible.

The ASP Program
---------------

The above crieria can be encoded with the following simple ASP program:

.. code-block:: prolog

   time(1..4).

   1 { assignment(I, D, T) : driver(D), time(T) } 1 :- item(I).
   :- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

   working_driver(D) :- assignment(_,D,_).

   #minimize { 1@2,D : working_driver(D) }.
   #minimize { T@1,D : assignment(_,D,T) }.


You will notice that while the above ASP program encodes the *problem domain*,
but it does not specify the *problem instance*, which in this case means
specifying the individual delivery drivers and items to be delivered.

The Python Program
------------------

Unlike the ASP encoding of the *problem domain*, which is largely static and
changes only if the requirements change, the *problem instance* changes
daily. Hence it cannot be a simple static encoding but must instead be generated
as part of the Python application that calls the ASP solver and processes the
solution. Clorm is designed with this use-case in mind.

First the relevant libraries need to be imported.

.. code-block:: python

   from clorm import Predicate, ConstantField, IntegerField
   from clorm.clingo import Control

.. note:: Importing from ``clorm.clingo`` instead of ``clingo``.

   While it is possible to use Clorm with the raw clingo library, a wrapper
   library is provided to make the integration seemless. This wrapper (should)
   behave identically to the original module, except that it extends the
   functionality to offer integration with Clorm objects. It is also possible to
   `monkey patch <https://en.wikipedia.org/wiki/Monkey_patch>`_ Clingo if this
   is your preferred approach (see :ref:`api_clingo_integration`).


Defining the Data Model
-----------------------

The most important step is to define a *data model* that maps the Clingo
predicates to Python classes. Clorm provides the ``Predicate`` and
``ComplexTerm`` classes for this purpose (although, for this example only the
``Predicate`` class is needed). These classes must be sub-classed; a
``Predicate`` sub-class defines a direct mapping to an underlying ASP logical
predicate. The parameters of the predicate are specified using a number of
*field* classes. Fields can be thought of as *term definitions* as they define
how a logical *term* is converted to, and from, a Python object. Clorm provides
three standard field classes, ``ConstantField``, ``StringField``, and
``IntegerField``, that correspond to the standard *logic programming* data types
of constant, string, and integer.

.. code-block:: python

   class Driver(Predicate):
       name=ConstantField

   class Item(Predicate):
       name=ConstantField

   class Assignment(Predicate):
       item=ConstantField
       driver=ConstantField
       time=IntegerField

The above code defines three classes to match the ASP program's input and output
predicates, where the name of the predicate to map to is derived from the
declared class name.

``Driver`` maps to the ``driver/1`` predicate, ``Item`` maps to ``item/1``, and
``Assignment`` maps to ``assignment/3`` (note: the ``/n`` is a common logic
programming notation for specifying the arity of a predicate or function). A
predicate can contain zero or more fields.

The number of fields in the ``Predicate`` declaration must match the predicate
arity and the order in which they are declared must also match the position of
each term in the ASP predicate.

One thing to note here is that there is no ``Predicate`` sub-class that was
defined corresponding to the ``working_driver/1`` predicate. Clorm does not
require that *all* ASP predicates have a corresponding Python ``Predicate``
sub-class. In this case ``working_driver/1`` is only of interest within the ASP
program itself and is not used for defining the relevant inputs and outputs of
the solver, so there is no need to define any Python interface.

Using the Data Model to Generate Solutions
------------------------------------------

Once the data model has been defined it can be used to instantiate facts that
are asserted to, or extract from, the ASP solver. In particular, it will be used
to dynamically add the facts that make up a problem instance, and then to
extract and print the *models* that correspond to solutions to the problem.

First the Clingo ``Control`` object needs to be created and initialised, and the
static problem domain encoding must be loaded.

.. code-block:: python

    ctrl = Control(unifier=[Driver,Item,Assignment])
    ctrl.load("quickstart.lp")

The ``clorm.clingo.Control`` object controls how the ASP solver is run. When the
solver runs it generates *models*. These models constitute the solutions to the
problem. Facts within a model are encoded as ``clingo.Symbol`` objects. The
``unifier`` argument is important as it defines which symbols are turned into
``Predicate`` instances.

For every symbol fact in the model, Clorm will successively attempt to *unify*
(or match) the symbol against the predicates in the unifier list. When a match
is found the symbol is used to define an instance of the matching predicate. Any
symbol that does not unify against any of the predicates is ignored.

Once the control object is created and the unifier predicates specified the
static ASP program is loaded.

Next we generate a problem instance by generating a lists of ``Driver`` and
``Item`` objects. These items are added to a ``clorm.FactBase`` object, which is
a specialised set-like container for storing facts (i.e., predicate instances).

.. code-block:: python

    from clorm import FactBase

    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = FactBase(drivers + items)

The ``Driver`` and ``Item`` constructors use named parameters that match the
declared field names. While Clorm supports the use of positional arguments to
initialise instances, doing so will potentially make the code harder to
refactor. So in general you should avoid using positional arguments except for a
few cases (eg., simple tuples where the order is unlikely to change).

Now, these input facts can be added to the control object and combined with the
previously loaded ASP program to produce a *grounded* ASP program.

.. code-block:: python

    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

At this point the control object is ready to be run and generate
solutions. There are a number of ways in which the ASP solver can be run (see
the `Clingo API documentation
<https://potassco.org/clingo/python-api/5.4/#clingo.Control.solve>`_). For this
example we run it using a callback function, which is called each time a model
is found.

.. code-block:: python

    solution=None
    def on_model(model):
        global solution     # Note: use `nonlocal` keyword depending on scope
        solution = model.facts(atoms=True)

    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")

The ``on_model()`` callback is triggered for every new model. Because of the ASP
optimisation statements this callback can potentially be triggered multiple times
before an optimal model is found. Also, note that if the problem is
unsatisfiable then it will never be called and you should always check for this
case.

The line ``solution = model.facts(atoms=True)`` extracts only instances of the
predicates that were registered with the ``unifier`` parameter that was passed
down through the ``Control`` object constructor. As mentioned earlier, any facts
that fail to unify are ignored. In this case it ignores the ``working_driver/1``
instances. The unified facts are stored and returned in a ``clingo.FactBase``
object.

Querying
--------

The final part of our Python program involves querying the solution to print out
the relevant facts. To do this we call the ``FactBase.select()`` member function
that returns a suitable query object.

.. code-block:: python

    from clorm import ph1_

    query=solution.select(Assignment).where(Assignment.driver == ph1_).order_by(Assignment.time)

A Clorm query can be viewed as a simplified version of a traditional database
query, and the function call syntax will be familiar to users of Python ORM's
such as SQLAlchemy or Peewee.

Here we want to find ``Assignment`` instances that match the ``driver`` field to
a special placeholder object ``ph1_`` and to return the results sorted by the
assignment time. The value of ``ph1_`` will be provided when the query is
executed. Note: seperating query definition from query execution allows for a
query to be re-used.

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
the query definition. Clorm has four predefined placeholders ``ph1_``,... ,
``ph4_``, but more can be created using the ``ph_`` function.

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

Other Clorm Features
--------------------

The above example shows some of the basic features of Clorm and how to match the
Python data model to the defined ASP predicates. However, beyond the basics
outlined above there are other important features that will be useful for more
complex interactions. These include:

* Defining complex-terms. Many ASP programs include complex terms (i.e., either
  tuples or functional objects). Clorm supports predicate definitions that
  include complex-terms using a ``ComplexTerm`` class. Every defined complex
  term has an associated ``Field`` property that can be used within a Predicate
  definition.

.. code-block:: python

    from clorm import ComplexTerm

    class Event(ComplexTerm):
        date=StringField
	name=StringField

    class Log(Predicate):
        event=Event.Field
	level=IntegerField

The above definition can be used to match against an ASP fact containing a
complex term.

.. code-block:: prolog

    log(event("2019-04-05", "goto shops"), 0).

* Custom fields. The ``IntegerField``, ``StringField``, and ``ConstantField``
  classes are in fact sub-classes of a ``RawField`` class. Custom data
  conversions can be performed by sub-classing ``RawField`` directly, or by
  sub-classing one of its existing sub-classes. For example, a ``DateField`` can
  be defined that converts Python date objects into Clingo strings with
  YYYY-MM-DD formatting.

.. code-block:: python

    from clorm import StringField          # StringField is a sub-class of RawField
    from datetime import datetime

    class DateField(StringField):
        pytocl = lambda dt: dt.strftime("%Y-%m-%d")
        cltopy = lambda s: datetime.datetime.strptime(s,"%Y-%m-%d").date()

    class DeliveryDate(Predicate):
        item=ConstantField()
        date=DateField()

* Clingo allows Python functions to be called from within an ASP program using
  the @-syntax. Values are passed to these Python functions as ``clingo.Symbol``
  objects and it is up to the Python code to perform all appropriate data
  conversions.

  Clorm provides a number of mechanisms to automate this data conversion process
  through the specification of a *data conversion signature*.

  In the following example the function ``add`` is decorated with an automatic
  data conversion signature that accepts two input integers and returns an
  output integer.

.. code-block:: python

    @make_function_asp_callable(IntegerField, IntegerField, IntegerField)
    def add(a,b): a+b

.. code-block:: prolog

    f(@add(5,6)).    % grounds to f(11).

The default behaviour of the Clingo API does infact provide some minimal
automatic data conversion for the @-functions. In particular, it will
automatically convert numbers and strings, however it cannot deal with other
types such as constants or more complex terms.

The Clorm mechanism of a data conversion signatures provide a more principled
and transparent approach; it can deal with arbitrary conversions and all data
conversions are clear since they are specified as part of the signature.

