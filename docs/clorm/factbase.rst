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

Clorm provides the :class:`~clorm.FactBase` class as a container for storing and
querying facts. A :class:`~clorm.FactBase` behaves much like a normal Python
``set`` object with two caveats: firstly, it can only contain instances of
:class:`~clorm.Predicate` sub-classes, and secondly, it provides an interface to
a database-like query mechanism.

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
functions. Like a Python ``set`` object it has an
:py:meth:`FactBase.add()<clorm.FactBase.add>` member function for adding
facts. However, because it can only store :class:`~clorm.Predicate` instances
this function is able to be more flexible and has been overloaded to accept
either a single fact or a collection of facts.

.. code-block:: python

   dave_dog = Pet(owner="dave", petname="Bob")
   morri_cat = Pet(owner="morri", petname="Fido")
   morri_cat2 = Pet(owner="morri", petname="Dusty")

   fb.add(dave_dog)
   fb.add([morri_cat, morri_cat2])

   assert dave_dog in fb
   assert morri_cat in fb
   assert morri_cat2 in fb


Querying
--------

An important motivation for providing a specialised :class:`~clorm.FactBase`
container class for storing facts, as opposed to simply using a Python ``list``
or ``set`` object, is to support a rich mechanism for querying the contents of a
collection.

When an ASP model is returned by the solver the application developer needs to
process the model in order to extract the relevant information. The simplest
mechanism to do this is to simply loop through the facts in the model. This loop
will typically contain a number of conditional statements to determine what
action to take for the given fact; and to store it if some sort of matching
needs to take place.

However, this loop-and-test approach leads to unnecessary boilerplate code as
well as making the purpose of the code more obscure. :class:`~clorm.FactBase` is
intended to alleviate this problem by offering a database-like query mechanism
for extracting information from a model.

.. note::

   The following highlights the operations of the new Query API. As of Clorm
   1.2.1 this new API should be the preferred search mechanism. It provides all
   the functionality of the old query interface and much more; including
   SQL-like joins between predicates and controlling how the query results are
   presented.


Simple Queries
^^^^^^^^^^^^^^

Continuing the running example above the
:py:meth:`FactBase.query()<clorm.FactBase.query>` method can be used to create
:class:`~clorm.Query` objects.

.. code-block:: python

   query1=fb.query(Pet).where(Pet.owner == "dave")
   query2=fb.query(Person).where(Person.id == "dave")

The queries are defined by chaining over the member functions of a
:class:`~clorm.Query` object. Each function call returns a modified copy of the
:class:`~clorm.Query` object. Here the member function
:py:meth:`Query.where()<clorm.Query.where>` returns a modified copy of
itself. This chaining technique will be be familiar to users of Python ORM's
such as SQLAlchemy or Peewee, where it is used as a generator for SQL
statements.

A query object needs to be executed in order to return the search results. There
are number of end-points that can be used to execute the search. The
:py:meth:`Query.all()<clorm.Query.all>` member function returns a generator to
iterate over all matching search results:

.. code-block:: python

   assert set(query1.all()) == set([dave_cat,dave_dog])

The :py:meth:`Query.singleton()<clorm.Query.singleton>` member function returns
the single matching item (and raises an exception if there is not exactly one
match):

.. code-block:: python

   assert query2.singleton() == dave


The :py:meth:`Query.first()<clorm.Query.first>` member function returns the first
matching item, and only raises an exception if there no matching items:

.. code-block:: python

   assert query2.first() == dave

The :py:meth:`Query.count()<clorm.Query.count>` member function returns
the number of matching entries:

.. code-block:: python

   assert query1.count() == 2

.. note::

   For comparison the following shows how these queries and results can be
   encoded using the legacy query API. The
   :py:meth:`FactBase.select()<clorm.FactBase.select>` method is used to create
   :class:`clorm.Select` objects. Note: there is no matching member function for
   :py:meth:`Query.first()<clorm.Query.first>`.


   .. code-block:: python

       query1_legacy=fb.select(Pet).where(Pet.owner == "dave")
       query2_legacy=fb.select(Person).where(Person.id == "dave")

       assert set(query1_legacy.get()) == set([dave_cat,dave_dog])
       assert query2_legacy.get_unique() == dave
       assert query1_legacy.count() == 2

   An important difference between the old and new interfaces is that the call
   to :meth:`Select.get()<clorm.Select.get>` executes the query and returns the
   list of results. In contrast the call to :meth:`Query.all()<clorm.Query.all>`
   returns a generator and the query is executed by the generator during its
   iteration.


Queries with Joins
^^^^^^^^^^^^^^^^^^

It is often useful to match instances of different predicates in the same way
that you would join multiple database tables in an SQL query. To perform a
search across multiple predicates it is first necessary to specify the
predicates in the call to :py:meth:`FactBase.query()<clorm.FactBase.query>` and
then specify to how these predicates are to be joined in the chained member
function :py:meth:`Query.join()<clorm.Query.join>`

.. code-block:: python

   query3=fb.query(Person,Pet).join(Person.id == Pet.owner)

When a query contains multiple predicates the result will consist of tuples,
where each tuple contains the facts matching the signature of predicates in the
``query`` clause. Mathematically, the tuples are a subset of the cross-product
over instances of the predicates; where the subset is determined by the ``join``
clause.

.. code-block:: python

   assert set(query3.all()) == set([(dave,dave_cat),(dave,dave_dog),
                                    (morri,morri_cat),(morri,morri_cat2)])


Projections
^^^^^^^^^^^

Returning tuples of facts may not be convenient and a more usable output format
may be desired. In such a case it is possible to specify a
:py:meth:`Query.select()<clorm.Query.select>` specification to provide the
*projection* of the results. This is much like the use of the SQL ``SELECT``
clause.

.. note::

   Instead of formulating the query from scratch a new query can be defined as a
   refinement of an existing query.

.. code-block:: python

   query4=query3.select(Pet.petname, Person.address)

   assert set(query4.all()) == set([("Bob","UNSW"),("Frank","UNSW"),
                                    ("Fido","UNSW"),("Dusty","UNSW")])


In the general case the query result is returned as a tuple consisting of the
instances of the signature matching the
:py:meth:`FactBase.query()<clorm.FactBase.query>` specification. However, if the
result signature is for a single item, for example you only want to return the
name of the pet, then returning a singleton tuple is not very intuitive. So,
instead, when the result signature consists only of a single item then the API
default behaviour is for the query result to return the items themselves rather
than being wrapped in a singleton tuple.

.. code-block:: python

   query5=query3.select(Pet.petname)

   assert set(query5.all()) == set(["Bob","Frank","Fido","Dusty"])

One important point to note when using projections is that the uniqueness of the
output is no longer guaranteed. While the combinations of the cross-product of
tuples being joined are guaranteed to be unique, once a
:py:meth:`Query.select()<clorm.Query.select>` signature is specified this may no
longer be the case. For example, if in the above query we only want to output
the addresses of the owners of the different pets, the projection will lead to
duplicate elements. These duplicates can be removed from the search by
specifying the :py:meth:`Query.distinct()<clorm.Query.distinct>` modifier. In
terms of SQL this is similar to specfying a ``SELECT DISTINCT`` query.

.. code-block:: python

   query6=query3.select(Person.address)
   query7=query6.distinct()

   assert query6.count() == 4
   assert set(query6.all()) == set(["UNSW"])
   assert list(query7.all()) == ["UNSW"]


Finally, for greatest flexibility the
:py:meth:`Query.select()<clorm.Query.select>` member function can be passed a
single Python `callable` object such as a function or lambda expression. The
call signature of this object must match the signature specified in the
:py:meth:`FactBase.query()<clorm.FactBase.query>` specification. The output of
this callable are then presented as the results of the query.

.. code-block:: python

   query7=fb.query(Person,Pet).join(Person.id == Pet.owner)\
            .select(lambda pn,pt: f"{pt.petname} from {pn.address}")


Queries with Ordered Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :py:meth:`Query.order_by()<clorm.Query.order_by>` member function allows for
the ordering of results similar to an SQL ``ORDER BY`` clause. Multiple fields
can be listed as well as being able to specify ascending or descending sort
order; with ascending order being the default and descending order specified by
the :func:`~clorm.desc` function.

.. code-block:: python

   from clorm import desc

   query8=fb.query(Pet).order_by(Pet.owner, desc(Pet.petname))\
            .select(Pet.owner,Pet.petname)

   assert list(query8.all()) == [("dave","Frank"),("dave","Bob"),
                                 ("morri","Fido"),("morri","Dusty")]


Grouping the Query Results
^^^^^^^^^^^^^^^^^^^^^^^^^^

Query results can be grouped in a similarly to an SQL ``GROUP BY`` clause using
the :py:meth:`Query.group_by()<clorm.Query.group_by>` member function . An
important distinction between SQL and Clorm's grouping mechanism is that Clorm
does not support query aggregate functions, so any aggregating needs to be
performed outside the query specification itself.

The :py:meth:`Query.group_by()<clorm.Query.group_by>` clause modifies the
behaviour of the output of the generator returned
:py:meth:`Query.all()<clorm.Query.all>`. Instead of simply iterating over the
individual items, the iterator returns pairs where the first element of the pair
is the group identifier (based on the ``group_by`` specification) and the second
element is an iterator over the matching elements within the group.

.. code-block:: python

   query9=fb.query(Pet).group_by(Pet.owner)\
            .order_by(desc(Pet.petname)).select(Pet.petname)

   result = [(oname, list(petnames)) for oname,petnames in query9.all()]
   assert result == [("dave",["Frank","Bob"]),("morri",["Fido","Dusty"])]

Querying by Positional Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As well as querying by field name (or sub-field name) it is also possible to
query by the field (sub-field) position.

.. code-block:: python

   query10=fb.query(Pet).where(Pet[0] == "dave").order_by(Pet[1])

However, earlier warnings still hold; use positional arguments sparingly and
only in cases where the order of elements will not change as the ASP code
evolves.


Querying Predicates with Complex Terms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Querying Predicates with complex terms is no different to the simple case. A
chain of "." notation expressions and positional arguments can be used to
identify the appropriate field. For example we can replace the ``Person``
definition earlier to something containing a tuple:

.. code-block:: python

   from clorm import Predicate, ConstantField, StringField, FactBase

   class PersonAlt(Predicate):
      id = ConstantField
      address = (StringField,StringField)

   dave = PersonAlt(id="dave", address=("Newcastle","UNSW"))
   morri = PersonAlt(id="morri", address=("Sydney","UNSW"))
   torsten = PersonAlt(id="torsten", address=("Potsdam","UP"))

   fb2 = FactBase([dave,morri,torsten])

   query11=fb2.query(PersonAlt)\
              .where(PersonAlt.address[1] == "UNSW")\
              .select(PersonAlt.address[0])\
              .order_by(PersonAlt.address[1])

   assert list(query11.all()) == ["Newcastle","Sydney"]


Complex Query Expressions
^^^^^^^^^^^^^^^^^^^^^^^^^

So far we have only seen Clorm's support for queiries with a single ``where``
clause, such as:

.. code-block:: python

   query12=fb.query(Pet).where(Pet.owner == "dave")

However, more complex queries can be specified. Firstly, a ``where`` clause can
consist of a comma seperated list of clauses. These are treated as a
conjunction:

.. code-block:: python

   # Search for pets named Bob that are owned by dave

   query13=fb.query(Pet).where(Pet.petname == "Bob", Pet.owner == "dave")

   assert query13.singleton() == dave_dog

It is also possible to specify more complex queries using the overloaded logical
operators ``&``, ``|``, and ``~``.

.. code-block:: python

   # Find the Person with id "torsten" or whose university address is not "UP"
   query14=fb2.query(PersonAlt)\
              .where((PersonAlt.id == "torsten") | ~(PersonAlt.address[1] == "UP"))

   assert set(query14.all()) == set([dave,morri,torsten])

   # Find the Person with id "dave" and with address "UNSW"
   query15=fb2.query(PersonAlt)\
              .where((PersonAlt.id == "dave") & (PersonAlt.address[1] == "UNSW"))

   assert query15.singleton() == dave

Clorm also provides the explicit functions :py:func:`~clorm.and_`,
:py:func:`~clorm.or_`, and :py:func:`~clorm.not_` for these logical operators,
but the overloaded syntax is arguably more intuitive. With the explicit
functions the above could also be written as:

.. code-block:: python

   query14alt=fb2.query(PersonAlt)\
                 .where(or_(PersonAlt.id == "torsten", not_(PersonAlt.address[1] == "UP")))
   query15alt=fb2.query(PersonAlt)\
                 .where(and_(PersonAlt.id == "dave", PersonAlt.address[1] == "UNSW"))


Finally, it is also possible to test for membership of a collection using the
:py:func:`~clorm.in_` and :py:func:`~clorm.notin_` functions.

.. code-block:: python

   query16=fb2.query(PersonAlt).where(in_(PersonAlt.id, ["dave","bob","sam"])

   assert query16.singleton() == dave

Queries with Parameters
^^^^^^^^^^^^^^^^^^^^^^^

To support more flexible queries Clorm provides placeholders as a means of
parameterising queries. Placeholders are named ``ph1_`` to ``ph4_`` and
correspond to the positional parameters. These parameters are bounds to actual
values by calling :py:meth:`Query.bind()<clorm.Query.bind>` where the input
parameter to the function call must match the declared placeholders.

.. code-block:: python

   from clorm import ph1_, ph2_

   query12=fb.query(Pet).where((Pet.owner == ph1_) & (Pet.petname == ph2_))

   assert query12.bind("dave","Bob").singleton() == dave_dog
   assert query12.bind("dave","Fido").count() == 0

Additional placeholders can be defined using the :py:func:`ph_` function. For
example, ``ph_(5)`` will create a placeholder for the 5th positional argument.

Clorm also supports **named placeholders**, which may be preferable if there are
a larger number of parameters. A named placeholder is created by calling the
:py:meth:`ph_()` function with a non-numeric first parameter, and are referenced
in the call to :py:meth:`Query.bind()<clorm.Query.bind>` using keyword function
parameters. An advantange of named placeholders is that they allow for a default
value to be set.

.. code-block:: python

   from clorm import ph_

   query13=fb.query(Pet).where(Pet.owner == ph_("owner","dave"))

   assert set(query13.all()) == set([dave_dog,dave_cat])
   assert set(query13.bind(owner="morri").all()) == set([morri_cat,morri_cat2])

Querying Negative Facts/Complex-Terms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ASP problems can often by compactly modelled using only default negation instead
of strong negation. Because of this the use of explicitly negated literals is
not particularly common in ASP programs.

Nevertheless Clorm does support negated facts and the Clorm query mechanism
support querying based on the sign of a fact or complex term.

.. code-block:: python

   from clorm import IntegerField

   class P(Predicate):
       a = IntegerField

   p1 = P(1)
   neg_p2 = P(2,sign=False)

   fb3 = FactBase([p1,neg_p2])
   assert fb3.query(P).where(P.sign == True).singleton() == p1
   assert fb3.query(P).where(P.sign == False).singleton() == neg_p2


Querying the Predicate Itself
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While it is possible to query fields (and sub-fields) of a predicate using the
intutive "." syntax (eg., ``Pet.owner == ph1_``), unfortunately, it is not
possible to provide this intuitive syntax for querying the predicate itself
(e.g., a query of ``Pet < ph1_`` will fail).

Instead a helper function :py:func:`path` is provided for this special case.

.. code-block:: python

   from clorm import path

   query14=fb.query(Pet).where(path(Pet) == dave_dog)
   assert query14.count() == 1

Note, querying by the predicate itself is a boundary case. While testing for
equality or inequality makes sense semantically, the semantics of a query based
on an ordering operator doesn't always make sense (eg., ``path(Pet) < dave_dog``).

Furthermore, when testing for equality or inequality it is usually simpler to
not use the query mechanism and instead to use the basic Python set inclusion
operation:

.. code-block:: python

   assert dave_dog in fb


FactBases with Indexes
^^^^^^^^^^^^^^^^^^^^^^

A typical ASP program has models that contain relatively small numbers of facts
(e.g., 10-100 facts). With such small numbers of facts, querying these facts
from a :class:`~clorm.FactBase` can often be done without regard to performance
considerations, since the solving of the combinatorial ASP problem will often
dominate.

However, as the number of the number of facts increases so to does the cost of
querying these facts from a :class:`~clorm.FactBase`. Eventually this can lead
to a noticeable impact of performance.

In order to alleviate this problem a :class:`~clorm.FactBase` can be defined
with indexes for one of more fields.

To highlight this the following example creates a simple test predicate that has
two fields. Instances are created where the two fields have identical values,
and these instances are added to a :class:`~clorm.FactBase` where one field is
indexed and the other is not.

.. code-block:: python

   class Num(Predicate):
       to_idx=IntegerField
       not_to_idx=IntegerField

   fb4 = FactBase([Num(to_idx=n,not_to_idx=n) for n in range(0,100000)], indexes=[Num.to_idx])

We can now compare the timing differences between searching for a value where
one query searches for a value based on the indexed field and the other query
searches for the same value based on the non-indexed field.

.. code-block:: python

   import time

   query15=fb4.query(Num).where(Num.to_idx == 50000)
   query16=fb4.query(Num).where(Num.not_to_idx == 50000)


   start_q15 = time.time()
   assert query15.count() == 1
   q15_time = time.time() - start_q15

   start_q16 = time.time()
   assert query16.count() == 1
   q16_time = time.time() - start_q16

   assert q15_time < q16_time
   print("Indexed search {} vs non-indexed search {}".format(q15_time,q16_time))

To confirm that these two queries are indeed behaving differently we can examine
the query plans for the respective queries by calling the
:py:meth:`Query.query_plan()<clorm.Query.query_plan>` methods.

.. code-block:: python

   print("Querying without indexing:\n{}\n".format(query15.query_plan()))
   print("Query with indexing:\n{}\n".format(query16.query_plan()))

Note, currently, there is no official API for a query plan object so it is only
possible to print the object for manual examination.  The key aspect to notice
here is that the search on the indexed field appears as a ``keyed search``
whereas the search on the non-indexed field appears as a ``filter
clause``. Essentially the non-indexed search has to examine every fact in the
fact base while the indexed search doesn't.


.. code-block:: bash

   Querying without indexing:
   ------------------------------------------------------
   QuerySubPlan:
           Input Signature: ()
           Root path: Num
           Indexes: (Num.to_idx,)
           Prejoin keyed search: [ Num.to_idx == 50000 ]
           Prejoin filter clauses: None
           Prejoin order_by: None
           Join key: None
           Post join clauses: None
           Post join order_by: None
   ------------------------------------------------------

   Query with indexing:
   ------------------------------------------------------
   QuerySubPlan:
           Input Signature: ()
           Root path: Num
           Indexes: (Num.to_idx,)
           Prejoin keyed search: None
           Prejoin filter clauses: ( [ Num.not_to_idx == 50000 ] )
           Prejoin order_by: None
           Join key: None
           Post join clauses: None
           Post join order_by: None
   ------------------------------------------------------

A final note. As with indexing in databases, the use of indexes should be
monitored carefully. The speed up in search must always be balanced the cost of
constructing and maintaining the index.




