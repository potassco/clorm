Clingo Solver Integration
=========================

.. attention:: This whole page needs more work.

So for we have shown how to define predicates and fact bases. However, we have
not discussed in detail how these objects are integrated and interact with the
Clingo ASP solver. In the following we outline the functions that turn ClORM
based-objects into Clingo symbol objects that can be used by Clingo. We also
discuss the seemless integration that ClORM provides for Clingo.

ClORM provides the ``Predicate`` and ``FactBase`` classes as a means of mapping
raw Clingo symbols to more intuitive Python objects. However, ultimately,
getting facts into and out of the Clingo ASP reasoner using the Clingo API
requires dealing with raw symbols.

As detailed in :ref:`raw-symbol-label` at its most basic level a Clingo
``Symbol`` object can be extracted from a ``Predicate`` object using the ``raw``
property and conversely a ``Symbol`` object can be passed as the ``raw``
parameter in the ``Predicate`` constructor. ClORM provides further functions
that build on this interface to provide tightly integrated interaction.

The two most important Clingo classes that an app developer will likely deal
with are:

* ``Control``. This is the heart of the interface to the reasoner and determines
  when and how the reasoner is called.
* ``Model``. This is the class that contains the facts (and other meta-data)
  associated with an ASP model.

In the following we only present the intuitive and tightly-integrated way of
interacting with Clingo.


Running Example
---------------

For the rest of this chapter we shall assume the following ASP program in a file
``birds.lp``:

.. code-block:: python

   #external Penguin(dave).

   Bird(X) :- Penguin(X).

as well as the following Python starter code:

.. code-block:: python

   from clorm import *

   fbh = FactBaseHelper()
   with fbh:
      class Penguin(Predicate):
         name = ConstantTermDefn()

      class Bird(Predicate):
         name = ConstantTermDefn()

   AppDB = fbh.create_class("AppDB")

   f1 = Penguin(name="dave")
   f2 = Penguin(name="tux")

   facts = AppDB([f1,f2])

Wrapper Classes
---------------

ClORM provides wrapper classes to be used instead of the Clingo ``Control``,
``Model``, and ``SolveHandle`` classes. These classes extend the relevant member
functions that interact with ``Symbol`` objects to also support the ClORM data
structures. The easiest way to use these classes is to `monkey patches
<https://en.wikipedia.org/wiki/Monkey_patch>`_ the clingo classes.

.. code-block:: python

   from clorm import monkey; monkey.patch()
   from clingo import Control


Clingo ``Control``
^^^^^^^^^^^^^^^^^^

The ``Control`` is the main object for interacting with the ASP grounder and
solver and provides a rich set of features. It allows an ASP program that is
stored in a file to be loaded. It can then be grounded and solved and the
generated models returned. It also allows for incremental solving, where a
ground program can be extended and solved repeatedly, as well as both
synchronous and asynchronous solving modes. These facilities are well documented
in the Clingo API <https://potassco.org/clingo/python-api/current/clingo.html>`_
so we only highlight some of the more important aspects connected with ClORM.


* ``control_add_facts(ctrl, facts)``.  This function adds facts to an ASP
  program. The facts can be either a list of predicate objects or a fact
  base. Because the initial facts in an ASP program will affect the grounding,
  new facts should only be added to the program **before** grounding.

.. code-block:: python

    from clingo import Control

    ctrl = Control()
    ctrl.load("starter.lp")
    ctrl.add_facts(db)
    ctrl.ground([("base",[])])



Other functions:

``Model.facts()`` simply calls the ``model_facts()`` function and
``Model.contains()`` calls the ``model_contains()`` function.

Similarly with ``Control.add_facts()``, ``Control.assign_external()``,
``Control.release_external()``, Finally, the ``Control.solve()`` function is
also modified slighly, so that the ``assumptions`` parameter can take a fact
base or list of facts, the ``on_model`` callback calls a function that can take
a wrapped ``Model`` object and if the ``yield_`` parameter is called returns a
wrapped ``SolveHandle`` object that wraps the original Clingo ``SolveHandle``
object.




Integration Functions
---------------------

.. attention:: This section is incomplete. It should be part of the API documentation.

ClORM provides functions for interacting with ``Control`` and ``Model``
objects. Each of these functions takes the appropriate Clingo object as a first
parameter while the second parameter contains any fact related objects.

* ``control_add_facts(ctrl, facts)``.  This function adds facts to an ASP
  program. The facts can be either a list of predicate objects or a fact
  base. Because the initial facts in an ASP program will affect the grounding,
  new facts should only be added to the program **before** grounding.

.. code-block:: python

    from clingo import Control

    ctrl = Control()
    ctrl.load("starter.lp")
    ctrl.add_facts(db)
    ctrl.ground([("base",[])])


* ``control_assign_external(ctrl, fact, truth)`` and
  ``control_release_external(ctrl, fact)``. These functions are simple wrappers
  around the ``Control.assign_external()`` and ``Control.release_external()``
  functions that simply transform a predicate object into a raw symbol before
  passing it on the the control object.

* ``model_contains(model,fact)``. A wrapper function around ``Model.contains()``
  to test is a fact is contained in the model.

* ``model_facts(model, factbase_subclass, atoms=False, terms=False,
  shown=False)``. This is a wrapper around the ``Model.symbols()`` function. The
  ``Model.symbols()`` function extracts the appropriate symbols (*atoms*,
  *terms*, or *shown*) from a ``Model`` object. ``model_facts()`` that turns
  these symbols into a set of unified predicates and stored in the appropriate
  ``FactBase`` sub-class.

