Quick Start
===========

We now highlight the basic features of Clorm by way of a simple example. This
example covers:

* defining a simple data model
* loading a statically written ASP program and dynamically generated data
* running the Clingo solver
* querying and processing the solution returned by the solver

This example is located in the project's ``examples`` sub-directory; where the
ASP program is ``quickstart.lp`` and the Python program is ``quickstart.py``.

This document is about the Clingo ORM API and we therefore assume that the
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

Imagine you are running a courier company and you have drivers that deliver
items on a daily basis. An item is delivered during one of four time slots, and
you want to assign a driver to deliver each item, while also ensuring that all
items are assigned and drivers aren't double-booked for a time slot.

You also want to apply some optimisation criteria. Firstly, you want to minimise
the number of drivers that you use (for example, because bringing a driver on
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
it does not specify any actually delivery drivers or items to be
delivered. Hence, to actually solve a problem we need to provide it with a
*problem instance* (i.e., a specific set of drivers and items).

The Python Program
------------------

Unlike the ASP encoding of the *problem domain*, which is largely static and
changes only if the requirements change, the problem instance changes
daily. Hence it cannot be a simple static encoding but must instead be generated
as part of the Python application that calls the ASP solver and processes the
solution.

First the relevant libraries need to be imported.

.. code-block:: python

   from clorm import Predicate, ConstantField, IntegerField, FactBaseBuilder, ph1_
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

The most important step is to define a data model that maps the Clingo
predicates to Python classes. Clorm introduces the ``Predicate`` and
``ComplexTerm`` classes, which must be sub-classed, that define a direct mapping
to ASP predicates (for this example we only need the ``Predicate`` class).

Clorm further introduces the ``FactBase`` class as a general container for
storing predicate instances (i.e., *facts*), as well as providing a helper class
``FactBaseBuilder`` that makes it easy to build fact bases. The data generated
by the ASP solver is returned as Clingo ``Symbol`` objects. The
``FactBaseBuilder`` provides a mechanism to *unify* Clorm predicate classes with
Clingo symbols.

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
``Assignment`` maps to ``assignment/3`` (note: the ``/n`` is a common logic
programming notation for specifying the arity of a predicate or function). A
predicate can contain zero or more *fields* (using database terminology). Fields
can be thought of as *term definitions* as they define how a logical *term* is
converted to, and from, a Python object.

The number of fields in the ``Predicate`` declaration must match the predicate
arity and the order in which they are declared must also match the position of
each term in the ASP predicate.

The ``FactBaseBuilder`` provides a decorator that registers the predicate class
with the builder. Once a predicate class is registered the builder will use this
class to try and unify against Clingo symbols. It also ensures that the fact
base is built with the appropriate indexes as specified by ``index=True`` for
the field. In the example, the ``driver`` field is indexed allowing for faster
queries when searching for specific drivers. As with databases, indexing
improves query performance but should be used sparingly.

Using the Data Model
--------------------

Having defined the data model we now show how to dynamically add a problem
instance, solve the resulting ASP program, and print the solution.

First we create the Clingo ``Control`` object and load the ASP program.

.. code-block:: python

    ctrl = Control()
    ctrl.load("quickstart.lp")


Next we generate a problem instance by generating a lists of ``Driver`` and
``Item`` objects. These items are added to an ``FactBase`` instance.

.. code-block:: python

    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = FactBase(drivers + items)

The ``Driver`` and ``Item`` constructors require named parameters that match the
declared term names. Note, a design decision was taken to disallow "normal"
Python positional arguments as it would make it too easy to write brittle code;
for example, the code would break if the order of the fields was changed.

The facts can now be added to the control object and the combined ASP program
grounded.

.. code-block:: python

    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

Next we run the solver to generate solutions. The solver is run with a callback
function that is called each time a solution (i.e., *model*) is found.

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
it ignores the ``working_driver/1`` instances. These gathered facts are stored
and returned in a fact base.

The final part of our Python program involves querying the solution to print out
the relevant facts. To do this we call the ``FactBase.select()`` member function
that returns a suitable fact base query object.

.. code-block:: python

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
each driver and print the result. Note, the ``FactBaseBuilder`` instance ``fbb``
had the ``Assignment.driver`` field registered as an index. This means that the
returned ``FactBase`` instance will have indexing for this field and therefore
querying based on this field will be relatively efficient.

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

The above example shows some of the main features of Clorm and how to match the
Python data model to the defined ASP predicates.
