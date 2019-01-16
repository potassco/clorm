Clingo Solver Integration
=========================

In the following we outline the facilities that CLORM provides for using
predicates and fact bases with the Clingo ASP solver.

CLORM provides the ``Predicate`` and ``FactBase`` classes as a means of mapping
raw Clingo symbols to more intuitive Python objects. However, ultimately,
getting facts into and out of the Clingo ASP reasoner using the Clingo API
requires dealing with raw symbols.

To simplify this process for the developer CLORM provides a number of functions
as well as providing more tightly integrated wrapper classes.

The two most important Clingo classes that an app developer will like deal with are:

* ``Control``. This is the heart of the reasoner and determines when and how the
  reasoner is called.
* ``Model``. This is the class that contains the facts (and other meta-data)
  associated with an ASP model.

Integration Functions
---------------------

CLORM provides functions to help with interacting with ``Control`` and ``Model``
objects. Each of these functions takes the appropriate Clingo object as a first
parameter while the second parameter contains any fact related objects.

* ``control_add_facts(ctrl, facts)``.  This function adds facts to an ASP
  program. The facts can be either a list of predicate objects or a fact
  base. Because the initial facts in an ASP program will affect the grounding,
  new facts should only be added to the program **before** grounding.

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

Wrapper Classes
---------------

While the above functions can be used to interact with the Clingo API, it is
possible to integrate more deeply with the Clingo API by using a set of wrapper
classes around the important Clingo classes.

These classes can be used to instead of the Clingo ``Control``, ``Model``, and
``SolveHandle`` classes and provide a full-integration with CLORM. The easiest
way to use these classes is to `monkey patches
<https://en.wikipedia.org/wiki/Monkey_patch>`_ the clingo classes.

.. code-block:: python

   from clorm import monkey; monkey.patch()
   from clingo import Control

The wrapped classes contains new or modified member functions that calls the
integration functions outlined above. All other functions are simply passed
through to the underlying clingo object. In particular:

``Model.facts()`` simply calls the ``model_facts()`` function and
``Model.contains()`` calls the ``model_contains()`` function.

Similarly with ``Control.add_facts()``, ``Control.assign_external()``,
``Control.release_external()``, Finally, the ``Control.solve()`` function is
also modified slighly, so that the ``assumptions`` parameter can take a fact
base or list of facts, the ``on_model`` callback calls a function that can take
a wrapped ``Model`` object and if the ``yield_`` parameter is called returns a
wrapped ``SolveHandle`` object that wraps the original Clingo ``SolveHandle``
object.
