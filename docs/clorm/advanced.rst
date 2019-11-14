Advanced Features
=================

This chapter provides details of more advanced Clorm features. Clorm implements
a number of functions and classes to provide its abstraction over the raw Clingo
symbol objects. There may be more advanced use-cases where it is useful to have
access to these features. Or at the very least it may help to provide a better
understanding of the internal operations of Clorm.

Introspection of Predicate Definitions
--------------------------------------

A number of properties of a ``Predicate`` or ``ComplexTerm`` definition can be
accessed through the ``meta`` property of the class. To highlight these features
we assume the following definitions:

.. code-block:: python

   from clorm import Predicate, ComplexTerm, ConstantField, StringField

   class Address(ComplexTerm):
	street = StringField
	city = StringField(index=true)

   class Person(Predicate):
      name = StringField(index=true)
      address = Address.Field

Firstly the name and arities of the complex term and predicate can be examined:

.. code-block:: python

   assert Address.meta.name == "address"
   assert Address.meta.arity == 2
   assert Person.meta.name == "person"
   assert Person.meta.arity == 2

The fields, and sub-fields, of a predicate that are specified as being indexed
are also available:

.. code-block:: python

   assert set(Person.meta.indexes) == set([Person.name, Address.city])

It is possible to introspect the field names of a predicate:

.. code-block:: python

   assert set(Person.meta.keys()) == set(["name","city"])


Raw Clingo and Clorm Facts
--------------------------

The Clingo reasoner deals in ``clingo.Symbol`` objects while Clorm facts provide
an intuitive abstraction on top of the underlying raw symbols.  Clorm and the
Clingo integration library ``clorm.clingo`` minimises the need to deal with
explicitly coverting between the two.

However, there may still be use-cases where it is useful to deal explicitly with
the underlying raw clingo symbol objects. For example, if the user choses not to
use the ``clorm.clingo`` integration module but instead to use the main
``clingo`` module.

Unification
^^^^^^^^^^^

In logical terms, unification involves transforming one expression into another
through term substitution. We co-op this terminology for the process of
transforming ``Clingo.Symbol`` objects into Clorm facts. This unification
process is integral to using Clorm since it is the main process by which the
symbols within a Clingo model are transformed into Clorm facts.

A ``unify`` function is provided that takes two parameters; a *unifier* and a
list of raw clingo symbols. It then tries to unify the list of raw symbols with
the predicates in the unifier. The function then returns a ``FactBase``
containing the facts that resulted from the unification of the symbols with the
first matching predicate. If a symbol was not able to unify with any predicate
it is ignored.

.. code-block:: python

   from clingo import Function, String
   from clorm import Predicate, StringField, unify

   class Person(Predicate):
      name = StringField(index=True)
      address = StringField

   good_raw = Function("person", [String("Dave"),String("UNSW")])
   bad_raw = Function("nonperson", [])
   fb = unify([Person], [bad_raw, good_raw])
   assert list(fb) == [Person(name="Dave", address="UNSW")]
   assert len(fb.indexes) == 1


.. note:: In general it is a good idea to avoid defining multiple predicate
   definitions that can unify to the same symbol. However, if a symbol can unify
   with multiple predicate definitions then the ``unify`` function will match
   only the first predicate definition in the list of predicates.

By default, the fact base object returned by the ``unify`` function will be
initialised with any indexed fields as specified by the matching predicate
declaration.

To get more fined grained behaviour, such as controlling which fields are
indexed, the user can also use a ``SymbolPredicateUnfier`` helper function.
This class also provides a decorator function that can be used to register the
class and any indexes at the point where the predicate is defined. The symbol
predicate unifer can then be passed to the unify function instead of a list of
predicates.

.. code-block:: python

   from clingo import Function, String
   from clorm import Predicate, StringField, unify

   spu = SymbolPredicateUnifier(supress_auto_index=True)

   @spu.register
   class Person(Predicate):
      name = StringField(index=True)
      address = StringField

   class Person(Predicate):
      id = ConstantField()
      address = StringField()

   good_raw = Function("person", [String("Dave"),String("UNSW")])
   bad_raw = Function("nonperson", [])
   fb = spu.unify([bad_raw, good_raw])
   assert list(fb) == [Person(name="Dave", address="UNSW")]
   assert len(fb.indexes) == 0

This function has two other useful features. Firtly, the option
``raise_on_empty=True`` will throw an error if no clingo symbols unify with the
registered predicates, which can be useful for debugging purposes.

The final option is the ``delayed_init=True`` option that allow for a delayed
initialisation of the ``FactBase``. What this means is that the symbols are only
processed (i.e., they are not unified agaist the predicates to generate facts)
when the ``FactBase`` object is actually used.

This is also useful because there are cases where a fact base object is never
actually used and is simply discarded. In particular this can happen when the
ASP solver generates models as part of the ``on_model()`` callback function. If
applications only cares about an optimal model or there is a timeout being
applied then only the last model generated will actually be processed and all
the earlier models may be discarded (see :ref:`api_clingo_integration`).










