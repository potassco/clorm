Fact Bases and Querying
=======================

As well as offering a higher-level interface for mapping ASP facts to Python
objects, Clorm also provides facilities for dealing with collections of facts.
Whether they are the set of facts that make up the problem instance or,
alternatively, the facts that constitute the *model* of a problem, an ASP
application typically does not simply deal with individual facts in isolation.

A Container for Facts
---------------------

Clorm provides the ``FactBase`` as a container class for storing and querying
facts. ``FactBase`` behaves much like a normal Python container except that it
can only contain instances of Predicate (or it's sub-classes) and has
database-like query mechanism.

.. code-block:: python

   from clorm import *

   class Person(Predicate):
      id = ConstantField
      address = StringField

   class Pet(Predicate):
      owner = ConstantField
      petname = StringField

   dave = Person(id="dave", address="UNSW")
   morri = Person(id="morri", address="UNSW")
   dave_cat = Pet(owner="dave", petname="Frank")

   fb = FactBase([dave,morri,dave_cat])

   # The in and len operators work as expected
   assert dave in fb
   assert len(fb) == 3

The fact base can be populated at object construction time or later. Like a
Python ``set`` object a ``FactBase`` has an ``add`` member function for adding
facts. However, because it can only store ``Predicate`` instances the function
is able to be more flexible and has been overloaded to accept either a single
fact or a list of facts.

.. code-block:: python

   dave_dog = Pet(owner="dave", petname="Bob")
   morri_cat = Pet(onwer="morri", petname="Fido")
   morri_cat2 = Pet(onwer="morri", petname="Dusty")

   fb.add(dave_dog)
   fb.add([morri_cat, morri_cat2])

Indexing
^^^^^^^^

A typical ASP program has models that contain relatively small numbers of facts
(e.g., 10-100 facts). With such small numbers of facts, querying these facts
from a ``FactBase`` can often be done without regard to performance
considerations.

However, similarly to a traditional database, there can be cases where the
number of facts that need to be stored can relatively large. In such cases
querying these facts from a ``FactBase`` can present a performance bottleneck.

In order to alleviate this problem a ``FactBase`` can be defined with indexes
for specific fields. Extending the above example:

.. code-block:: python

   fb1 = FactBase([dave,morri,dave_cat],indexes=[Person.id, Pet.owner])

Here the fact base ``fb1`` maintains an index on the ``id`` field of the
``Person`` predicate, as well as the ``owner`` field for the ``Pet`` predicate.

In this case any querying on the ``Person.id`` or ``Pet.owner`` fields will use
the index and not have to examine every fact of that type.

Note, as with database indexing, specifying indexes should be done sparingly to
ensure the right balance of the cost of maintaining an index against the cost of
querying the fact base.


Querying
--------

An important motivation for providing a specialised container class for storing
facts, as opposed to simply using a Python ``list`` or ``set`` object, is to
support a rich mechanism for querying the contents of a fact base.

When an ASP model is returned by the solver the application developer needs to
process the model in order to extract the relevant facts. The simplest mechanism
to do this is to simply loop through the facts in the model. This loop will
typically contain a number of conditional statements to determine what action to
take for the given fact; and to store it if some sort of matching needs to take
place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. ``FactBase`` is intended to
alleviate this problem by offering a database-like query mechanism for
extracting facts from a model.

Simple Queries
^^^^^^^^^^^^^^

Assuming the definitions and the ``fb`` instance above, a ``FactBase`` object
can create ``Select`` query objects:

.. code-block:: python

       query1=facts.select(Person).where(Person.id == "dave")
       query2=facts.select(Pet).where(Pet.owner == "dave")

A query object needs to be executed in order to return the results. There are
three member functions to execute a query: ``get()``, ``get_unique()``, and
``count()``. ``get()`` returns a list of results, while ``get_unique()`` returns
exactly one result and will raise a ``ValueError`` if this is not the
case. Finally, ``count()`` returns the number of matching entries.

.. code-block:: python

       dave = query1.get_unique()
       for pet in query2.get():
           assert pet.owner == "dave"

Indexing
^^^^^^^^

Querying can be a relatively expensive process as it has to potentially to
examine every fact in the ``FactBase``. However, if you know that you will be
mostly searching for values that match a particular field (or set of fields)
then it is useful to define an index on that field (or fields) when the
``FactBase`` object is instantiated:

.. code-block:: python

   fb = FactBase([dave,morri,dave_cat], index=[Pet.owner])

   query=facts.select(Pet).where(Pet.owner == ph1_)


Queries with Parameters
^^^^^^^^^^^^^^^^^^^^^^^

To allow more flexible queries Clorm introduces placeholders as a means of
parameterising queries. Placeholders are named ``ph1_`` to ``ph4_`` and
correspond to the position of the parameter in the ``get()``, ``get_unique()``,
or ``count()`` function calls.

.. code-block:: python

       query1=facts.select(Person)
       query2=facts.select(Pet).where(Pet.owner == ph1_)

       for person in query1.get():
          print("Pets owned by: {}".format(person.id))
          for pet in query2.get(person.owner):
	      print("\t pet named {}".format(pet.petname))


Additional placeholders can be defined using the ``ph_`` function:
``ph_(5)`` will create a placeholder for the 5th positional argument.

Clorm also supports **named placeholders**, which may be preferable if there are
a larger number of parameters. A named placeholder is created using the ``ph_``
function with a non-numeric first parameter, and are referenced in the query
execution using keyword function parameters. An advantange of named
placeholders is that they allow for a default value to be set.

.. code-block:: python

   query2=facts.select(Pet).where(Pet.owner == ph_("owner", "dave"))

   # Find pets owned by "morri"
   for pet in query2.get(owner="morri"):
       print("\t pet named {}".format(pet.petname))

   # Find pets owned by "dave" (using the default value)
   for pet in query2.get():
       print("\t pet named {}".format(pet.petname))


Ordering Queries
^^^^^^^^^^^^^^^^

Queries allow for ordering the result by setting order options using the
``order_by`` member function. Multiple fields can be listed as well as being
able to specify ascending or descending sort order (with ascending order being
the default).

.. code-block:: python

       query2=facts.select(Pet).order_by(Pet.owner, Pet.petname)

The above will list all pets, first sorted by the owner's name and then sorted in
by the pet's name.

In order to specify descending order you need to use the ``desc`` function. So
for the above example to sort by the pet's name in descending order:

.. code-block:: python

	from clorm import desc

	query2=facts.select(Pet).order_by(Pet.owner, desc(Pet.petname))


Querying by Positional Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As well as querying by field name (or sub-field) it is also possible to query by
the field position.

.. code-block:: python

       query2=facts.select(Pet).where(Pet[0] == "dave").order_by(Pet[1])

However, the warning from the previous section still holds; to use positional
arguments sparingly and only in cases where the order of elements will not
change as the ASP code evolves.

Querying the Predicate Itself
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While it is possible to query fields (and sub-fields) of a predicate using the
intutive "." syntax (eg., ``Pet.owner == ph1_``), unfortunately, it is not
possible to provide this intuitive syntax for querying the predicate itself
(e.g., a query of ``Pet < ph1_`` will fail).

Instead a helper function ``path()`` is provided for this special case.

.. code-block:: python

       from clorm import path

       p1=Pet(owner="dave", petname="bob")
       query3=facts.select(Pet).where(path(Pet) <= p1)

Here the query will return all pet objects that are less than ``p1``, based on
the ordering of the underlying Clingo Symbol objects. Note, querying by the
predicate itself is a boundary case and it is not necessarily clear when this
feature is required. For example, when testing for equality it is usually
simpler to not use the query mechanism and instead to use the basic Python set
inclusion operation.

.. code-block:: python

   assert p1 not in facts

.. note::

   The technical reason for not providing the intuitive syntax is that it would
   require overloading the boolean comparison operators for the
   NonLogicalSymbol's metaclass. However, this would likely cause unexpected
   behaviour when using the NonLogicalSymbol class in a variety of
   contexts. Because of this it was thought better to provide a special syntax
   for this boundary case.


Complex Query Expressions and Indexing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the simple case where the ``Select`` query object contains a ``where`` clause
that corresponds to a field that is indexed then Clorm is able to use this index
to make query execution more efficient.

However, a ``where`` clause can consist of more than one clause and these are
treated as a conjunction. Its is also possible to construct more complex clauses
using Clorm supplied ``and_``, ``or_``, and ``not_`` constructs.

.. code-block:: python

       query1=facts.select(Person).where(or_(Person.id == "dave", Person.address == "UNSW"))

Here when ``query1`` is execute it will return any person who is either
``"dave""`` or based at ``"UNSW"``.

Functors and Lambdas
^^^^^^^^^^^^^^^^^^^^

Finally, it should be noted that the specification of a select ``where`` clause
is in reality a mechanism for generating functors. Therefore it is possible to
simply provide a function or lambda statement instead.

For example to find a specific owner from the set of pet facts, the following
two queries will generate the same results.


.. code-block:: python

       query1=facts.select(Pet).where(Pet.owner == ph1_)
       query2=facts.select(Pet).where(lambda x, o: x.owner == o))

       results1 = list(query1.get("dave"))
       results2 = list(query2.get("dave"))

However, while both these queries do generate the same result they are not
equivalent in behaviour. In particular, the Clorm generated functor has a
structure that the system is able to analyse and can therefore potentially use
indexing to improve query efficiency. In contrast, there is no mechanism to
analyse the internal make up of a lambda or function. Consequently in these
latter cases the query would have to examine every fact (of the appropriate
type) in the fact base and test the function against that fact. Hence it is
usually preferable to use the Clorm generated clauses where possible.


Importing Raw Clingo Symbols and FactBaseBuilder
------------------------------------------------

A ``FactBase`` container can only contain predicate objects. However, the Clingo
reasoner deals in ``Clingo.Symbol`` objects.  By using the ``clorm.clingo``
module the need to deal with the underlying symbol objects is eliminated for
many use-cases. However, there may still be more advanced cases where it is
useful to deal with the raw symbol objects. Clorm provides functions and classes
to simplify this interaction.

A ``unify`` function is provided that takes two parameters; a list of predicate
classes as *unifiers* and a list of raw clingo symbols. It then tries to unify
the list of raw symbols with the list of predicates. This function returns a
list of facts that represent the unification of the symbols with the first
matching predicate. If a symbol was not able to unify with any predicate then it
is ignored.

.. code-block:: python

   from clingo import *
   from clorm import *

   class Person(Predicate):
      id = ConstantField
      address = StringField

   dave = Person(id="dave", address="UNSW")
   dave_raw = Function("person", [Function("dave",[]),String("UNSW")])
   facts = unify([Person], [dave_raw])
   assert facts == [dave]

.. note:: In general it is a good idea to avoid defining multiple predicate
   definitions that can unify to the same symbol. However, if a symbol can unify
   with multiple predicate definitions then the ``unify`` function will match to
   only the first predicate definition in the list of predicates.

The ``FactBaseBuilder`` provides a helper class to simplify the process of
turning raw symbols into facts stored within a ``FactBase``.


It also provides integrated features to make it easier to define field
indexes.

Because defining queries is a potentially common requirement the field
definition within the predicate can include the option ``index=True`` which will
be used by the ``FactBaseBuilder``.

So the earlier definition can be modified:

.. code-block:: python

   class Pet(Predicate):
      owner = ConstantField(index=True)
      petname = StringField()

``FactBaseBuilder`` provides a decorator function that can be used to register
the class and index option with the builder.

.. code-block:: python

   from clorm import *

   fbb = FactBaseBuilder()

   @fbb.register
   class Person(Predicate):
      id = ConstantField()
      address = StringField()

   @fbb.register
   class Pet(Predicate):
      owner = ConstantField(index=True)
      petname = StringField()

   dave_raw = Function("person", [Function("dave",[]),String("UNSW")])
   fb1 = fbb.new(symbols=[dave_raw])


Once a ``FactBaseBuilder`` object has registered a number of predicates then the
``FactBaseBuilder.new()`` member function can be used to create a ``FactBase``
object containing the facts that were generated by unifying the
``Clingo.Symbol`` objects against the registered predicates. The generated
``FactBase`` will also have the appropriate indexes specified by the
registration of the predicates.

This function has two other useful features. Firtly, the option
``raise_on_empty=True`` will throw an error if no clingo symbols unify with the
registered predicates. While there are legitimate cases where a symbol doesn't
unify with the builder there are also many cases where this indicates an error
in the definition of the predicates or in the ASP program itself.

The final option is the ``delayed_init=True`` option that allow for a delayed
initialisation of the ``FactBase``. What this means is that the symbols are only
processed (i.e., they are not unified agaist the predicates to generate facts)
when the ``FactBase`` object is actually used.

This is useful because there are cases where a fact base object is never
actually used and is simply discarded. In particular this can happen when the
ASP solver generates models as part of the ``on_model()`` callback function. If
applications only cares about an optimal model or there is a timeout being
applied then only the last model generated will actually be processed and all
the earlier models may be discarded (see :ref:`api_clingo_integration`).










