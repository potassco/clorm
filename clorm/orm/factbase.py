# -----------------------------------------------------------------------------
# Clorm ORM FactBase implementation. FactBase provides a set-like container
# specifically for storing facts (Predicate instances).
# ------------------------------------------------------------------------------

import io
import operator
import collections
import bisect
import inspect
import abc
import functools
import itertools

from .core import *
from .core import get_field_definition, PredicatePath, kwargs_check_keys, \
    validate_root_paths

from .query import *

from .query import Placeholder, OrderBy, desc, asc

from .query import JoinQueryPlan, QueryPlan, \
    process_where, process_join, process_orderby, \
    make_input_alignment_functor, basic_join_order_heuristic, make_query_plan,\
    FuncInputSpec, FunctionComparator, QuerySpec, make_query, QueryOutput

from .factcontainers import FactSet, FactIndex, FactMap, factset_equality

__all__ = [
    'FactBase',
    'Select',
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Support function for printing ASP facts
#------------------------------------------------------------------------------

def _format_asp_facts(iterator,output,width):
    tmp1=""
    for f in iterator:
        fstr="{}.".format(f)
        if tmp1 and len(tmp1) + len(fstr) > width:
            print(tmp1,file=output)
            tmp1 = fstr
        else:
            tmp1 = tmp1 + " " + fstr if tmp1 else fstr
    if tmp1: print(tmp1,file=output)

#------------------------------------------------------------------------------
# A FactBase consisting of facts of different types
#------------------------------------------------------------------------------

class FactBase(object):
    """A fact base is a container for facts (i.e., Predicate sub-class instances)

    ``FactBase`` can be behave like a specialised ``set`` object, but can also
    behave like a minimalist database. It stores facts for ``Predicate`` types
    (where a predicate type loosely corresponds to a *table* in a database)
    and allows for certain fields to be indexed in order to perform more
    efficient queries.

    The initaliser can be given a collection of predicates. If it is passed
    another FactBase then it simply makes a copy (including the indexed fields).

    FactBase also has a special mode when it is passed a functor instead of a
    collection. In this case it performs a delayed initialisation. This means
    that the internal data structures are only populated when the FactBase is
    actually used. This mode is particularly useful when extracting facts from
    models. Often a program will only want to keep the data from the final model
    (for example, with optimisation we often want the best model before a
    timeout). Delayed initialisation is useful will save computation as only the
    last model will be properly initialised.

    Args:
      facts([Predicate]|FactBase|callable): a list of facts (predicate
         instances), a fact base, or a functor that generates a list of
         facts. If a functor is passed then the fact base performs a delayed
         initialisation. If a fact base is passed and no index is specified then
         an index will be created matching in input fact base.
      indexes(Field): a list of fields that are to be indexed.

    """

    #--------------------------------------------------------------------------
    # Internal member functions
    #--------------------------------------------------------------------------

    # A special purpose initialiser so that we can delayed initialisation
    def _init(self, facts=None, indexes=None):

        # flag that initialisation has taken place
        self._delayed_init = None

        # If it is delayed initialisation then get the facts
        if facts and callable(facts):
            facts = facts()
        elif facts and isinstance(facts, FactBase) and indexes is None:
            indexes = facts.indexes
        if indexes is None: indexes=[]

        # Create FactMaps for the predicate types with indexed fields
        grouped = {}

        self._indexes = tuple(indexes)
        for path in self._indexes:
            if path.meta.predicate not in grouped: grouped[path.meta.predicate] = []
            grouped[path.meta.predicate].append(path)
        self._factmaps = { pt : FactMap(pt, idxs) for pt, idxs in grouped.items() }

        if facts is None: return
        self._add(facts)

    # Make sure the FactBase has been initialised
    def _check_init(self):
        if self._delayed_init: self._delayed_init()  # Check for delayed init

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------

    def _add(self, arg):
        if isinstance(arg, Predicate): return self._add_fact(type(arg),arg)
        facts = sorted(arg, key=lambda x : type(x).__name__)
        for ptype, g in itertools.groupby(facts, lambda x: type(x)):
            self._add_facts(ptype, g)

    def _add_fact(self, ptype, fact):
        if not issubclass(ptype,Predicate):
            raise TypeError(("type of object {} is not a Predicate "
                             "(or sub-class)").format(fact))
        fm = self._factmaps.setdefault(ptype, FactMap(ptype))
        fm.add_fact(fact)

    def _add_facts(self, ptype, facts):
        if not issubclass(ptype,Predicate):
            raise TypeError(("type of object {} is not a Predicate "
                             "(or sub-class)").format(fact))
        fm = self._factmaps.setdefault(ptype, FactMap(ptype))
        fm.add_facts(facts)

    def _remove(self, fact, raise_on_missing):
        ptype = type(fact)
        if not isinstance(arg, Predicate) or ptype not in self._factmaps:
            raise KeyError("{} not in factbase".format(arg))

        return self._factmaps[ptype].delete()

    #--------------------------------------------------------------------------
    # Initiliser
    #--------------------------------------------------------------------------
    def __init__(self, facts=None, indexes=None):
        self._delayed_init=None
        if callable(facts):
            def delayed_init():
                self._init(facts, indexes)
            self._delayed_init=delayed_init
        else:
            self._init(facts, indexes)


    #--------------------------------------------------------------------------
    # An internal API for the query mechanism. Not to be called by users.
    #--------------------------------------------------------------------------
    @property
    def factmaps(self):
        self._check_init()  # Check for delayed init
        return self._factmaps

    #--------------------------------------------------------------------------
    # Set member functions
    #--------------------------------------------------------------------------
    def add(self, arg):
        self._check_init()  # Check for delayed init
        return self._add(arg)

    def remove(self, arg):
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=True)

    def discard(self, arg):
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=False)

    def pop(self):
        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items():
            if fm: return fm.pop()
        raise KeyError("Cannot pop() from an empty FactBase")

    def clear(self):
        """Clear the fact base of all facts."""

        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items(): fm.clear()

    #--------------------------------------------------------------------------
    # Special FactBase member functions
    #--------------------------------------------------------------------------
    def select(self, *roots):
        """Create a Select query for a predicate type."""
        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = set([r.meta.predicate for r in validate_root_paths(roots)])
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return SelectImpl(self, roots)

    def delete(self, root):
        self._check_init()  # Check for delayed init
        return _Delete(self, root)

    def select2(self, *roots):
        """Create a Select query for a predicate type."""
        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = set([r.meta.predicate for r in validate_root_paths(roots)])
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return Select2Impl(self, QuerySpec(roots=tuple(validate_root_paths(roots))))

    @property
    def predicates(self):
        """Return the list of predicate types that this fact base contains."""

        self._check_init()  # Check for delayed init
        return tuple([pt for pt, fm in self._factmaps.items() if fm])

    @property
    def indexes(self):
        self._check_init()  # Check for delayed init
        return self._indexes

    def facts(self):
        """Return all facts."""

        self._check_init()  # Check for delayed init
        tmp = [ fm.factset for fm in self._factmaps.values() if fm]
        return list(itertools.chain(*tmp))

    def asp_str(self,width=0,commented=False):
        """Return a string representation of the fact base that is suitable for adding
        to an ASP program

        """
        self._check_init()  # Check for delayed init
        out = io.StringIO()

        if not commented:
            _format_asp_facts(self,out,width)
        else:
            first=True
            for fm in self._factmaps.values():
                if first: first=False
                else: print("",file=out)
                pm=fm.predicate.meta
                print("% FactBase predicate: {}/{}".format(pm.name,pm.arity),file=out)
                _format_asp_facts(fm.factset,out,width)

        data = out.getvalue()
        out.close()
        return data



    def __str__(self):
        self._check_init()  # Check for delayed init
        tmp = ", ".join([str(f) for f in self])
        return '{' + tmp + '}'

    def __repr__(self):
        return self.__str__()

    #--------------------------------------------------------------------------
    # Special functions to support set and container operations
    #--------------------------------------------------------------------------

    def __contains__(self, fact):
        """Implemement set 'in' operator."""

        self._check_init() # Check for delayed init

        if not isinstance(fact,Predicate): return False
        ptype = type(fact)
        if ptype not in self._factmaps: return False
        return fact in self._factmaps[ptype].factset

    def __bool__(self):
        """Implemement set bool operator."""

        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            if fm: return True
        return False

    def __len__(self):
        self._check_init() # Check for delayed init
        return sum([len(fm.factset) for fm in self._factmaps.values()])

    def __iter__(self):
        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            for f in fm.factset: yield f

    def __eq__(self, other):
        """Overloaded boolean operator."""

        # If other is not a FactBase then create one
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init(); other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if self_fms.keys() != other_fms.keys(): return False

        for p, fm1 in self_fms.items():
            fm2 = other_fms[p]
            if not factset_equality(fm1.factset,fm2.factset): return False

        return True

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __lt__(self,other):
        """Implemement set < operator."""

        # If other is not a FactBase then create one
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() ; other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if len(self_fms) > len(other_fms): return False

        known_ne=False
        for p, spfm in self_fms.items():
            if p not in other_fms: return False
            opfm = other_fms[p]
            if spfm.factset < opfm.factset: known_ne=True
            elif spfm.factset > opfm.factset: return False

        if known_ne: return True
        return False

    def __le__(self,other):
        """Implemement set <= operator."""

        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() ; other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if len(self_fms) > len(other_fms): return False

        for p, spfm in self_fms.items():
            if p not in other_fms: return False
            opfm = other_fms[p]
            if spfm.factset > opfm.factset: return False
        return True

    def __gt__(self,other):
        """Implemement set > operator."""
        if not isinstance(other, self.__class__): other=FactBase(other)
        return other.__lt__(self)

    def __ge__(self,other):
        """Implemement set >= operator."""
        if not isinstance(other, self.__class__): other=FactBase(other)
        return other.__le__(self)

    def __or__(self,other):
        """Implemement set | operator."""
        return self.union(other)

    def __and__(self,other):
        """Implemement set & operator."""
        return self.intersection(other)

    def __sub__(self,other):
        """Implemement set - operator."""
        return self.difference(other)

    def __xor__(self,other):
        """Implemement set ^ operator."""
        return self.symmetric_difference(other)

    def __ior__(self,other):
        """Implemement set |= operator."""
        self.update(other)
        return self

    def __iand__(self,other):
        """Implemement set &= operator."""
        self.intersection_update(other)
        return self

    def __isub__(self,other):
        """Implemement set -= operator."""
        self.difference_update(other)
        return self

    def __ixor__(self,other):
        """Implemement set ^= operator."""
        self.symmetric_difference_update(other)
        return self


    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        """Implements the set union() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        for o in others: predicates.update(o._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            if p in self._factmaps:
                fb._factmaps[p] = self._factmaps[p].union(*pothers)
            else:
                fb._factmaps[p] = FactMap(p).union(*pothers)
        return fb

    def intersection(self,*others):
        """Implements the set intersection() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        for o in others: predicates.intersection_update(o._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].intersection(*pothers)
        return fb

    def difference(self,*others):
        """Implements the set difference() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].difference(*pothers)
        return fb

    def symmetric_difference(self,other):
        """Implements the set symmetric_difference() function"""
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() # Check for delayed init
        other._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        predicates.update(other._factmaps.keys())

        for p in predicates:
            if p in self._factmaps and p in other._factmaps:
                fb._factmaps[p] = self._factmaps[p].symmetric_difference(other._factmaps[p])
            else:
                if p in self._factmaps: fb._factmaps[p] = self._factmaps[p].copy()
                fb._factmaps[p] = other._factmaps[p].copy()

        return fb

    def update(self,*others):
        """Implements the set update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        for o in others:
            for p,fm in o._factmaps.items():
                if p in self._factmaps: self._factmaps[p].update(fm)
                else: self._factmaps[p] = fm.copy()

    def intersection_update(self,*others):
        """Implements the set intersection_update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()
        num = len(others)

        predicates = set(self._factmaps.keys())
        for o in others: predicates.intersection_update(o._factmaps.keys())
        pred_to_delete = set(self._factmaps.keys()) - predicates

        for p in pred_to_delete: self._factmaps[p].clear()
        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            self._factmaps[p].intersection_update(*pothers)

    def difference_update(self,*others):
        """Implements the set difference_update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        for p in self._factmaps.keys():
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps ]
            self._factmaps[p].difference_update(*pothers)

    def symmetric_difference_update(self,other):
        """Implements the set symmetric_difference_update() function"""
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() # Check for delayed init
        other._check_init()

        predicates = set(self._factmaps.keys())
        predicates.update(other._factmaps.keys())

        for p in predicates:
            if p in self._factmaps and p in other._factmaps:
                self._factmaps[p].symmetric_difference_update(other._factmaps[p])
            else:
                if p in other._factmaps: self._factmaps[p] = other._factmaps[p].copy()


    def copy(self):
        """Implements the set copy() function"""
        self._check_init() # Check for delayed init
        fb=FactBase()
        for p,fm in self._factmaps.items():
            fb._factmaps[p] = self._factmaps[p].copy()
        return fb

#------------------------------------------------------------------------------
# Select is an interface query over a FactBase.
# ------------------------------------------------------------------------------

class Select(abc.ABC):
    """An abstract class that defines the interface to a query object.

    ``Select`` query object cannot be constructed directly.

    Instead a ``Select`` object is returned as part of a specfication return
    thed ``FactBase.select()`` function. Given a ``FactBase`` object ``fb``, a
    specification is of the form:

          ``query = fb.select(<predicate>).where(<expression>).order_by(<ordering>)``

    where ``<predicate>`` specifies the predicate type to search
    for,``<expression>`` specifies the search criteria and ``<ordering>``
    specifies a sort order when returning the results. The ``where()`` clause and
    ``order_by()`` clause can be omitted.

    """
    @abc.abstractmethod
    def join(self, *expressions):
        """Set the select statement's join conditions.

        The join statement consists of a list of comparison expressions, where
        each comparison expression specifies the join between two predicate
        types.

        """
        pass

    @abc.abstractmethod
    def where(self, *expressions):
        """Set the select statement's where clause.

        The where clause consists of a set of boolean and comparison
        expressions. This expression specifies a search criteria for matching
        facts within the corresponding ``FactBase``.

        Boolean expression are built from other boolean expression or a
        comparison expression. Comparison expressions are of the form:

               ``<PredicatePath> <compop>  <value>``

       where ``<compop>`` is a comparison operator such as ``==``, ``!=``, or
       ``<=`` and ``<value>`` is either a Python value or another predicate path
       object refering to a field of the same predicate or a placeholder.

        A placeholder is a special value that issubstituted when the query is
        actually executed. These placeholders are named ``ph1_``, ``ph2_``,
        ``ph3_``, and ``ph4_`` and correspond to the 1st to 4th arguments of the
        ``get``, ``get_unique`` or ``count`` function call.

        Args:
          expressions: one or more comparison expressions.

        Returns:
          Returns a reference to itself.

        """
        pass

    @abc.abstractmethod
    def order_by(self, *fieldorder):
        """Provide an ordering over the results.

        Args:
          fieldorder: an ordering over fields
        Returns:
          Returns a reference to itself.
        """
        pass

    @abc.abstractmethod
    def get(self, *args, **kwargs):
        """Return all matching entries."""
        pass


#------------------------------------------------------------------------------
# Delete is an interface to perform a query delete from a FactBase.
# ------------------------------------------------------------------------------

class Delete(abc.ABC):
    """An abstract class that defines the interface to a delete query object.

    ``Delete`` query object cannot be constructed directly.

    Instead a ``Delete`` object is returned as part of a specfication return
    thed ``FactBase.delete()`` function. Given a ``FactBase`` object ``fb``, a
    specification is of the form:

          ``query = fb.delete(<predicate>).where(<expression>)``

    where ``<predicate>`` specifies the predicate type to search
    for,``<expression>`` specifies the search criteria. The ``where()`` clause
    can be omitted in which case all predicates of that type will be deleted.

    """

    @abc.abstractmethod
    def where(self, *expressions):
        """Set the select statement's where clause.

        See the documentation for ``Select.where()`` for further details.
        """
        pass

    @abc.abstractmethod
    def execute(self, *args, **kwargs):
        """Function to execute the delete query"""
        pass

#------------------------------------------------------------------------------
# Query API version 1 with new query engine
#------------------------------------------------------------------------------

class SelectImpl(Select):

    def __init__(self, factbase, roots):
        self._factbase = factbase
        self._roots = tuple(validate_root_paths(roots))
        ptypes = set([ root.meta.predicate for root in self._roots])

        self._where = None
        self._joins = None
        self._orderbys = None
        self._pred2factset = {}
        self._path2factindex = {}

        for ptype in ptypes:
            fm =factbase.factmaps[ptype]
            self._pred2factset[ptype] = fm.factset
            for hpth, fi in fm.path2factindex.items():
                self._path2factindex[hpth] = fi

        qspec = QuerySpec(roots=self._roots,join=[],where=[],order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(), qspec)


    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    def join(self, *expressions):
        if self._where:
            raise TypeError(("The 'join' condition must come before the "
                             "'where' condition"))
        if self._orderbys:
            raise TypeError(("The 'join' condition must come before the "
                             "'order_by' condition"))
        if self._joins:
            raise TypeError("Cannot specify 'join' multiple times")
        if not expressions:
            raise TypeError("Empty 'join' expression")
        self._joins = process_join(expressions, self._roots)

        # Make a query plan in case there is no other inputs
        qspec = QuerySpec(roots=self._roots,join=self._joins,where=[],order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(), spec)
        return self

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
        if self._orderbys:
            raise TypeError(("The 'where' condition must come before the "
                             "'order_by' condition"))
        if self._where:
            raise TypeError("Cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("Empty 'where' expression")
        elif len(expressions) == 1:
            self._where = process_where(expressions[0],self._roots)
        else:
            self._where = process_where(and_(*expressions),self._roots)

        # Make a query plan in case there is no other inputs
        joins = self._joins if self._joins else []
        where = self._where if self._where else []
        qspec = QuerySpec(roots=self._roots,join=joins,where=where,order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(), qspec)
        return self

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self, *expressions):
        if self._orderbys:
            raise TypeError("Cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("Empty 'order_by' expression")
        self._orderbys = process_orderby(expressions,self._roots)

        # Make a query plan in case there is no other inputs
        joins = self._joins if self._joins else []
        where = self._where if self._where else []
        qspec = QuerySpec(roots=self._roots,join=joins,
                          where=where,order_by=self._orderbys)
        self._queryplan = make_query_plan(self._path2factindex.keys(), qspec)
        return self

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def query_plan(self,*args,**kwargs):
        if not args and not kwargs: return self._queryplan
        return self._queryplan.ground(*args,**kwargs)

    #--------------------------------------------------------------------------
    # Functions currently mirroring the old interface
    # --------------------------------------------------------------------------

    def get(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        join = self._joins if self._joins else []
        where = self._where if self._where else []
        order_by = self._orderbys if self._orderbys else []
        qspec = QuerySpec(roots=self._roots, join=join,
                          where=where, order_by=order_by)

        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
        return list(qo.all())

    def get_unique(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        join = self._joins if self._joins else []
        where = self._where if self._where else []
        order_by = self._orderbys if self._orderbys else []
        qspec = QuerySpec(roots=self._roots, join=join,
                          where=where, order_by=order_by)

        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
        return qo.singleton()

    def count(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        join = self._joins if self._joins else []
        where = self._where if self._where else []
        order_by = self._orderbys if self._orderbys else []
        qspec = QuerySpec(roots=self._roots, join=join,
                          where=where, order_by=order_by)

        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
        return qo.count()

#------------------------------------------------------------------------------
# The Delete class
#------------------------------------------------------------------------------

class _Delete(Delete):

    def __init__(self, factbase, root):

        ptype = path(root).meta.predicate

        if ptype not in factbase.factmaps: return
        self._factmap = factbase.factmaps[ptype]
        self._select = SelectImpl(factbase,[root])
        self._has_where = False

    def where(self, *expressions):
        self._has_where = True
        self._select.where(*expressions)
        return self

    def execute(self, *args, **kwargs):
        # If there is no where clause then delete everything
        if not self._has_where:
            num_deleted = len(self._factmap.facts())
            self._factmap.clear()
            return num_deleted

        # Gather all the facts to delete and remove them
        to_delete = [ f for f in self._select.get(*args, **kwargs) ]
        for fact in to_delete: self._factmap.remove(fact)
        return len(to_delete)





























#------------------------------------------------------------------------------
# Select V2 API
#------------------------------------------------------------------------------
class Select2Impl(object):

    def __init__(self,factbase, qspec, join_order_heuristic=None):
        self._factbase = factbase
        self._qspec = qspec
        self._join_order_heuristic = join_order_heuristic
        self._qplan = None

        self._pred2factset = {}
        self._path2factindex = {}

        ptypes = set([ root.meta.predicate for root in self._qspec.roots])
        for ptype in ptypes:
            fm =factbase.factmaps[ptype]
            self._pred2factset[ptype] = fm.factset
            for hpth, fi in fm.path2factindex.items():
                self._path2factindex[hpth] = fi

    #--------------------------------------------------------------------------
    # Overide the heuristic
    #--------------------------------------------------------------------------
    def heuristic(self, join_order):
        if self._join_order_heuristic:
            raise TypeError("Cannot specify 'heuristic' multiple times")
        self._join_order_heuristic = join_order
        self._qplan = None
        return Select2Impl(self._factbase, self._qspec, self._join_order_heuristic)


    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    def join(self, *expressions):
        if self._qspec.getp("where"):
            raise TypeError(("The 'join' condition must come before the "
                             "'where' condition"))
        if self._qspec.getp("order_by"):
            raise TypeError(("The 'join' condition must come before the "
                             "'order_by' condition"))
        if self._qspec.join:
            raise TypeError("Cannot specify 'join' multiple times")
        if not expressions:
            raise TypeError("Empty 'join' expression")

        join=process_join(expressions, self._qspec.roots)
        return Select2Impl(self._factbase, self._qspec.newp(join=join))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
        if self._qspec.getp("order_by"):
            raise TypeError(("The 'where' condition must come before the "
                             "'order_by' condition"))
        if self._qspec.getp("where"):
            raise TypeError("Cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("Empty 'where' expression")
        elif len(expressions) == 1:
            where = process_where(expressions[0],self._qspec.roots)
        else:
            where = process_where(and_(*expressions),self._qspec.roots)

        return Select2Impl(self._factbase, self._qspec.newp(where=where))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self, *expressions):
        if self._qspec.order_by:
            raise TypeError("Cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("Empty 'order_by' expression")
        order_by = process_orderby(expressions,self._qspec.roots)
        return Select2Impl(self._factbase,self._qspec.newp(order_by=order_by))

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def query_plan(self,*args,**kwargs):
        if not self._qplan:
            self._qplan = make_query_plan(self._path2factindex.keys(),
                                          self._qspec)

        if not args and not kwargs: return self._qplan
        return self._qplan.ground(*args,**kwargs)

    #--------------------------------------------------------------------------
    # Functions currently mirroring the old interface
    # --------------------------------------------------------------------------

    def run(self, *args, **kwargs):

        # NOTE: a limitation of the current implementation of FunctionComparator
        # means that I have to call ground() to make the assignment valid. Need
        # to look at this.

        qplan = self.query_plan()
        gqplan = qplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        return QueryOutput(self._factbase.factmaps,self._qspec,gqplan,query)

























#------------------------------------------------------------------------------
# New Clorm Query API
#
# QueryImpl
# - factmaps             - dictionary mapping predicate types to FactMap objects
# - qspec                - a dictionary with query parameters
#------------------------------------------------------------------------------
class QueryImpl(object):

    def __init__(self, factmaps, roots=None, qspec={}):
        def root_path(p):
            p = path(p)
            if not p.is_root:
                raise ValueError(("Non-root path '{}' in query roots "
                                  "specification '{}'").format(p,roots))

        self._factmaps = factmaps
        if roots is None and qspec:
            raise ValueError(("Internal error: cannot specify 'roots' and "
                              "'qspec' together"))
        if roots is not None:
            roots = ( root_path(r) for r in roots )
            self._qspec = { 'roots' : roots }
        else:
            self._qspec = dict(qspec)

    #--------------------------------------------------------------------------
    # Internal function to test whether a function has been called and add it
    #--------------------------------------------------------------------------
    def _setp(self, name, value):
        if value is None:
            raise ValueError("Cannot specify empty '{}'".format(name))
        if name in self._qspec:
            raise ValueError("Cannot specify '{}' multiple times".format(name))
        nqspec = dict(self._qspec)
        nqspec[name] = value
        return nqspec

    def _modp(self, name, value):
        nqspec = dict(self._qspec)
        nqspec[name] = value
        return nqspec

    def _getp(self, name,default=None):
        return self.qspec.get(name,default)

    def _check_join_first(self, name):
        if len(self._getp['roots']) == 1: return True
        if "join" not in nqspec:
            raise ValueError("'join' must be specified before '{}'".format(name))
        return True

    #--------------------------------------------------------------------------
    # Overide the default heuristic
    #--------------------------------------------------------------------------
    def heuristic(self, join_order):
        nqspec = self._setp("heuristic", join_order)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    def join(self, *expressions):
        nqspec = self._setp("join",
                            process_join(expressions, self._getp["roots"]))
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
        self._check_join_first("where")
        roots = self._getp["roots"]
        if not expressions:
            self._setp("where", None)
        if len(expressions) == 1:
            where = process_where(expressions[0], roots)
        else:
            where = process_where(and_(*expressions), roots)

        nqspec = self._setp("where", where)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self, *expressions):
        self._check_join_first("order_by")
        if not expressions:
            nqspec = self._setp("order_by", None)
        else:
            nqspec = self._setp("order_by",
                                process_orderby(expressions,self._getp["roots"]))
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Add a group_by expression
    #--------------------------------------------------------------------------
    def group_by(self, grouping=1):
        self._check_join_first("group_by")
        order_by = self._getp("order_by")
        if order_by is None:
            raise ValueError("'order_by' must be set before 'group_by'")
        if grouping <= 0:
            raise ValueError("The grouping must be a positive integer")
        if grouping > len(order_by):
            raise ValueError(("The grouping size {} cannot be larger than the "
                              "order_by() specification "
                              "'{}'").format(grouping,self._qspec.order_by))

        nqspec = self._setp("group_by",
                            [ob.path for ob in self._getp["order_by"][:grouping]])
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # The tuple flag
    #--------------------------------------------------------------------------
    def tuple(self):
        self._check_join_first("tuple")
        nqspec = self._setp("tuple", True)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # The unique flag
    #--------------------------------------------------------------------------
    def unique(self):
        self._check_join_first("unique")
        nqspec = self._setp("unique", True)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Ground
    #--------------------------------------------------------------------------
    def ground(self,*args,**kwargs):
        self._check_join_first("ground")

        nqspec = self._setp("ground", True)
        where = self._getp("where")
        if not where:
            raise ValueError(("Cannot 'ground' a query when no 'where' "
                              "condition has been set"))
        nqspec = self._modp("where", where.ground(*args,**kwargs))
        return QueryImpl(self._factmaps, self._roots, nqspec)

    #--------------------------------------------------------------------------
    # Support function
    #--------------------------------------------------------------------------
    def _get_facts_data(self):
        ptypes = set([ r.meta.predicate for r in self._roots])
        factsets = {}
        indexes = {}
        for ptype in ptypes:
            fm =self_.factmaps[ptype]
            factsets[ptype] = fm.factset
            for hpth, fi in fm.path2factindex.items(): indexes[hpth] = fi
        return (factsets,indexes)

    def _get_query_plan_spec(self):
        join = self._getp("join",[])
        where = self._getp("where",[])
        order_by = self._getp("order_by",[])
        return QuerySpec(roots=self._roots,join=join,where=where,order_by=order_by)

    def _get_query_output(self):
        qpspec = self._get_query_plan_spec()

    #--------------------------------------------------------------------------
    # End points
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # For the user to see what the query plan looks like
    #--------------------------------------------------------------------------
    def query_plan():
        self._check_join_first("query_plan")
        return QueryExecutor.make_query_plan(self._factmaps, self._qspec)

    #--------------------------------------------------------------------------
    # Select to display all the output of the query
    # --------------------------------------------------------------------------
    def select(self, *outsig):
        self._check_join_first("select")

        if outsig:
            qspec = self._setp("outsig", outsig)
        else:
            qspec = self._qspec

        qe = QueryExecutor(self._factmaps, qspec)
        return qe.all()

    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    def singleton(self, *outsig):
        self._check_join_first("singleton")

        if outsig:
            qspec = self._setp("outsig", outsig)
        else:
            qspec = self._qspec

        qe = QueryExecutor(self._factmaps, qspec)

        found = None
        for out in qe.all():
            if found: raise ValueError("Query returned more than a single element")
            found = out
        return found

    #--------------------------------------------------------------------------
    # Return the count of elements
    # --------------------------------------------------------------------------
    def count(self):
        self._check_join_first("count")
        qe = QueryExecutor(self._factmaps, self._qspec)
        return len(list(qe.all()))


    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    def first(self, *outsig):
        self._check_join_first("first")

        if outsig:
            qspec = self._setp("outsig", tuple(outsig))
        else:
            qspec = self._qspec

        qe = QueryExecutor(self._factmaps, qspec)
        return next(iter(qe.all()))

    #--------------------------------------------------------------------------
    # Delete a selection of fact
    #--------------------------------------------------------------------------
    def delete(self,*subroots):
        self._check_join_first("delete")

        if subroots:
            qspec = self._setp("", outsig)
        else:
            qspec = self._qspec

        qe = QueryExecutor(self._factmaps, qspec)
        return qe.delete()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
