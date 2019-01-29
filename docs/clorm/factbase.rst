Fact Bases and Querying
=======================


As well as offering a higher-level interface for mapping ASP facts to Python
objects, ClORM also provides facilities for dealing with collections of facts.
Whether they are the set of facts that make up the problem instance or,
alternatively, the facts that constitute the *model* of a problem, an ASP
application typically does not simply deal with individual facts in isolation.

A Container for Facts
---------------------

ClORM provides the ``FactBase`` as a container class for storing and querying
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
examine the integration of ClORM with the ASP solver and dealing with ASP
models.

A Helper for Defining Containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While defining a ``FactBase`` is not a particularly onerous task, nevertheless
it does leave open some room for mistakes; for example when a Predicate
definition is modified and the modification is not reflected in the fact base
definitions.


To help with this ClORM provides a ``FactBaseHelper`` class that instantiates a
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
to do this to loop through the facts in the model. The loop will then typically
contains a number of conditional statements to determine what action to take for
the given fact; and to store it if some sort of matching needs to take place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. ClORM's ``FactBase`` is
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

A query object needs to be executed in order to return the results. There two
functions ``get()`` and ``get_unique()``. The ``get_unique()`` function expects
exactly one results and will raise a ``ValueError`` if this is not the case.

.. code-block:: python

       dave = query1.get_unique()
       for pet in query2.get():
           assert pet.owner == "dave"

Queries with Parameters
^^^^^^^^^^^^^^^^^^^^^^^

To provide for more flexible queries ClORM introduces placeholders in order to
parameterise queries. Placeholders are named ``ph1_`` to ``ph4_`` and correspond
to the position of the parameter in the ``get()`` or ``get_unique()`` function
calls.

A placeholder can be used in order to query each person and the pets that they own.

.. code-block:: python

       query1=facts.select(Person).where()
       query2=facts.select(Pet).where(Pet.owner == "dave")

       for person in query1.get():
          print("Pets owned by: {}".format(person.person))
          for pet in query2.get(person.owner):
	      print("\t pet named {}".format(pet.petname))


Complex Queries and Indexing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the simple case where the ``Select`` query object contains a ``where`` clause
that corresponds to a field that is indexed then ClORM is able to use this index
to make query execution efficient.

A ``where`` clause can consist of more the one clause and these are treated as a
conjunction. Its is also possible to construct more complex clauses using ClORM
supplied ``and_``, ``or_``, and ``not_`` constructs.

.. code-block:: python

       query1=facts.select(Person).where(or_(Person.person == "dave", Person.address == "UNSW"))

Here when ``query1`` is execute it will return any person who is either
``"dave""`` or or based at ``"UNSW"``.

Functors and Lambdas
^^^^^^^^^^^^^^^^^^^^

Finally, it should be noted that the specification of a select ``where`` clause
is in reality a mechanism for generating functors. Therefore it is possible to
simply provide a function or lambda statement instead.

For example to find a specific person the following two queries will generate
the same results.


.. code-block:: python

       query1=facts.select(Pet).where(Pet.owner == ph1_)
       query2=facts.select(Pet).where(lambda x, o: return x.owner == o))

       results1 = list(query1.get("dave"))
       results2 = list(query2.get("dave"))

However, while both these queries do generate the same result they are not
equivalent in behaviour. In particular, the ClORM generated functor has a
structure that the system is able to analyse and can therefore potentially use
indexing to improve query efficiency.

However, there is no mechanism to analyse the internal make up of a lambda or
function. Consequently in these cases the query would have to examine every fact
in the fact base of the given type and test the function against that
fact. Hence it is usually preferable to use the ClORM generated where clauses
possible.


