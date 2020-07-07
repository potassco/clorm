Fact Bases and Querying
=======================

As well as offering a high-level interface for mapping ASP facts to Python
objects, Clorm also provides facilities for dealing with collections of facts.
An ASP application typically does not simply deal with individual facts in
isolation, but instead needs to deal in a collection of facts; whether they are
the set of facts that make up the *problem instance* or, alternatively, the facts
that constitute the *model* of a problem,

A Container for Facts
---------------------

Clorm provides the ``FactBase`` class as a container for storing and querying
facts. A ``FactBase`` behaves much like a normal Python ``set`` object with two
caveats: firstly, it can only contain instances of ``Predicate`` sub-classes,
and secondly, it has a database-like query mechanism.

.. code-block:: python

   from clorm import Predicate, ConstantField, StringField, FactBase

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

   # The "in" and "len" operators work as expected
   assert dave in fb
   assert len(fb) == 3

A fact base can be populated at object construction time or later. It can also
be manipulated using the standard Python set operators and member
functions. Like a Python ``set`` object it has an ``add`` member function for
adding facts. However, because it can only store ``Predicate`` instances this
function is able to be more flexible and has been overloaded to accept either a
single fact or a collection of facts.

.. code-block:: python

   dave_dog = Pet(owner="dave", petname="Bob")
   morri_cat = Pet(onwer="morri", petname="Fido")
   morri_cat2 = Pet(onwer="morri", petname="Dusty")

   fb.add(dave_dog)
   fb.add([morri_cat, morri_cat2])

   assert dave_dog in fb
   assert morri_cat in fb
   assert morri_cat2 in fb

Indexing
^^^^^^^^

A typical ASP program has models that contain relatively small numbers of facts
(e.g., 10-100 facts). With such small numbers of facts, querying these facts
from a ``FactBase`` can often be done without regard to performance
considerations.

However, in a similar manner to a traditional database, there can be cases where
the number of facts that need to be stored can be relatively large. In such
cases querying these facts from a ``FactBase`` can present a performance
bottleneck.

In order to alleviate this problem a ``FactBase`` can be defined with indexes
for specific fields. Extending the above example:

.. code-block:: python

   fb1 = FactBase([dave,morri,dave_cat],indexes=[Person.id, Pet.owner])

Here the fact base ``fb1`` maintains an index on the ``id`` field of the
``Person`` predicate, as well as the ``owner`` field of the ``Pet`` predicate.

With these indexes any querying on the ``Person.id`` or ``Pet.owner`` fields
will be able to use the appropriate index and not have to examine every fact of
that type.

Of course, as with database indexing, specifying indexes should be done
sparingly to ensure the right balance between the cost of maintaining the index
against the cost of querying the fact base.


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
can be used to create ``Select`` query objects:

.. code-block:: python

       query1=fb.select(Person).where(Person.id == "dave")
       query2=fb.select(Pet).where(Pet.owner == "dave")

A query object needs to be executed in order to return the results. There are
three member functions to execute a query: ``get()``, ``get_unique()``, and
``count()``. ``get()`` returns a list of results, while ``get_unique()`` returns
exactly one result and will raise a ``ValueError`` if this is not the
case. Finally, ``count()`` returns the number of matched entries.

.. code-block:: python

       dave = query1.get_unique()
       for pet in query2.get():
           assert pet.owner == "dave"

Querying Negative Facts/Complex-Terms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Clorm query mechanism support querying based on the sign of a fact or
complex term.

.. code-block:: python

   class P(Predicate):
       a = IntegerField

   p1 = P(1)
   neg_p2 = P(2,sign=False)

   fb = FactBase([p1,neg_p2])
   assert fb.select(P).where(P.sign == True).get(), [p1]
   assert fb.select(P).where(P.sign == False).get(), [neg_p2]

Queries that use Indexes
^^^^^^^^^^^^^^^^^^^^^^^^

Querying can be a relatively expensive process as it has to potentially to
examine every fact in the ``FactBase``. However, if you know that you will be
mostly searching for values that match a particular field (or set of fields)
then it is useful to define an index on that field (or fields) when the
``FactBase`` object is instantiated:

.. code-block:: python

   fb3 = FactBase([dave,morri,dave_cat], index=[Pet.owner])

   # Using an indexed field in a query
   query=fb3.select(Pet).where(Pet.owner == "dave")


Queries with Parameters
^^^^^^^^^^^^^^^^^^^^^^^

To allow more flexible queries Clorm introduces placeholders as a means of
parameterising queries. Placeholders are named ``ph1_`` to ``ph4_`` and
correspond to the position of the parameter in the ``get()``, ``get_unique()``,
or ``count()`` function calls.

.. code-block:: python

       query1=fb.select(Person)
       query2=fb.select(Pet).where(Pet.owner == ph1_)

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

   query2=fb.select(Pet).where(Pet.owner == ph_("owner", "dave"))

   # Find pets owned by "morri"
   for pet in query2.get(owner="morri"):
       print("\t pet named {}".format(pet.petname))

   # Find pets owned by "dave" (using the default value)
   for pet in query2.get():
       print("\t pet named {}".format(pet.petname))


Queries with Output Ordering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Queries allow for ordering the result by setting order options using the
``order_by`` member function. Multiple fields can be listed as well as being
able to specify ascending or descending sort order (with ascending order being
the default).

.. code-block:: python

   query2=fb.select(Pet).order_by(Pet.owner, Pet.petname)

The above will list all pets, first sorted by the owner's name and then sorted
by the pet's name.

In order to specify descending order you need to use the ``desc`` function. So
for the above example to sort by the pet's name in descending order:

.. code-block:: python

   from clorm import desc

   query2=fb.select(Pet).order_by(Pet.owner, desc(Pet.petname))


Querying by Positional Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As well as querying by field name (or sub-field) it is also possible to query by
the field position.

.. code-block:: python

   query2=fb.select(Pet).where(Pet[0] == "dave").order_by(Pet[1])

However, the warning from the previous section still holds; use positional
arguments sparingly and only in cases where the order of elements will not
change as the ASP code evolves.

Querying Predicates with Complex Terms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Querying Predicates with complex terms is no different to the simple case. A
chain of "." notation expressions and positional arguments can be used to
identified the appropriate field. For example we can replace the the ``Person``
definition earlier to something with tuples:

.. code-block:: python

   from clorm import Predicate, ConstantField, StringField, FactBase

   class Person(Predicate):
      id = ConstantField
      address = (StringField,StringField)

   dave = Person(id="dave", address=("Newcastle","UNSW"))
   morri = Person(id="morri", address=("Sydney","UNSW"))
   torsten = Person(id="torsten", address=("Potsdam","UP"))

   fb = FactBase([dave,morri,torsten])

   query2=fb.select(Person).where(Person.address[1] == "UNSW")

   assert query2.count() == 2

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
       query3=fb.select(Pet).where(path(Pet) <= p1)

Here the query will return all pet objects that are less than ``p1``, based on
the ordering of the underlying Clingo Symbol objects. Note, querying by the
predicate itself is a boundary case and it is not necessarily clear when this
feature is required. For example, when testing for equality it is usually
simpler to not use the query mechanism and instead to use the basic Python set
inclusion operation:

.. code-block:: python

   assert p1 not in facts

.. note::

   The technical reason for not providing the intuitive syntax when querying on
   the Predicate itself is that this would require overloading the boolean
   comparison operators for the Predicate's metaclass. This would likely cause
   unexpected behaviour when using the Predicate class in a variety of
   contexts. Furthermore, the use-case for querying on the predicate instance
   itself is limited, so it was deemed preferable to simply provide a special
   syntax for this boundary case.


Complex Query Expressions
^^^^^^^^^^^^^^^^^^^^^^^^^

So far we have only seen Clorm's support for queiries with a single ``where``
clause, such as:

.. code-block:: python

   query=fb.select(Pet).where(Pet.owner == "dave")

or with a single placeholder:

.. code-block:: python

   query=facts.select(Pet).where(Pet.owner == ph1_)

However, more complex queries can be specified, including with multiple
placeholders. Firstly, a ``where`` clause can consist of a comma seperated list
of clauses. These are treated as a conjunction:

.. code-block:: python

   query1=fb.select(Pet).where(Pet.name == _ph1, Pet.owner == _ph2)

   # Count facts for pets named "Fido" with owner "morri"
   assert query1.count("Fido","morri")) == 1

It is also possible to specify more complex queries using overloaded logical
operators ``&``, ``|``, and ``~``:

.. code-block:: python

   # Find the Person with id "torsten" or whose university address is not "UP"
   query1=fb.select(Person).where((Person.id == "torsten") | ~(Person.address[1] == "UP"))

   # With the previously defined factbase this matches all people
   assert query1.count() == 3

   # Find the Person with id "dave" and with address "UNSW"
   query2=fb.select(Person).where((Person.id == "dave") & (Person.address[1] == "UNSW"))
   assert query2.count() == 1

Clorm also provides explicit functions (``and_``, ``or_``, and ``not_``) for
these logical operators, but the overloaded syntax is arguably more
intuitive. With these operators the above could be written as:

.. code-block:: python

   query1=fb.select(Person).where(or_(Person.id == "torsten", not_(Person.address[1] == "UP")))
   query2=fb.select(Person).where(and_(Person.id == "dave", Person.address[1] == "UNSW"))

.. note::

   *Limitations*. Clorm has some current implementation limitations when it
   comes to complex queries and indexing. Currently, if a complex query contains
   multiple fields, and those fields are indexed, Clorm is only able to use the
   index of the first field in the query. This is an implementation, rather than
   a design, limitation and could be improved if there is a genuine need.

Functors and Lambdas
^^^^^^^^^^^^^^^^^^^^

Finally, it should be noted that the specification of a ``where`` clause is in
reality a mechanism for generating functors. Therefore, instead of using the
intuitive field syntax, it is possible to simply provide a function or lambda
statement instead. The signature of such a function requires at least a single
argument corresponding to the fact object and must return ``True`` if that fact
matches the search criteria and ``False`` otherwise. If the ``get()`` member
function is called with additional parameters then these parameters will also be
passed to the ``where`` function.

For example to find a specific owner from the set of pet facts, the following
two queries will generate the same results.


.. code-block:: python

       query1=facts.select(Pet).where(Pet.owner == ph1_)
       query2=facts.select(Pet).where(lambda x, o: x.owner == o))

       results1 = list(query1.get("dave"))
       results2 = list(query2.get("dave"))

While both these queries do generate the same result they are not necessarily
equivalent in behaviour. In particular, the Clorm generated functor has a
structure that the system is able to analyse and can therefore take advantage of
any indexed fields to improve query efficiency.

In contrast, there is no simple mechanism to analyse the internal make up of a
lambda statement or function. Consequently in these latter cases the query would
have to examine every fact in the fact base, of that predicate type, and test
the function against that fact. In a large fact base this could result in a
significant performance penalty. Hence it is usually preferable to use the Clorm
generated clauses where possible.
