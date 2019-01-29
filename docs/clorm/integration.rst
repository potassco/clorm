Clingo Solver Integration
=========================

So for we have shown how to define predicates and fact bases, and perform
queries over fact bases. However, we have not discussed in detail how these
objects are integrated and interact with the Clingo ASP solver.

As detailed in :ref:`raw-symbol-label`, at its most basic level a Clingo
``Symbol`` object can be extracted from a ClORM ``Predicate`` object using the
``raw`` property and conversely a ``Symbol`` object can be passed as the ``raw``
parameter in the ``Predicate`` constructor.

Wrapper classes
---------------

While extracting ``Symbol`` objects from ``Predicates`` is sufficient to use
ClORM with the Clingo solver it is still not a particularly clean interface and
can result in unnecessary boilerplate code. To avoid this the ``clorm.clingo``
module fully integrates ClORM objects into the Clingo API. It does this by
providing wrapper classes around the key Clingo classes:

* ``Control`` is the heart of the interface to the reasoner and determines when
  and how the reasoner is called. The ``Control.solve`` function starts the
  solving process. Depending on the parameters it can operate in different
  modes; for example it can use a callback that is called with ``Model`` ojects
  and can also return a ``SolveHandle``.

* ``Model`` is the class that contains the facts (and other meta-data)
  associated with an ASP model. This class should not be instantiated explicitly
  and is instead passed within the ``Control.solve`` callback.

* ``SolveHandle`` provides a mechanism to iterate over the models. Similarly to
  the ``Model`` class it should not be instantiated explicitly and is instead
  returned from the ``Control.solve`` function.

Clingo ``Control``
^^^^^^^^^^^^^^^^^^

``Control`` is the main object for interacting with the ASP grounder and solver
and provides a rich set of features. It allows an ASP program that is stored in
a file to be loaded. It can then be grounded and solved and the generated models
returned. It also allows for incremental solving, where a ground program can be
extended and solved repeatedly, as well as both synchronous and asynchronous
solving modes. These featuers are documented in the `Clingo Control API
<https://potassco.org/clingo/python-api/current/clingo.html#Control>`_ so we
only highlight the changes that ClORM introduces.

ClORM add, or overloads, the following member functions:

* ``__init__()``. ClORM adds an optional ``control_`` parameter that is mutually
  exclusive with all other parameters. This allows a ``clingo.Control`` object
  to be passed to the wrapper and is a mechanism to allow ClORM to be used even
  when Python is embedded within Clingo. See the example
  ``embedded_quickstart.lp`` for a more detailed example, but the basics are
  that a Control object is passed to the embedded ``main`` function which is
  then wrapped in ``clorm.clingo.Control``:

.. code-block:: python

    #script(python).

    import clorm.clingo

    def main(ctrl_):
        ctrl = clorm.clingo.Control(control_=ctrl_)

	# ...
    #end.


* ``add_facts(facts)``.  This function adds facts to an ASP program. The facts
  can be either a list of predicate objects or a fact base. Because the initial
  facts in an ASP program will affect the grounding, new facts should only be
  added to the program **before** grounding.

.. code-block:: python

    from clorm.clingo import Control

    ctrl = Control()
    ctrl.load("quickstart.lp")
    ctrl.add_facts(db)
    ctrl.ground([("base",[])])

* ``solve()``. This function provides a rich set of options for calling the
  solver and returning the results. These parameters are documented in the
  Clingo API. ClORM modifies this interface in three ways:

  - ``assumptions`` parameter. As well as taking a list of ``clingo.Symbol``
    objects, ClORM also allows the assumptions to be specified as a list of
    ``clorm.Predicate`` objects or a single ``clorm.FactBase`` object.
  - ``on_model`` callback parameter. ClORM modifies this interface so that a
    ``clorm.clingo.Model`` is pass to the callback function.
  - If the parameter ``yield_=True`` is specified then the return value of the
    function is a ``clorm.clingo.SolveHandle`` object. This object iterates over
    ``clorm.clingo.Model`` objects.

* ``assign_external()`` is modified so that the ``fact`` parameter can take a
  ``clorm.Predicate`` object.

* ``release_external()`` is modified so that the ``fact`` parameter can take a
  ``clorm.Predicate`` object.

Clingo ``Model``
^^^^^^^^^^^^^^^^

The `Clingo Model
<https://potassco.org/clingo/python-api/current/clingo.html#Model>`_ object
encapsulates an ASP model and the associated meta-data. It is passed to the
``Clingo.solve(on_model=on_model)`` callback. ClORM wraps the ``Model`` class to
provide a mechanism to extract ClORM facts from the model. The added and
modified functions are:

* ``facts(self, factbase, atoms=False, terms=False, shown=False)``. This
  function requires a ``FactBase`` sub-class to be specified as the first
  argument, as well as allowing for the same options as the ``Model.symbols()``
  function. It creates a fact base object from the passed class and populates it
  with the selected symbols that are able to unify with the class.

* ``contains(self,fact)``. Extends ``clingo.Model.contains`` to allow for a
  clorm facts as well as a clingo symbols.

Clingo ``SolveHandle``
^^^^^^^^^^^^^^^^^^^^^^

The `Clingo SolveHandle
<https://potassco.org/clingo/python-api/current/clingo.html#Model>`_ object
provides a mechanism for iterating over the models when the ``yield_=True``
options is specified to the ``Control.solve`` function. The various iterator
functions are modified by ClORM, but its operations should be transparent to the
user.

Monkey-patching
---------------

ClORM provides `monkey patching <https://en.wikipedia.org/wiki/Monkey_patch>`_
of the ``Control`` class so that ClORM can be integrated into an existing code
base with minimal effort.

.. code-block:: python

   from clorm import monkey; monkey.patch()
   from clingo import Control

.. note:: In general monkey patching should be avoided where possible.

