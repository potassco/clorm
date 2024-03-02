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
<https://potassco.org/clingo/python-api/5.7/clingo/>`_.

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

   from clorm import Predicate, ConstantStr
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

The most important step is to define a *data model* that maps the Clingo predicates to Python
classes. Clorm provides the :class:`~clorm.Predicate` base class for this purpose; a
:class:`~clorm.Predicate` sub-class defines a direct mapping to an underlying ASP logical
predicate. The parameters of the predicate are specified using a number of *fields*, similar to
the definition of a standard Python ``dataclass``. In the Clorm context the fields can be
thought of as *term definitions*, as they define how a logical *term* is converted to, and
from, a Python object.

ASP's *logic programming* syntax allows for three primitive types: integer, string, and
constant. From the Python side this corresponds to the standard types ``int`` and ``str``, as
well as a special Clorm defined type ``ConstantStr``. Note: ``ConstantStr`` is sub-classed from
``str`` in order to disambiguate between ASP constants and strings, while still offering the
same Python type checking behaviour of the ``str`` parent class.

.. code-block:: python

   class Driver(Predicate):
       name: ConstantStr

   class Item(Predicate):
       name: ConstantStr

   class Assignment(Predicate):
       item: ConstantStr
       driver: ConstantStr
       time: int

The above code defines three classes to match the ASP program's input and output
predicates, where the name of the predicate to map to is derived from the
declared class name.

``Driver`` maps to the ``driver/1`` predicate, ``Item`` maps to ``item/1``, and
``Assignment`` maps to ``assignment/3`` (note: the ``/n`` is a common logic
programming notation for specifying the arity of a predicate or function). A
predicate can contain zero or more fields.

The number of fields in the :class:`~clorm.Predicate` declaration must match the
predicate arity and the order in which they are declared must also match the
position of each term in the ASP predicate.

One thing to note here is that there is no :class:`~clorm.Predicate` sub-class
that was defined corresponding to the ``working_driver/1`` predicate. Clorm does
not require that *all* ASP predicates have a corresponding Python
:class:`~clorm.Predicate` sub-class. In this case ``working_driver/1`` is only
of interest within the ASP program itself and is not used for defining the
relevant inputs and outputs of the solver, so there is no need to define any
Python interface.

Using the Data Model to Generate Solutions
------------------------------------------

Once the data model has been defined it can be used to instantiate facts that are asserted to,
or extracted from, the ASP solver. In particular, it will be used to dynamically add the facts
that make up a problem instance, and then to extract and print the *models* that correspond to
problem solutions.

First, the :class:`~clorm.clingo.Control` object needs to be created and
initialised, and the static problem domain encoding must be loaded.

.. code-block:: python

    ctrl = Control(unifier=[Driver,Item,Assignment])
    ctrl.load("quickstart.lp")

The :class:`~clorm.clingo.Control` object controls the operations of the ASP
solver. When the solver runs it generates *models*. These models constitute the
solutions to the problem. Facts within a model are encoded as ``clingo.Symbol``
objects. The :class:`unifier<clorm.clingo.Control>` argument is important as it
defines which symbols are turned into :class:`~clorm.Predicate` instances.

For every symbol fact in the model, Clorm will successively attempt to *unify*
(or match) the symbol against the predicates in the unifier list. When a match
is found the symbol is used to define an instance of the matching predicate. Any
symbol that does not unify against any of the predicates is ignored.

Once the control object is created and the unifier predicates specified the
static ASP program is loaded.

Next we generate a problem instance by generating a lists of ``Driver`` and
``Item`` objects. These items are added to a :class:`~clorm.FactBase` object,
which is a specialised set-like container for storing facts (i.e., predicate
instances).

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
<https://potassco.org/clingo/python-api/5.7/clingo/control.html#clingo.control.Control.solve>`_).
For this example we run it using a callback function, which is called each time a
model is found.

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
down through the :class:`~clorm.clingo.Control` object constructor. As mentioned
earlier, any facts that fail to unify are ignored. In this case it ignores the
``working_driver/1`` instances. The unified facts are stored and returned in a
:class:`~clorm.FactBase` object.

Querying
--------

The final part of our Python program involves querying the solution to print out
the relevant facts. In particular it would be useful to display all drivers and
any jobs they have.  To do this we call the factbase's
:py:meth:`FactBase.query()<clorm.FactBase.query>` member function that
returns a suitable :class:`~clorm.Query` object.

The query is defined in terms of a chaining over the member functions of a
:class:`~clorm.Query` object. Each function call returns a modified copy of the
:class:`~clorm.Query` object. This technique will be familiar to users of
Python ORM's such as SQLAlchemy or Peewee.

.. code-block:: python

    from clorm import ph1_

    query=solution.query(Assignment)\
                  .where(Assignment.driver == ph1_)\
                  .order_by(Assignment.time)


The above query defines a search over the ``Assignment`` predicate to match the
``driver`` field to a special placeholder object ``ph1_`` and to return the
assignments for that driver sorted by the delivery time. The value of ``ph1_``
will be provided when the query is executed.  Here the
:py:meth:`FactBase.query()<clorm.FactBase.query>` method mirrors a traditional
SQL ``FROM`` clause.

We can now loop over the known drivers and execute the query for each
driver. This is done by first *binding* the value of the placeholder ``ph1_`` to
a specific value and calling the :py:meth:`Query.all()<clorm.Query.all>`
method. This function returns a Python generator which is then used to execute
and iterate over the results.

.. code-block:: python

    for d in drivers:
        assignments = list(query.bind(d.name).all())
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))

Calling ``query.bind(d.name)`` first creates a new query with the placeholder
values assigned. Because ``d.name`` is the first parameter to the function call
it matches against the placeholder ``ph1_``. Clorm has four predefined
placeholders ``ph1_``,... , ``ph4_``, but more can be created using the ``ph_``
function.

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

Note, viewing the items for all drivers, including those drivers with no
assignments, could be done simply with a single SQL ``OUTER JOIN``
query. Unfortunately, the Clorm Query API doesn't have an equivalent of an
``OUTER JOIN``. While it can usually be simulated with a bit of extra Python
code, in this case it was simplest to execute a query for each
driver. Alternatively, if we were happy to only specify the drivers with
assignments then the problem could be formulated in terms of a query with a
grouping modifier.

.. code-block:: python

    query=solution.query(Assignment)\
                  .group_by(Assignment.driver)\
                  .order_by(Assignment.time)\
                  .select(Assignment.item,Assignment.time)

    for dname, grpit in query.all():
        print("Driver {} must deliver: ".format(dname))
        for item,time in grpit:
            print("\t Item {} at time {}".format(item, time))

Here the :py:meth:`Query.group_by()<clorm.Query.group_by>` method modifies the
query generator output to return pairs of objects; where the first element of
the pair consists of the elements specified by the grouping and the second
element is an iterator over the matching elements for that group (here further
ordered by delivery time). This is loosely analagous to how an SQL ``GROUP BY``
clause works. Similarly the :py:meth:`Query.order_by()<clorm.Query.order_by>`
function operates like an SQL ``ORDER BY`` clause.

It is also worth noting that the :py:meth:`Query.select()<clorm.Query.select>`
projection operator performs a similar function to an SQL ``SELECT`` clause to
modify the output. Here, instead of returning the assignment item itself, it
returns the two relevant parameter values.
