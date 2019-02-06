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
facts. This class must be sub-classed, and each sub-class is distinguished by
the predicates that it can store and the terms for which it maintains an index.

.. code-block:: python

   from clorm import *

   class Person(Predicate):
      person = ConstantField()
      address = StringField()

   class Pet(Predicate):
      owner = ConstantField()
      petname = StringField()

   class AppDB(FactBase):
      predicates = [Person, Pet]
      indexes = [Pet.owner]


The fact base can be populated at object construction time or later.

.. code-block:: python

   dave = Person(person="dave", address="UNSW")
   morri = Person(person="morri", address="UNSW")
   dave_cat = Pet(owner="dave", petname="Frank")
   dave_dog = Pet(owner="dave", petname="Bob")
   morri_cat = Pet(onwer="morri", petname="Fido")

   facts = AppDB([dave, morri, dave_cat])
   facts.add([dave_dog, morri_cat])

It should be noted that adding a fact for a predicate type that has not been
registered for a given ``FactBase`` sub-class will result in the fact not being
added; which is also why the ``FactBase.add()`` function returns the number of
facts that have been added.

Importing Raw Clingo Symbols
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While a container can be populated with existing predicate objects, it can also
be used a generate predicate objects from the raw ``Clingo.Symbol`` objects by
passing a named parameter ``symbols`` to the constructor.

.. code-block:: python

   from clingo import *

   dave_raw = Function("person", [Function("dave",[]),String("UNSW")])
   facts = AppDB(symbols=[dave_raw])

Here the ``AppDB`` object tries to unify each raw symbol with its internal list
of predicates and creates a matching object for the first predicate that it
unifies with. If there are no unifying predicates then the symbol is ignored.

.. note:: Since a raw Clingo symbol is mapped to the first predicate that it
   unifies with, the order that the predicates are defined can change the
   behaviour of the fact base. Therefore, in general it is a good idea to avoid
   defining multiple predicates that can unify with the same symbols.

A final feature of the ``FactBase`` constructor is that it implements a delayed
initialisation feature with the constructor option ``delayed_init=True``. With
this option the importing of a symbols list is delayed until the first access of
the object. The usefulness of this option will be discussed later when we
examine the integration of Clorm with the ASP solver and dealing with ASP
models.

A Helper for Defining Containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While defining a ``FactBase`` is not a particularly onerous task, nevertheless
it does leave open some room for mistakes; for example when a Predicate
definition is modified and the modification is not reflected in the fact base
definitions.


To help with this Clorm provides a ``FactBaseHelper`` class that instantiates a
decorator that can be used to associate a predicate with a helper object.

.. code-block:: python

   from clorm import *

   fbh1  = FactBaseHelper()
   fbh2  = FactBaseHelper()

   @fbh1.register
   @fbh2.register
   class Person(Predicate):
      person = ConstantField()
      address = StringField()

   @fbh1.register
   class Pet(Predicate):
      owner = ConstantField(index=True)
      petname = StringField()

   AppDB1 = fbh1.create_class("AppDB1")
   AppDB2 = fbh2.create_class("AppDB2")

As was mentioned in the previous chapter the indexes are defined by specifying
``index=True`` for the appropriate predicate definition.

Querying
--------

Having outlined how to define a fact base we now turn to showing how to
efficiently access the data in a fact base. In fact, the primary motivation for
providing a specialised container class for storing facts, instead of simply
using a Python ``list`` or ``set`` oject, is to support a richer query
mechanism.

When an ASP model is returned by the solver the application developer needs to
process the model in order to extract the relevant facts. The simplest mechanism
to do this to loop through the facts in the model. This loop will typically
contain a number of conditional statements to determine what action to take for
the given fact; and to store it if some sort of matching needs to take place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. Clorm's ``FactBase`` is
intended to alleviate this problem by offering a database-like query mechanism
for extracting facts from a model.

Simple Queries
^^^^^^^^^^^^^^

Assuming the first definition of ``AppDB`` and the ``facts`` instance from
above, the class provides a function to generate appropriate ``Select`` query
objects. From a query object a ``where`` clause can also be set.

.. code-block:: python

       query1=facts.select(Person).where(Person.person == "dave")
       query2=facts.select(Pet).where(Pet.owner == "dave")

A query object needs to be executed in order to return the results. There are
two member functions to execute a query: ``get()`` and
``get_unique()``. ``get()`` returns a list of results, while ``get_unique()``
returns exactly one results and will raise a ``ValueError`` if there is not
exactly one result.

.. code-block:: python

       dave = query1.get_unique()
       for pet in query2.get():
           assert pet.owner == "dave"

Queries with Parameters
^^^^^^^^^^^^^^^^^^^^^^^

To provide for more flexible queries Clorm introduces placeholders in order to
parameterise queries. Placeholders are named ``ph1_`` to ``ph4_`` and correspond
to the position of the parameter in the ``get()`` or ``get_unique()`` function
calls.

.. code-block:: python

       query1=facts.select(Person)
       query2=facts.select(Pet).where(Pet.owner == ph1_)

       for person in query1.get():
          print("Pets owned by: {}".format(person.person))
          for pet in query2.get(person.owner):
	      print("\t pet named {}".format(pet.petname))


Additional placeholders can be defined using the ``ph_`` function:
``ph_(5)`` will create a placeholder for the 5th positional argument.

Clorm also supports **named placeholders**, which may be preferable if there are
a larger number of parameters. A named placeholder is created using the ``ph_``
function with a non-numeric first parameter, and are referenced in the query
execution using a keyword function parameter. Named placeholders also allow for
a default value.

.. code-block:: python

   query2=facts.select(Pet).where(Pet.owner == ph_("owner", "dave")

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

       query2=facts.select(Pet).order_by(Pet.owner, Pet.petname.desc())

The above will list all pets first sorted by the owner's name and then sorted in
descending order by the pet's name.

There is also a ``desc`` helper function for those that find the syntax more
intuitive. So the above could equally be written as:

.. code-block:: python

	from clorm import desc

	query2=facts.select(Pet).order_by(Pet.owner, desc(Pet.petname))


Complex Query Expressions and Indexing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the simple case where the ``Select`` query object contains a ``where`` clause
that corresponds to a field that is indexed then Clorm is able to use this index
to make query execution efficient.

However, a ``where`` clause can consist of more the one clause and these are
treated as a conjunction. Its is also possible to construct more complex clauses
using Clorm supplied ``and_``, ``or_``, and ``not_`` constructs.

.. code-block:: python

       query1=facts.select(Person).where(or_(Person.person == "dave", Person.address == "UNSW"))

Here when ``query1`` is execute it will return any person who is either
``"dave""`` or based at ``"UNSW"``.

Functors and Lambdas
^^^^^^^^^^^^^^^^^^^^

Finally, it should be noted that the specification of a select ``where`` clause
is in reality a mechanism for generating functors. Therefore it is possible to
simply provide a function or lambda statement instead.

For example to find a specific person the following two queries will generate
the same results.


.. code-block:: python

       query1=facts.select(Pet).where(Pet.owner == ph1_)
       query2=facts.select(Pet).where(lambda x, o: x.owner == o))

       results1 = list(query1.get("dave"))
       results2 = list(query2.get("dave"))

However, while both these queries do generate the same result they are not
equivalent in behaviour. In particular, the Clorm generated functor has a
structure that the system is able to analyse and can therefore potentially use
indexing to improve query efficiency.

However, there is no mechanism to analyse the internal make up of a lambda or
function. Consequently in these cases the query would have to examine every fact
in the fact base of the given type and test the function against that
fact. Hence it is usually preferable to use the Clorm generated clauses where
possible.


