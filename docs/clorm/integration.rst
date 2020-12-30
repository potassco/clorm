Clingo Solver Integration
=========================

So for we have shown how to define predicates and fact bases, and perform
queries over fact bases. However, we have not discussed in detail how these
objects are integrated and interact with the Clingo ASP solver.

As detailed in :ref:`raw-symbol-label`, at its most basic level a Clingo
``Symbol`` object can be extracted from a Clorm ``Predicate`` object using the
``raw`` property and conversely a ``Symbol`` object can be passed as the ``raw``
parameter in the ``Predicate`` constructor.

Wrapper classes
---------------

While extracting ``Symbol`` objects from ``Predicates`` is sufficient to use
Clorm with the Clingo solver it is still not a particularly clean interface and
can result in unnecessary boilerplate code. To avoid this the ``clorm.clingo``
module fully integrates Clorm objects into the Clingo API. It does this by
providing wrapper classes around the key Clingo classes:

* ``Control`` is the heart of the interface to the reasoner and determines when
  and how the reasoner is called. The ``Control.solve()`` function starts the
  solving process. Depending on the parameters it can operate in different
  modes; for example it can use a callback that is called with ``Model`` ojects
  and can also return a ``SolveHandle``.

* ``Model`` is the class that contains the facts (and other meta-data)
  associated with an ASP model. This class should not be instantiated explicitly
  and is instead passed within the ``Control.solve`` callback.

* ``SolveHandle`` provides a mechanism to iterate over the models. Similarly to
  the ``Model`` class it should not be instantiated explicitly and is instead
  returned from the ``Control.solve()`` function.

``Control``
^^^^^^^^^^^

``Control`` is the main object for interacting with the ASP grounder and solver
and provides a rich set of features. It allows an ASP program that is stored in
a file to be loaded. It can then be grounded and solved and the generated models
returned. It also allows for incremental solving, where a ground program can be
extended and solved repeatedly, as well as both synchronous and asynchronous
solving modes. These featuers are documented in the `Clingo Control API
<https://potassco.org/clingo/python-api/current/#clingo.Control>`_ so we
only highlight the changes that Clorm introduces.

Clorm adds some new member functions as well as overloading some existing
functions:

* ``__init__()``. Clorm adds an optional ``unifier`` parameter for specifying a
  default list of ``Predicate`` sub-classes (or a single
  ``SymbolPredicateUnifier`` object). This parameter is passed to any generated
  ``Model`` objects and is used during the unification process of converting raw
  symbols to Clorm facts. A second parameter ``control_`` is introduced. This
  parameter is mutually exclusive with the standard parameters for
  ``clingo.Control``. The ``control_`` parameter allows an existing
  ``clingo.Control`` object to be passed to the wrapper and is a mechanism to
  allow Clorm to be used even when Python is embedded within Clingo. See the
  example ``embedded_quickstart.lp`` for more details, but the basics are that a
  Control object is passed to the embedded ``main`` function which is then
  wrapped in ``clorm.clingo.Control``:

* ``unifier``. A property to get and set the unifier even after the
  ``clorm.clingo.Control`` object has been instantiated.

.. code-block:: python

    #script(python).

    import clorm.clingo

    def main(ctrl_):
        ctrl = clorm.clingo.Control(control_=ctrl_)

	# ...
    #end.


* ``add_facts(facts)``.  A new function that adds facts to an ASP program. The
  input can be any collection of facts (such as a ``list``, ``set``, or
  ``clorm.FactBase``). A fact can be either a ``clorm.Predicate`` or
  ``clingo.Symbol`` object. Note however that a ``clorm.FactBase`` can only
  contain ``clorm.Predicate`` instances.  **Warning**: because the initial facts in
  an ASP program will affect the grounding, new facts should only be added to
  the program **before** grounding.

.. code-block:: python

    from clorm.clingo import Control

    ctrl = Control()
    ctrl.load("quickstart.lp")
    ctrl.add_facts(db)
    ctrl.ground([("base",[])])

* ``solve()``. This function provides a rich set of options for calling the
  solver and returning the results. These parameters are documented in the
  Clingo API. Clorm modifies this interface in three ways:

  - ``assumptions`` parameter. This parameter restricts the returned models to
    only those satisfying the given assumptions. This parameter must consist of
    a list of argument-boolean pairs. As well as ``clingo.Symbol`` objects the
    argument element is extended to allow ``clorm.Predicate`` instances or a
    collection of clingo symbols or clorm predicates. This makes it flexible so
    that, for example, a ``FactBase`` object can be specified as being either
    True or False in the model.
  - ``on_model`` callback parameter. Clorm modifies this interface so that a
    ``clorm.clingo.Model`` is pass to the callback function.
  - If the parameter ``yield_=True`` is specified then the return value of the
    function is a ``clorm.clingo.SolveHandle`` object. This object iterates over
    ``clorm.clingo.Model`` objects.

* ``assign_external(external,truth)``. This function assigns a truth value to an
  external atom. This function has been overloaded so that the ``external``
  parameter can also take a ``clorm.Predicate`` instance or a collection of
  external atoms (e.g., a ``FactBase``), where the same truth value is assigned
  to all atoms in the collection.

* ``release_external(external)``. This function releases an external atom so
  that it is permanently false. The function is overloaded so that the
  ``external`` parameter can also take a ``clorm.Predicate`` instance or a
  collection of extenal atoms.

``Model``
^^^^^^^^^

The `Clingo Model
<https://potassco.org/clingo/python-api/current/#clingo.Model>`_ object
encapsulates an ASP model and the associated meta-data. It is passed to the
``Clingo.solve(on_model=on_model)`` callback. Clorm wraps the ``Model`` class to
provide a mechanism to extract Clorm facts from the model. The additional and
modified functions are:

* ``facts(self, unifier=None, atoms=False, terms=False, shown=False,
  raise_on_empty=True)``. returns a fact base object constructed from unifying
  against the raw Clingo symbols within the model.

  The ``unifier`` parameter takes a list of ``Predicate`` sub-classes or a
  single ``SymbolPredicateUnifier`` which defines the predicates to unify
  against. If no ``unifier`` parameter is provided then a ``unifier`` must have
  been passed to the ``clorm.clingo.Control`` object.

  The ``raise_on_empty`` parameter specifies that a ``ValueError`` will be
  raised if the returned fact base is empty. This can happen for two reasons:
  there were no selected elements in the model or there were elements from the
  model but none of them was able to unify with the fact base. This parameter is
  potentially useful for debugging purposes. While returning an empty fact base
  can be legimate outcomes for some applications, however in many cases this
  would indicate a problem; either in the ASP program or in the declaration of
  the predicates to unify against.

  Apart from the ``unifier`` and ``raise_on_empty`` parameters the remaining
  parameters are the same as for the ``Model.symbols()`` function.

* ``contains(self,fact)``. Extends ``clingo.Model.contains()`` to allow for a
  clorm facts as well as a clingo symbols.


``SolveHandle``
^^^^^^^^^^^^^^^

The `Clingo SolveHandle
<https://potassco.org/clingo/python-api/current/#clingo.Model>`_ object provides
a mechanism for iterating over the models when the ``yield_=True`` option is
specified in the ``Control.solve()`` function call. The various iterator functions
are modified by Clorm, but its operations should be transparent to the user.

Monkey-patching
---------------

Clorm provides `monkey patching <https://en.wikipedia.org/wiki/Monkey_patch>`_
of the ``Control`` class so that Clorm can be integrated into an existing code
base with minimal effort.

.. code-block:: python

   from clorm import monkey; monkey.patch()
   from clingo import Control

.. note:: In general monkey patching should be avoided where possible.

