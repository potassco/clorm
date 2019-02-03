Clingo ORM (ClORM)
==================

ClORM is a Python library that provides an Object Relational Mapping (ORM)
interface to the Clingo Answer Set Programming (ASP) solver. The goal of this
library is to make it easier to integrate Clingo within a Python application. It
is designed to supplement and not replace the existing Clingo API.

When integrating an ASP program into an application you typically want to model
the domain as a statically written ASP program, but then to generate problem
instances and process the results dynamically. ClORM makes this integration
cleaner, both in terms of code readability but also by making it easier to
refactor the python code as the ASP program evolves.

Note: ClORM currently only works with Python 3.x.

Installation
------------

The easiest way to install ClORM is with Anaconda. Assuming you have already
installed some variant of Anaconda, first you need to install Clingo:

.. code-block:: bash

    $ conda install -c potassco clingo

Then install ClORM:

.. code-block:: bash

    $ conda install -c daveraja clorm

Quick Start
-----------

The following example highlights the basic features of ClORM. The ASP and Python
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

   from clorm import Predicate, ConstantField, IntegerField, FactBaseHelper, ph1_
   from clorm.clingo import Control

Note: Importing from ``clorm.clingo`` instead of ``clingo``.

   While it is possible to use ClORM with the raw clingo library, a wrapper
   library is provided to make the integration seemless. This wrapper (should)
   behave identically to the original module, except that it extends the
   functionality to offer integration with ClORM objects. It is also possible to
   `monkey patch <https://en.wikipedia.org/wiki/Monkey_patch>`_ Clingo if this
   is your preferred approach (see the `documentation
   <https://clorm.readthedocs.io/en/latest/>`_).

The next step is to define a data model that maps the Clingo predicates to
Python classes. ClORM introduces two basic concepts for defining the data model:
``Predicate`` and ``FactBase``. ``Predicate`` maps the ASP predicates to Python
classes, while ``FactBase`` provides a container for storing facts of these
types.  Both classes must be sub-classed when defining the data model. A helper
class ``FactBaseHelper`` is provided for simplifying the construction of the
``FactBase`` sub-class.

.. code-block:: python

   fbh = FactBaseHelper()

   @fbh.register
   class Driver(Predicate):
       name=ConstantField()

   @fbh.register
   class Item(Predicate):
       name=ConstantField()

   @fbh.register
   class Assignment(Predicate):
       item=ConstantField()
       driver=ConstantField(index=True)
       time=IntegerField()

   DB = fbh.create_class("DB")

The above code defines three classes to match the ASP program's input and output
predicates.

``Driver`` maps to the ``driver/1`` predicate, ``Item`` maps to ``item/1``, and
``Assignment`` maps to ``assignment/3``. A predicate may contain zero or more
*fields* (using database terminology). Fields can be thought of as *term
definitions* as they define how a logical *term* is converted to, and from, a
Python object. The number of fields must match the predicate arity and the order
in which they are declared must also match the position of each term in the ASP
predicate.

The ``FactBaseHelper`` provides a decorator that registers the predicate class
with the helper. It then provides a member function for dynamically defining a
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

    query=solution.select(Assignment).where(Assignment.driver == ph1_).order_by(Assignment.time)

A ClORM query can be viewed as a simplified version of a traditional database
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
the query definition. ClORM has four predefined placeholders but more can be
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

The above example shows some of the main features of ClORM and how to match the
Python data model to the defined ASP predicates. For more details about how to
use ClORM see the `documentation <https://clorm.readthedocs.io/en/latest/>`_.

Development
-----------
* Python version: ClORM was developed using Python 3.7 and has been tested with Python 3.6.
* Clingo version: ClORM has been tested with Clingo version 5.3.0 and 5.3.1

TODO
----
* complete Sphinx documentation
* add more examples

* add a library of resuable ASP integration components (started).
* add a debug library -- my ideas on this are still vague.

Alternatives
------------

I think an ORM interface provides a natural fit for getting data into and out of
the Clingo solver. However, there will be other opinions on this. Also, data IO
is only one aspect of how you might want to interact with the ASP solver.

So, here are some other projects for using Python and Clingo:

* `PyASP <https://github.com/sthiele/pyasp>`_
* `Clyngor <https://github.com/aluriak/clyngor>`_


