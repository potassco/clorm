Clingo ORM (CLORM)
==================

CLORM is a Python library that provides an Object Relational Mapping (ORM)
interface to the Clingo Answer Set Programming (ASP) solver. The goal of this
library is to make it easier to integrate Clingo into a (Python) application
environment.

When integrating an ASP program into an application you typically want to model
the domain as a statically written ASP program, but then to generate problem
instances and process the results dynamically. CLORM makes this integration
cleaner, both in terms of code readability but also by making it easier to
refactor the python code as the ASP program evolves.

Background
----------

`ASP <https://en.wikipedia.org/wiki/Answer_set_programming>`_ is a AI/logic
based language for modelling and solving combinatorial optimisation
problems. ASP has a Prolog-style language for defining problems in terms of
predicates and the relations between them. The solver then generates solutions
(called *models* or *answer sets*) consisting of a sets of ground facts that are
(minimally) consistent with the defintions.

`Clingo <https://potassco.org>`_ is the leading open-source ASP solver. It can
be run as a stand-alone executable or integrated as a library into other
languages. It has very good support for Python with an extensive API for
interacting with the solving.

Clingo supports Python in two ways:

* calling Python functions from within an ASP program,
* running Clingo from within a Python application.

While the Python API is both extensive and flexible it is fairly low-level when
it comes to getting data into, and out of, the solver. This also means that as
an ASP program evolves and changes, adapting the Python code to match the ASP
code can become tedious. CLORM is intended to help by providing a higher-level
ORM interface to make it easy to match the ASP facts to Python objects.

`ORM <https://en.wikipedia.org/wiki/Object-relational_mapping>`_ interfaces are
a common way of interacting with relational databases and there are some
well-known Python ORMs (e.g., SQLAlchemy and Peewee).

Use Case
--------

The basic use case is for a Python-based application that needs to interact with
the Clingo reasoner. A typical such application would be Python web-app with a
database backend that supplies data for some form of high-level reasoning (e.g.,
business logic). The database is queried and the results of the query are
asserted to the Clingo reasoner. Clingo then produces a solution (or sets of
possibly solutions) which can be used in the application or simply inserted back
to the database.

Installation
------------

The easiest way to install CLORM is with Anaconda. This is ideal if you have
already used Anaconda for installing Clingo.

So assumming you have already installed Clingo with something like:

.. code-block:: bash

    $ conda install -c potassco clingo

Then also install CLORM with:

.. code-block:: bash

    $ conda install -c daveraja clorm


Note: CLORM currently only works with Python 3.x. I may look at supporting
Python 2.7 in the future.


Quick Start
-----------

The following is a simplified scheduling problem. Imagine you are running a
courier company and you have drivers and items that need to be delivered. An
item is delivered during one of four time slots, and you want to assign drivers
to delivery items, ensuring that all items are assigned and drivers aren't
double-booked for a time slot.

You want to minimise the number of drivers you use (for example, because
bringing a driver on for a day has some fixed cost), and as a secondary
optimisation criteria you want to deliver items as early in the day as possible.

The following ASP program encodes this problem:

.. code-block:: prolog

   time(1..4).

   1 { assignment(I, D, T) : driver(D), time(T) } 1 :- item(I).
   :- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

   working_driver(D) :- assignment(_,D,_).

   #minimize { 1@2,D : working_driver(D) }.
   #minimize { T@1,D : assignment(_,D,T) }.


Now, assume that this ASP program is in a file ``quickstart.lp``.

We now write a Python program that loads up this ASP program, gives it a problem
instance (i.e., a list of drivers and items to be delivered) and generates a
solution as an assignment of drivers to deliver items. The following gives a
breakdown of this Python program.

First we need to import from the relavant libraries

.. code-block:: python


   from clorm import monkey; monkey.patch()
   from clorm import Predicate, ConstantField, IntegerField, FactBaseHelper, ph1_
   from clingo import Control

The first line `monkey patches <https://en.wikipedia.org/wiki/Monkey_patch>`_ a
number of Clingo classes by creating wrappers that make the integration with
CLORM seemless. You can of course use CLORM without monkey patching Clingo but
it makes the interaction with the solver a bit more cumbersome.

The second and third line imports the basic functions and classes that we need.

The next step is to define a data model that maps the Clingo predicates to
Python objects. CLORM introduces two basic classes for defining the data model:
``Predicate`` and ``FactBase``. Both classes will need to be sub-classed when
defining the data model.

The ``Predicate`` class provides the basic object relational mapping so that
ground predicate instances (i.e., facts) can be mapped to class instances.

The ``FactBase`` provides a container class for storing and querying a set
facts. Loosely you can think of it like defining a database schema. Because
there is a close link between defining the predicates and defining the
associated ``FactBase`` CLORM provides a helper class to make this process
(almost) automatic.

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


The ``FactBaseHelper`` class provides a mechanism for easily creating
``FactBase`` sub-classes. The instance is declared as a context so that any
predicate declaration within this context will be automatically incorporated
into the subsequently defined ``FactBase`` sub-class.

Within the ``FactBaseHelper`` context we declare the ``Driver`` predicate to
match the ASP ``driver`` definition. Note: by default the name of the matching
ASP predicate is derived from the class name by simply making the first letter
lower-case. The ASP ``driver`` predicate only has one parameter which we declare
here as a Clingo constant (as opposed to a String). This process is repeated for
the ASP ``item`` predicate to create a Python ``Item`` class. The instances of
``Driver`` and ``Item`` will become the problem instances.

The other predicate that we care about is the ASP ``assignment`` predicate, a
set of which constitute a solution to the problem. Since ``assignment`` has an
arity of three we need to define three fields; the ``item``, the ``driver``, and
the ``time``. Note, the name of the fields are arbitrary but the order is
important and must correspond to the order of the ASP code.

The observant reader will note that the declaration of the ``driver`` field is
defined with ``index=True``. This is a useful option for defining the
interface. While it is does not change the mapping of the ``Assignment`` object
to the ``assignment`` ASP instances, however it does modify the
``FactBaseHelper`` when it creates the ``FactBase`` sub-class. Specially, it
will create an index on the ``driver`` field, to improve performance when
querying the set of facts. Note: just like with defining a database, using
indexes should be used sparingly.

Finally, the ``FactBaseHelper`` object is used to dynamically define a ``DB``
class that is a sub-class of ``FactBase`` built from the ``Predicate``
declarations within the context. We can then use this sub-class as a container
for storing facts; either for the problem instance or the for the solution
extracted from an ASP model. Note: it is worth emphasising that the helper class
mechanism is purely a convenience and a ``FactBase`` sub-class can also be
defined manually for greater control.


Now with the ASP program written and the Python data model defined we now need a
simple program that generates a problem instance, solves it, and prints the
solution.

First we create the Clingo ``Control`` object and load the ASP program.

.. code-block:: python

    # Create and load asp file that encodes the problem domain
    ctrl = Control()
    ctrl.load("quickstart.lp")


Next we generate a problem instance by generating a set of drivers and
items. These items are added to a ``DB`` instance (which was the dynamically
declared ``FactBase`` sub-class).

.. code-block:: python

    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = DB(drivers + items)

You can see that creating a ``Driver`` object is performed by calling the
constructor with named parameters matching the field names. Note: only named
arguments are supported, you cannot use "normal" list arguments.

Finally, the ``DB`` class is initialised with a list of facts.

Now the facts need to be added to the control object and the ASP program needs
to be grounded.

.. code-block:: python

    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

It is worth noting that the ``add_facts()`` member function is part of the monkey
patching of ``Clingo.Control``. It adds a ``FactBase`` (alternative a list of
facts) to the program.

The second line is the usual call to ground the ASP program.

At this point we have a ground ASP program for the specific problem
instance. Next we need to do the usual Clingo task of running the solving with a
callback function to examine the individual models.

.. code-block:: python

    solution=None
    def on_model(model):
        nonlocal solution
        solution = model.facts(DB, atoms=True)
    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")


The above is a fairly standard Clingo call to the solver, where a callback
function is provided to examine the individual models. Because our ASP program
has optimisation statements this callback can potentially be called multiple
times until an optimal solution is reached. Note: of course if the problem is
unsatisfiable then it will never be called and you should always test for this.

The only line that is different to a normal Clingo program is the assignment of
the solution ``solution = model.facts(DB, atoms=True)``. The ``Model.facts()``
function is another convenience member function that is created when monkey
patching Clingo. It is essentially a wrapper around the standard
``Model.symbols()`` where the first parameter is a ``FactBase`` class object and
the remaining arguments are the same as for ``Model.symbols()``.

In the above code we simply want to take all atoms in the model and add the
instances of the defined predicates to the fact base object. Here the ``DB``
class object provides facilities to unify the raw Clingo.Symbol objects against
its list of defined predicates, and will ignore all other predicates. For
example, in our ASP program we have a ``working_driver/1`` predicate for which
we haven't defined a corresponding Python predicate.

While the callback may be called multiple times, in our application we only
maintain the last (optimal) solution. It is worth noting that in order to reduce
the amount of unnecessary computation the ``FactBase`` sub-classes have a
delayed initialisation mode. Internally it stores a list of ``Clingo.Symbol``
objects and this list is only process the first time the fact base is
accessed. This means that even though the callback will create a new ``DB``
objects every time, it will not actually import the data (which involves
unifying predicates and creating indexes) when the object is created. So this
will only happen for the last object that is generated when the ``DB`` object is
queried.

So now, we can process the solution and print the assignment for the day. To do
this we first create a `Select` object.

.. code-block:: python

    query=solution.select(Assignment).where(Assignment.driver == ph1_)

The query can be viewed as a simplified version of a traditional database
`Select` statement. Here it creates a ``Select`` object over the ``Assignment``
predicates within the ``solution`` object. Note, ``query`` is not the result of
the query but rather the query object. This object still needs to be executed to
generate the results. Importantly, this means that a query object can be
reused. In fact the ``where`` clause here specifies that we want to match the
``driver`` field against a special placeholder object ``ph1_``. The value of
this object is only bound to an actual value when the query is executed.

We now want to execute the query for all the known drivers to report their
assignments.

.. code-block:: python

    for d in drivers:
        assignments = list(query.get(d.name))
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))

The interesting piece of code here is the second line ``assignments =
list(query.get(d.name))``. The `get()`` call executes the query with the
driver's ``name`` field as the value to be matched against. Because it is the
first parameter it matches against the placeholder ``ph1_`` in the query
definition. Currently, CLORM support up to four placeholders.

The second interesting aspect of this call is that because of the ``index=True``
option in the defintion of ``Assignment.driver`` it means that this field is
indexed. Hence the query will be relatively efficient and not have to examine
every assignment in order to extract the ones for the given driver.

Finally, the need to wrap the ``get`` call in a ``list()`` object is simply
because ``get`` is implement as a python generator and doesn't simply return a
list.

This example is in the ``examples`` directory.

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

This closes the loop; we now have a Python application that generates problem
instances which are easily grounded as part of a ASP program and the solution
processed. There are a number of other aspects to the CLORM API but hopefully
the above covers a fairly broad use case.

Development
-----------
* Python version: CLORM was developed using Python 3.7 and has been tested with Python 3.6.
* Clingo version: CLORM has been tested with clingo version 5.3.0 and 5.3.1

TODO
----
* clean up the API
* add Sphinx documentation
* add more examples

* add a library of resuable ASP integration components.
* add a debug library.

