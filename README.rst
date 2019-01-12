Clingo ORM (CLORM)
==================

CLORM is a Python library that provides an Object Relational Mapping (ORM)
interface to the Clingo Answer Set Programming (ASP) solver. The goal of this
library is to make it easier to integrate Clingo within a Python application. It
is designed to supplement and not replace the existing Clingo API.

When integrating an ASP program into an application you typically want to model
the domain as a statically written ASP program, but then to generate problem
instances and process the results dynamically. CLORM makes this integration
cleaner, both in terms of code readability but also by making it easier to
refactor the python code as the ASP program evolves.

Note: CLORM currently only works with Python 3.x.

Installation
------------

The easiest way to install CLORM is with Anaconda. Assuming you have already
installed some variant of Anaconda, first you need to install Clingo:

.. code-block:: bash

    $ conda install -c potassco clingo

Then install CLORM:

.. code-block:: bash

    $ conda install -c daveraja clorm

Quick Start
-----------

The following example highlights the basic features of CLORM. The ASP and Python
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


   from clorm import monkey; monkey.patch()
   from clorm import Predicate, ConstantField, IntegerField, FactBaseHelper, ph1_
   from clingo import Control

The first line `monkey patches <https://en.wikipedia.org/wiki/Monkey_patch>`_ a
number of Clingo classes by creating wrappers that makes the integration with
CLORM seemless. You can of course use CLORM without monkey patching Clingo, but
it requires a bit more code.

The next step is to define a data model that maps the Clingo predicates to
Python classes. CLORM introduces two basic concepts for defining the data model:
``Predicate`` and ``FactBase``. ``Predicate`` maps the ASP predicates to Python
classes, while ``FactBase`` provides a container for storing facts of these
types.  Both classes must be sub-classed when defining the data model. A helper
class ``FactBaseHelper`` is provided for simplifying the construction of the
``FactBase`` sub-class.

.. code-block:: python

   with FactBaseHelper() as fbh:

	class Driver(Predicate):
            name=ConstantField()

	class Item(Predicate):
	    name=ConstantField()

	class Assignment(Predicate):
	    item=ConstantField()
	    driver=ConstantField(index=True)
	    time=IntegerField()

   DB = fbh.create_class("DB")

The above code defines three classes to match the ASP program's input and output
predicates.

``Driver`` maps to the ``driver/1`` predicate, ``Item`` maps to ``item/1``, and
``Assignment`` maps to ``assignment/3``. The number of the field definitions
must match the predicate arity and the order in which the fields are defined
must also match the position of each parameter in the predicate.

The ``FactBaseHelper`` class provides a context for capturing the predicate
definitions and provides a member function for dynamically defining a
``FactBase`` sub-class. Here we define the class ``DB`` for storing predicate
instance (i.e., the *facts*) for these types.

You will notice that the declaration of the ``driver`` field contains the option
``index=True``. This ensures that the ``driver`` field is indexed whenever an
``Assignment`` object is inserted into a ``DB`` instance. As with a traditional
database indexing improves query performance but should also be used sparingly.

Having defined the data model we now show how to dynamically add a problem
instance, solve the resulting ASP program, and print the solution.

First we create the Clingo ``Control`` object and load the ASP program.

.. code-block:: python

    ctrl = Control()
    ctrl.load("quickstart.lp")


Next we generate a problem instance by generating a lists of ``Driver`` and
``Item`` objects. These items are added to a ``DB`` instance.

.. code-block:: python

    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = DB(drivers + items)

The ``Driver`` and ``Item`` constructors require named parameters that match the
declared field names; you cannot use "normal" Python list arguments.

Now, the facts can now be added to the control object and the combined ASP
program grounded.

.. code-block:: python

    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

Next we run the solver to generate solutions. The solver is run with a callback
function that is called each time a solution is found. Note: the solution of an
ASP program is typically called an *answer set* or simply a *model*.

.. code-block:: python

    solution=None
    def on_model(model):
        nonlocal solution
        solution = model.facts(DB, atoms=True)
    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")

The ``on_model()`` callback is triggered for every new model. Because of the ASP
optimisation statements this callback can potentially be triggered multiple times
before an optimal model is found. Also, note that if the problem is
unsatisfiable then it will never be called and you should always check for this
case.

The line ``solution = model.facts(DB, atoms=True)`` extracts only instances of
the predicates that were defined in the data model. In this case it ignores the
``working_driver/1`` instances. These facts are stored and returned in a ``DB``
object.

The final part of our Python program involves querying the solution to print out
the relevant parts. To do this we call the ``DB.select()`` member function that
returns a suitable ``Select`` object.

.. code-block:: python

    query=solution.select(Assignment).where(Assignment.driver == ph1_)

A CLORM query can be viewed as a simplified version of a traditional database
query. Here we want to find ``Assignment`` instances that match the ``driver``
field to a special placeholder object ``ph1_``. The value of ``ph1_`` will be
provided when the query is actually executed; which allows the query to be
re-run multiple times with different values.

In particular, we now iterate over the list of drivers and execute the query for
each driver and print the result.

.. code-block:: python

    for d in drivers:
        assignments = list(query.get(d.name))
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))

Calling ``query.get(d.name)`` executes the query for the given driver. Because
``d.name`` is the first parameter it matches against the placeholder ``ph1_`` in
the query definition. Currently, CLORM support up to four placeholders.

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

The above example shows some of the main features of CLORM and how to match the
Python data model to the defined ASP predicates. For more details of the CLORM
API see the documentation (**coming soon**).

Development
-----------
* Python version: CLORM was developed using Python 3.7 and has been tested with Python 3.6.
* Clingo version: CLORM has been tested with Clingo version 5.3.0 and 5.3.1

TODO
----
* add Sphinx documentation
* add more examples

* add a library of resuable ASP integration components.
* add a debug library -- my ideas on this are still vague.

