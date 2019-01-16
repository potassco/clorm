Sets of Facts
=============


As well as offering a higher-level interface for mapping ASP facts to Python
objects, CLORM also provides facilities for dealing with collections of facts.
Whether they are the set of facts that make up the problem instance or,
alternatively, the facts that constitute the *model* of a problem, an ASP
application typically does not simply deal with individual facts in isolation.

<<<<<<< HEAD
A Container for Facts
---------------------
=======
Defining a ``FactBase``
-----------------------
>>>>>>> c3470a6aafde0b666ffd488a9a20993c1f5945cc

CLORM provides the ``FactBase`` as a container class for storing and querying
facts. This class must be sub-classed, and each sub-class is distinguished by
the predicates that it can store and the predicate fields for which it maintains
an index.

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

   facts = AppDB([date, morri, dave_cat])
   facts.add([dave_dog, morri_cat])

It should be noted that adding a fact for a predicate type that has not been
registered for a given ``FactBase`` sub-class will result in the fact not being
added; which is also why the ``FactBase.add()`` function returns the number of
facts that have been added.

``FactBaseHelper``
^^^^^^^^^^^^^^^^^^

While defining a ``FactBase`` is not a particularly onerous task, nevertheless
it does leave open some room for mistakes; for example when a new Predicate is
defined but not aded to the fact base definition.

To help with this CLORM provides a ``FactBaseHelper`` class. It is especially
useful when these needs to be only one ``FactBase`` sub-class consisting of all
the difined predicates. In such a case the helper can be used as a context to
capture the predicate definitions and then the ``create_class()`` member
function used to dynamically define the corresponding class.

.. code-block:: python

   from clorm import *

   with FactBaseHelper() as fbh:
      class Person(Predicate):
         person = ConstantField()
         address = StringField()

      class Pet(Predicate):
         owner = ConstantField(index=True)
         petname = StringField()

   AppDB = fbh.create_class("AppDB")

As was mentioned in the previous chapter the indexes are defined by specifying
``index=True`` for the appropriate predicate definition, so that the above to
sets of versions will produce identical results.

The ``FactBaseHelper`` also supports a decorator mode that allows for slighly
more control.

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
contains a number of conditional statements to determine what action to take
with the current fact; and to store it if some sort of matching needs to take
place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. CLORM's ``FactBase`` is
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

To provide for more flexible queries CLORM introduces placeholders in order to
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
that corresponds to an indexed field then CLORM is able to use this index to
make query execution efficient.

A ``where`` clause can consist of more the one clause and these are treated as a
conjunction. Its is also possible to construct more complex clauses using CLORM
supplied ``and_``, ``or_``, and ``not_`` constructs.

.. code-block:: python

       query1=facts.select(Person).where(or_(Person.person == "dave", Person.address == "UNSW"))

Here when ``query1`` is execute it will return any person who is either
``"dave""`` or or based at ``"UNSW"``.

Functors and Lambdas
<<<<<<< HEAD
^^^^^^^^^^^^^^^^^^^^
=======
--------------------
>>>>>>> c3470a6aafde0b666ffd488a9a20993c1f5945cc

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
equivalent in behaviour. In particular, the CLORM generated functor has a
structure that the system is able to analyse and can therefore potentially use
indexing to improve query efficiency.

However, there is no mechanism to analyse the internal make up of a lambda or
function. Consequently in these cases the query would have to examine every fact
in the fact base of the given type and test the function against that
fact. Hence it is usually preferable to use the CLORM generated where clauses
possible.


