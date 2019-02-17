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
can only instances of Predicate (or it's sub-classes) and has database-like
query mechanism.

.. code-block:: python

   from clorm import *

   class Person(Predicate):
      person = ConstantField()
      address = StringField()

   class Pet(Predicate):
      owner = ConstantField()
      petname = StringField()

   dave = Person(person="dave", address="UNSW")
   morri = Person(person="morri", address="UNSW")
   dave_cat = Pet(owner="dave", petname="Frank")

   fb = FactBase([dave,morri,dave_cat])

   # The in and len operators work as expected
   assert dave in fb
   assert len(fb) == 3

The fact base can be populated at object construction time or later. Like a
Python ``set`` object a ``FactBase`` has an ``add`` member function for adding
facts. However, because it only accepts ``Predicate`` instances the function is
overloaded to accept either a single fact or a list of facts.

.. code-block:: python

   dave_dog = Pet(owner="dave", petname="Bob")
   morri_cat = Pet(onwer="morri", petname="Fido")
   morri_cat2 = Pet(onwer="morri", petname="Dusty")

   fb.add(dave_dog)
   fb.add([morri_cat, morri_cat2])

Querying
--------

The primary motivation for providing a specialised container class for storing
facts, instead of simply using a Python ``list`` or ``set`` object, is to
support a richer query mechanism.

When an ASP model is returned by the solver the application developer needs to
process the model in order to extract the relevant facts. The simplest mechanism
to do this to loop through the facts in the model. This loop will typically
contain a number of conditional statements to determine what action to take for
the given fact; and to store it if some sort of matching needs to take place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. ``FactBase`` is intended to
alleviate this problem by offering a database-like query mechanism for
extracting facts from a model.

Simple Queries
^^^^^^^^^^^^^^

Assuming the definitions and the ``fb`` instance above, a ``FactBase`` object
can create ``Select`` query objects:

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

Indexing
^^^^^^^^

Querying can be a relatively expensive process is it has to potentially has to
examine every fact in the ``FactBase``. However, if you know that you will be
mostly searching for on a particular field(s) then it is useful to define an index
on that field when the ``FactBase`` object is instantiated:

.. code-block:: python

   fb = FactBase([dave,morri,dave_cat], index=[Pet.owner])

   query=facts.select(Pet).where(Pet.owner == ph1_)


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
execution using a keyword function parameter. An advantange of named
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

Importing Raw Clingo Symbols and FactBaseBuilder
------------------------------------------------

A ``FactBase`` container can only contain predicate objects. However, the Clingo
reasoner deals in ``Clingo.Symbol`` objects. Clorm provides the ``unify``
function and the ``FactBaseBuilder`` class to simplify the interaction with
``Clingo.Symbol`` objects.

The ``unify`` function takes two parameters; a list of predicate classes as
`unifies` and a list of raw clingo symbols. It then tries to unify the list of
raw symbols with the list of predicates. This function returns a list of facts
that represent the unification of the symbols with the first matching
predicate. If a symbol was not able to unify with any predicate then it is
ignored.

.. code-block:: python

   from clingo import *
   from clorm import *

   class Person(Predicate):
      person = ConstantField()
      address = StringField()

   dave = Person(person="dave", address="UNSW")
   dave_raw = Function("person", [Function("dave",[]),String("UNSW")])
   facts = unify([Person], [dave_raw])
   assert facts == [dave]

.. note:: Since a raw Clingo symbol is mapped to the first predicate that it
   unifies with, the order that the predicates are defined can change the
   behaviour of the fact base. Therefore, in general it is a good idea to avoid
   defining multiple predicates that can unify with the same symbols.


The ``FactBaseBuilder`` provides a helper class to make it easier to build fact
bases. It also provides integrated features to make it easier to define field
indexes.

Because defining queries is a potentially common requirement the field
definition within the predicate can include the option ``index=True`` which will
be used by the ``FactBaseBuilder``.

So the earlier definition can be modified:

.. code-block:: python

   class Pet(Predicate):
      owner = ConstantField(index=True)
      petname = StringField()

``FactBaseBuilder`` provides a decorator function that can used to register the
class and index option with the builder.

.. code-block:: python

   from clorm import *

   fbb = FactBaseBuilder()

   @fbb.register
   class Person(Predicate):
      person = ConstantField()
      address = StringField()

   @fbb.register
   class Pet(Predicate):
      owner = ConstantField(index=True)
      petname = StringField()

   dave_raw = Function("person", [Function("dave",[]),String("UNSW")])
   fb1 = fbb.new(symbols=[dave_raw])


``FactBaseBuilder.new()`` member function has two other useful features. Firtly,
the option ``raise_on_empty=True`` will throw an error if no clingo symbols
unify with the registered predicates. While there are legitimate cases where a
symbol doesn't unify with the builder there are also many cases where this
indicates an error in the definition of the predicates or in the ASP program
itself.

The final option is that it allows for a delayed initialisation feature for the
``FactBase``. We will be highlighted in the section on integrating with Clingo
and processing ASP models, but essentially it allows for ``FactBase`` objects
that are not used to be defined and discarded cheaply.










