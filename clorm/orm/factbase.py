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
from .core import get_field_definition, PredicatePath, kwargs_check_keys

from .queryplan import *

from .queryplan import Placeholder, OrderBy, desc, asc

from .queryplan import JoinQueryPlan, QueryPlan, \
    process_where, process_join, process_orderby, \
    make_input_alignment_functor, basic_join_order_heuristic, make_query_plan,\
    FuncInputSpec, FunctionComparator, QuerySpec, modify_query_spec

# ------------------------------------------------------------------------------
# In order to implement FactBase I originally used the built in 'set'
# class. However this uses the hash value, which for Predicate instances uses
# the underlying clingo.Symbol.__hash__() function. This in-turn depends on the
# c++ std::hash function. Like the Python standard hash function this uses
# random seeds at program startup which means that between successive runs of
# the same program the ordering of the set can change. This is bad for producing
# deterministic ASP solving. So using an OrderedSet instead.

from ..util import OrderedSet as _FactSet

#_FactSet=set                                # The Python standard set class. Note
                                           # fails some unit tests because I'm
                                           # testing for the ordering.

# Note: Some other 3rd party libraries that were tried but performed worse on
# a basic FactBase creation process:
#
#from ordered_set import OrderedSet as _FactSet

#from orderedset import OrderedSet as _FactSet   # Note: broken implementation so
                                               # fails some unit tests - union
                                               # operator only accepts a single
                                               # argument

#from blist import sortedset as _FactSet
#from sortedcontainers import SortedSet as _FactSet
# ------------------------------------------------------------------------------

__all__ = [
    'FactBase',
    'Select',
    'Delete',
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# FactIndex indexes facts by a given field
#------------------------------------------------------------------------------

class FactIndex(object):
    def __init__(self, path):
        try:
            self._path = path
            self._predicate = self._path.meta.predicate
            self._keylist = []
            self._key2values = {}
        except:
            raise TypeError("{} is not a valid PredicatePath object".format(path))

    @property
    def path(self):
        return self._path

    def add(self, fact):
        if not isinstance(fact, self._predicate):
            raise TypeError("{} is not a {}".format(fact, self._predicate))
        key = self._path(fact)

        # Index the fact by the key
        if key not in self._key2values: self._key2values[key] = set()
        self._key2values[key].add(fact)

        # Maintain the sorted list of keys
        posn = bisect.bisect_left(self._keylist, key)
        if len(self._keylist) > posn and self._keylist[posn] == key: return
        bisect.insort_left(self._keylist, key)

    def discard(self, fact):
        self.remove(fact, False)

    def remove(self, fact, raise_on_missing=True):
        if not isinstance(fact, self._predicate):
            raise TypeError("{} is not a {}".format(fact, self._predicate))
        key = self._path(fact)

        # Remove the value
        if key not in self._key2values:
            if raise_on_missing:
                raise KeyError("{} is not in the FactIndex".format(fact))
            return
        values = self._key2values[key]
        if raise_on_missing: values.remove(fact)
        else: values.discard(fact)

        # If still have values then we're done
        if values: return

        # remove the key
        del self._key2values[key]
        posn = bisect.bisect_left(self._keylist, key)
        del self._keylist[posn]

    def clear(self):
        self._keylist = []
        self._key2values = {}

    @property
    def keys(self): return self._keylist

    #--------------------------------------------------------------------------
    # Internal functions to get keys matching some boolean operator
    #--------------------------------------------------------------------------

    def _keys_eq(self, key):
        if key in self._key2values: return [key]
        return []

    def _keys_ne(self, key):
        posn1 = bisect.bisect_left(self._keylist, key)
        if posn1: left =  self._keylist[:posn1]
        else: left = []
        posn2 = bisect.bisect_right(self._keylist, key)
        if posn2: right = self._keylist[posn2:]
        else: right = []
        return left + right

    def _keys_lt(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def _keys_le(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def _keys_gt(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    def _keys_ge(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    #--------------------------------------------------------------------------
    # Find elements based on boolean match to a key
    #--------------------------------------------------------------------------
    def find(self, op, key):
        keys = []
        if op == operator.eq: keys = self._keys_eq(key)
        elif op == operator.ne: keys = self._keys_ne(key)
        elif op == operator.lt: keys = self._keys_lt(key)
        elif op == operator.le: keys = self._keys_le(key)
        elif op == operator.gt: keys = self._keys_gt(key)
        elif op == operator.ge: keys = self._keys_ge(key)
        else: raise ValueError("unsupported operator {}".format(op))

        for k in keys:
            for fact in self._key2values[k]:
                yield fact

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------

    def __str__(self):
        if not self: return "{}"
        tmp = []
        for k,v in self._key2values.items(): tmp.extend(v)
        return "{" + ", ".join([repr(f) for f in tmp]) + "}"

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# A helper function to determine if two collections have the same elements
# (irrespective of ordering). This is useful if the underlying objects are two
# OrderedSet objects since the equality operator will also test for the same
# ordering which is something we don't want.
# ------------------------------------------------------------------------------

def _is_set_equal(s1,s2):
    if len(s1) != len(s2): return False
    for elem in s1:
        if elem not in s2: return False
    return True

#------------------------------------------------------------------------------
# A map for facts of the same type - Indexes can be built to allow for fast
# lookups based on a field value. The order that the fields are specified in the
# index matters as it determines the priority of the index.
# ------------------------------------------------------------------------------

class FactMap(object):
    def __init__(self, ptype, indexes=[]):
        self._ptype = ptype
        self._factset = _FactSet()
        self._path2factindex = {}
        self._factindexes = []

        # Validate the paths to be indexed
        allindexes = set([hashable_path(p) for p in indexes])
        for pth in allindexes:
            tmppath=path(pth)
            if hashable_path(tmppath.meta.dealiased) != hashable_path(tmppath):
                raise ValueError(("Cannot create an index for an alias path "
                                  "'{}'").format(tmppath))
            if tmppath.meta.predicate != ptype:
                raise ValueError(("Index path '{}' isn't a sub-path of Predicate "
                                  "'{}'").format(tmppath, path(ptype)))
            tmpfi = FactIndex(tmppath)
            self._path2factindex[hashable_path(tmppath)] = tmpfi
            self._factindexes.append(tmpfi)
        self._factindexes = tuple(self._factindexes)

    def add_facts(self, facts):
        for f in facts:
            self._factset.add(f)
            for fi in self._factindexes: fi.add(f)

    def add_fact(self, fact):
        self._factset.add(fact)
        for fi in self._factindexes: fi.add(fact)

    def discard(self,fact):
        self.remove(fact,False)

    def remove(self,fact, raise_on_missing=True):
        if raise_on_missing: self._factset.remove(fact)
        else: self._factset.discard(fact)
        for fi in self._factindexes:
            fi.remove(fact,raise_on_missing)

    def pop(self):
        if not self._factset: raise KeyError("Cannot pop() an empty set of facts")
        fact = next(iter(self._factset))
        self.remove(fact)
        return fact

    def clear(self):
        self._factset.clear()
        for fi in self._factindexes: fi.clear()

    @property
    def predicate(self):
        return self._ptype

    @property
    def factset(self):
        return self._factset

    @property
    def path2factindex(self):
        return self._path2factindex

    def __bool__(self):
        return bool(self._factset)

    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [o.factset for o in others]
        tmp = self.factset.union(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def intersection(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [o.factset for o in others]
        tmp = self.factset.intersection(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def difference(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [o.factset for o in others]
        tmp = self.factset.difference(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def symmetric_difference(self,other):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmp = self.factset.symmetric_difference(other.factset)
        nfm.add_facts(tmp)
        return nfm

    def update(self,*others):
        self.add_facts(itertools.chain(*[o.factset for o in others]))

    def intersection_update(self,*others):
        for f in set(self.factset):
            for o in others:
                if f not in o.factset: self.discard(f)

    def difference_update(self,*others):
        for f in itertools.chain(*[o.factset for o in others]):
            self.discard(f)

    def symmetric_difference_update(self, other):
        to_remove=set()
        to_add=set()
        for f in self._factset:
            if f in other._factset: to_remove.add(f)
        for f in other._factset:
            if f not in self._factset: to_add.add(f)
        for f in to_remove: self.discard(f)
        self.add_facts(to_add)

    def copy(self):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        nfm.add_facts(self.factset)
        return nfm

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

    def select2(self, *roots):
        """Create a Select query for a predicate type."""
        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = set([r.meta.predicate for r in validate_root_paths(roots)])
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return Select2Impl(self, QuerySpec(tuple(validate_root_paths(roots)),
                                           None,None,None))


    def delete(self, *ptypes):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = [p.meta.predicate for p in validate_root_paths(ptypes)]
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))
        return DeleteImpl(self, [path(pt) for pt in ptypes], ptypes)


    def dfrom(self, *roots):

        """Create a complex delete query."""
        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        roots = [r in validate_root_paths(roots)]
        ptypes = set([r.meta.predicate for r in roots])
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        class DeleteFrom(object):
            def __init__(self, factbase,roots): self._input=(factbase,roots)
            def delete(self, *ptypes): return DeleteImpl(*self._input, roots, ptypes)
        return DeleteFrom()

    def delete_from(self, ptypes, roots):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = [p.meta.predicate for p in validate_root_paths(roots)]
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return DeleteImpl(self, ptypes, roots)

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
            if not _is_set_equal(fm1.factset,fm2.factset): return False

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
# Implementing Queries - the abstraction underneath Select and Delete
# statements.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# prejoin query is the querying of the underlying factset or factindex
# ------------------------------------------------------------------------------

def make_prejoin_query(jqp, predicate_to_factset, hpath_to_factindex):
    factset = predicate_to_factset.get(jqp.root.meta.predicate, _FactSet())
    prejsc = jqp.prejoin_key
    prejcb = jqp.prejoin_clauses
    factindex = None
    if prejsc:
        factindex=hpath_to_factindex.get(hashable_path(prejsc.args[0]),None)
        if not factindex:
            raise ValueError(("Internal error: missing FactIndex for "
                              "path '{}'").format(prejsc.args[0]))

    # Iterate over the factset or the factindex find
    def base():
        if factindex: return factindex.find(prejsc.operator,prejsc.args[1])
        else: return iter(factset)

    def query_without_prejcb():
        for f in base(): yield (f,)

    def query_with_prejcb():
        cc = prejcb.make_callable([jqp.root])
        for f in base():
            if cc((f,)): yield (f,)

    if prejcb: return query_with_prejcb
    else: return query_without_prejcb

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------

def make_first_join_query(jqp, predicate_to_factset, hpath_to_factindex):

    if jqp.input_signature:
        raise ValueError(("A first JoinQueryPlan must have an empty input "
                          "signature but '{}' found").format(jqp.input_signature))

    base_query=make_prejoin_query(jqp,predicate_to_factset, hpath_to_factindex)
    def sorted_query():
        orderby_cmp = jqp.join_orderbys.make_cmp([jqp.root])
        return sorted(base_query(),key=functools.cmp_to_key(orderby_cmp))

    if jqp.join_orderbys: return sorted_query
    else: return base_query

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------

def make_chained_join_query(jqp, inquery,
                            predicate_to_factset, hpath_to_factindex):

    if not jqp.input_signature:
        raise ValueError(("A non-first JoinQueryPlan must have a non-empty input "
                          "signature but '{}' found").format(jqp.input_signature))

    prejoin_query = make_prejoin_query(jqp,predicate_to_factset, hpath_to_factindex)

    jsc = jqp.join_key
    jcb = jqp.join_clauses

    if jsc:
        source = FactIndex(jsc.args[0])
        operator = jsc.operator
        align_query_input = make_input_alignment_functor(
            jqp.input_signature,(jsc.args[1],))
    else:
        source = _FactSet()
    for (f,) in prejoin_query(): source.add(f)

    if jcb:
        jcbcc = jcb.make_callable(list(jqp.input_signature) + [jqp.root])

    # Return a different query depending on the inputs
    def query_factset_with_jcb():
        for intuple in inquery():
            for f in source:
                out = tuple(intuple + (f,))
                if jcbcc(out): yield out

    def query_factindex_with_jcb():
        for intuple in inquery():
            v, = align_query_input(intuple)
            for f in source.find(operator,v):
                out = tuple(intuple + (f,))
                if jcbcc(out): yield out

    def query_factset_without_jcb():
        for intuple in inquery():
            for f in source:
                yield tuple(intuple + (f,))

    def query_factindex_without_jcb():
        for intuple in inquery():
            v, = align_query_input(intuple)
            for f in source.find(operator,v):
                yield tuple(intuple + (f,))


    if jcb and isinstance(source,_FactSet): outquery=query_factset_with_jcb
    elif jcb and isinstance(source,FactIndex): outquery=query_factindex_with_jcb
    elif not jcb and isinstance(source,_FactSet): outquery=query_factset_without_jcb
    elif not jcb and isinstance(source,FactIndex): outquery=query_factindex_without_jcb

    def sorted_outquery():
        tmp = list(jqp.input_signature) + [jqp.root]
        orderby_cmp = jqp.join_orderbys.make_cmp(tmp)
        return sorted(outquery(),key=functools.cmp_to_key(orderby_cmp))

    if jqp.join_orderbys: return sorted_outquery
    else: return outquery

#------------------------------------------------------------------------------
# Makes a query given a ground QueryPlan and the underlying data. The returned
# query object is a Python generator function that takes no arguments.
# ------------------------------------------------------------------------------

def make_query(qp, predicate_to_factset, hpath_to_factindex):
    if qp.placeholders:
        raise ValueError(("Cannot execute an ungrounded query. Missing values "
                          "for placeholders: "
                          "{}").format(", ".join([str(p) for p in qp.placeholders])))
    query = None
    for idx,jqp in enumerate(qp):
        if not query:
            query = make_first_join_query(
                jqp,predicate_to_factset,hpath_to_factindex)
        else:
            query = make_chained_join_query(
                jqp,query,predicate_to_factset,hpath_to_factindex)
    return query



#------------------------------------------------------------------------------
# Helper function to check if all the paths in a collection are root paths and
# return path objects.
# ------------------------------------------------------------------------------
def validate_root_paths(paths):
    def checkroot(p):
        p = path(p)
        if not p.meta.is_root:
            raise ValueError("'{}' in '{}' is not a root path".format(p,paths))
        return p
    return list(map(checkroot,paths))


#------------------------------------------------------------------------------
# QueryOutput allows you to output the results of a Select query it different
# ways.
# ------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Given an input tuple of facts generate the appropriate output. Depending on
# the output signature what we want to generate this can be a simple of a
# complex operation. If it is just predicate paths or static values then a
# simple outputter is ok, but if it has a function then a complex one is needed.
# ------------------------------------------------------------------------------

def make_outputter(insig,outsig):

    def make_simple_outputter():
        af=make_input_alignment_functor(insig, outsig)
        return lambda intuple, af=af: af(intuple)

    def make_complex_outputter():
        metasig = []
        for out in outsig:
            if isinstance(out,PredicatePath) or \
                 (inspect.isclass(out) and issubclass(out,Predicate)):
                tmp = make_input_alignment_functor(insig, (path(out),))
                metasig.append(lambda x,af=tmp: af(x)[0])
            elif isinstance(out,FuncInputSpec):
                tmp=make_input_alignment_functor(insig, out.paths)
                metasig.append(lambda x,af=tmp,f=out.functor: f(*af(x)))
            elif callable(out):
                metasig.append(lambda x,f=out: f(*x))
            else:
                metasign.append(lambda x, out=out: out)

        maf=tuple(metasig)
        return lambda intuple, maf=maf: tuple(af(intuple) for af in maf)

    needcomplex=False
    for out in outsig:
        if isinstance(out,PredicatePath) or \
           (inspect.isclass(out) and issubclass(out,Predicate)):
            continue
        elif isinstance(out,FuncInputSpec) or callable(out):
            needcomplex=True
            break

    if needcomplex: return make_complex_outputter()
    else: return make_simple_outputter()

class QueryOutput(object):

    #--------------------------------------------------------------------------
    # factbase - the underlying factbase. Needed for the delete() function
    # query - the results generator function
    #--------------------------------------------------------------------------
    def __init__(self, factbase, query_spec, query_plan, query):
        self._factbase = factbase
        self._qspec = query_spec
        self._qplan = query_plan
        self._query = query
        self._unique = False
        self._sigoverride = False
        self._tuple_called = False
        self._grouping = None
        self._unwrap = len(self._qplan.output_signature) == 1

        self._outputter = make_outputter(self._qplan.output_signature,
                                         self._qspec.roots)
        self._executed = False



    #--------------------------------------------------------------------------
    # Functions to modify the output
    #--------------------------------------------------------------------------

    def tuple(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._tuple_called:
            raise ValueError("tuple() can only be specified once")
        self._tuple_called = True
        self._unwrap = False
        return self

    def unique(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._unique:
            raise ValueError("unique() can only be specified once")
        self._unique = True
        return self

    def output(self, *outsig):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if not outsig:
            raise ValueError("Empty output signature")
        if self._sigoverride:
            raise ValueError("output() can only be specified once")
        self._sigoverride = True

        if not self._tuple_called:
            self._unwrap = len(outsig) == 1

        tmp = tuple(outsig)

        self._outputter = make_outputter(self._qplan.output_signature,tmp)
        return self

    def group_by(self,grouping=1):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._grouping:
            raise ValueError("group_by() can only be specified once")

        if not self._qspec.order_by:
            raise ValueError(("group_by() can only be specified in conjunction "
                              "with order_by() in the query"))
        if grouping <= 0:
            raise ValueError("The grouping must be a positive integer")
        if grouping > len(self._qspec.order_by):
            raise ValueError(("The grouping size {} cannot be larger than the "
                              "order_by() specification "
                              "'{}'").format(grouping,self._qspec.order_by))

        self._grouping = [ob.path for ob in self._qspec.order_by[:grouping]]
        return self

    # --------------------------------------------------------------------------
    # Internal function generator for the query results
    # --------------------------------------------------------------------------
    def _all(self):
        cache = set()
        for input in self._query():
            output = self._outputter(input)
            if self._unwrap: output = output[0]
            if self._unique:
                if output not in cache:
                    cache.add(output)
                    yield output
            else:
                yield output

    def _group_by_all(self):
        def groupiter(group):
            cache = set()
            for input in group:
                output = self._outputter(input)
                if self._unwrap: output = output[0]
                if self._unique:
                    if output not in cache:
                        cache.add(output)
                        yield output
                else:
                    yield output

        unwrapkey = len(self._grouping) == 1 and not self._tuple_called

        group_by_keyfunc = make_input_alignment_functor(
            self._qplan.output_signature, self._grouping)
        for k,g in itertools.groupby(self._query(), group_by_keyfunc):
            if unwrapkey: yield k[0], groupiter(g)
            else: yield k, groupiter(g)


    #--------------------------------------------------------------------------
    # Functions to get the output - only one of these functions can be called
    # for a QueryOutput instance.
    # --------------------------------------------------------------------------

    def all(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        self._executed = True
        if self._grouping: return self._group_by_all()
        else: return self._all()

    def singleton(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._grouping:
            raise RuntimeError(("Returning a singleton() cannot be used in "
                                "conjunction with group_by()"))
        self._executed = True

        found = None
        for out in self._all():
            if found: raise ValueError("Query returned more than a single element")
            found = out
        return found

    def count(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._grouping:
            raise RuntimeError(("Returning count() cannot be used in "
                                "conjunction with group_by()"))
        self._executed = True
        return len(list(self._all()))

    def first(self):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._grouping:
            raise RuntimeError(("Returning first() cannot be used in "
                                "conjunction with group_by()"))
        self._executed = True
        return next(iter(self._all()))

    # --------------------------------------------------------------------------
    # Delete a selection of facts. Maintains a set for each predicate type
    # and adds the selected fact to that set. The delete the facts in each set.
    # --------------------------------------------------------------------------

    def delete(self,*subroots):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._grouping:
            raise RuntimeError(("delete() cannot be used in "
                                "conjunction with group_by()"))
        self._executed = True

        roots = set([hashable_path(p) for p in self._qspec.roots])
        subroots = set([hashable_path(p) for p in validate_root_paths(subroots)])

        if not subroots.issubset(roots):
            raise ValueError(("The roots to delete '{}' must be a subset of "
                              "the query roots '{}").format(subroots,roots))
        if not subroots: subroots = roots

        # Find the roots to delete and generate a set of actions that are
        # executed to add to a delete set
        deletesets = {}
        for r in subroots:
            pr = path(r)
            deletesets[pr.meta.predicate] = set()

        actions = []
        for out in self._qplan.output_signature:
            hout = hashable_path(out)
            if hout in subroots:
                ds = deletesets[out.meta.predicate]
                actions.append(lambda x, ds=ds: ds.add(x))
            else:
                actions.append(lambda x : None)

        for input in self._query():
            for fact, action in zip(input,actions):
                action(fact)

        for pt,ds in deletesets.items():
            fm = self._factbase.factmaps[pt]
            for f in ds: fm.discard(f)


    # --------------------------------------------------------------------------
    # Overload to make an iterator
    # --------------------------------------------------------------------------
    def __iter__(self):
        return self.all()


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

    @abc.abstractmethod
    def get_unique(self, *args, **kwargs):
        """Return the single matching entry. Raises ValueError otherwise."""
        pass

    @abc.abstractmethod
    def count(self, *args, **kwargs):
        """Return the number of matching entries."""
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
# Select V2 query engine with V1 API
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

        qspec = QuerySpec(self._roots,[],[],[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(), qspec)


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
        qspec = QuerySpec(self._roots,self._joins,[],[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(), spec)
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
        qspec = QuerySpec(self._roots,joins,where,[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(), qspec)
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
        qspec = QuerySpec(self._roots,joins,where,self._orderbys)
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(), qspec)
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

        qspec = QuerySpec(self._roots, self._joins, self._where, self._orderbys)
        qo = QueryOutput(self._factbase,qspec,gqplan,query)
        return list(qo.all())

    def get_unique(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        qspec = QuerySpec(self._roots, self._joins, self._where, self._orderbys)
        qo = QueryOutput(self._factbase,qspec,gqplan,query)
        return qo.singleton()

    def count(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        qspec = QuerySpec(self._roots, self._joins, self._where, self._orderbys)
        qo = QueryOutput(self._factbase,qspec,gqplan,query)
        return qo.count()

#------------------------------------------------------------------------------
# The Delete class
#------------------------------------------------------------------------------

class DeleteImpl(Delete):

    def __init__(self, factbase, roots, todelete):
        def _setof(paths): return set([hashable_path(p) for p in paths])

        self._factbase = factbase

        if not roots: raise ValueError("Empty list of root paths")
        if not todelete: raise ValueError("Empty predicate delete list")

        # Allow flexiblity in case the predicate types to delete are passed as
        # paths - but cannot pass an alias.
        self._todelete = tuple(validate_root_paths(todelete))
        for ppath in self._todelete:
            if hashable_path(ppath.meta.dealiased) != hashable_path(ppath):
                raise ValueError(("Cannot delete aliased facts '{}'").format(ppath))

        # todelete must be a subset of roots
        self._roots = tuple(validate_root_paths(roots))
        if not _setof(self._todelete).issubset(_setof(self._roots)):
                raise ValueError(("The predicates to delete '{}' must "
                                  "be a subset of the selected roots "
                                  "'{}'").format(self._todelete, self._roots))
        self._where = None
        self._joins = None
        self._pred2factset = {}
        self._path2factindex = {}

        for ptype in [r.meta.predicate for r in self._roots]:
            fm =factbase.factmaps[ptype]
            self._pred2factset[ptype] = fm.factset
            for hpth, fi in fm.path2factindex.items():
                self._path2factindex[hpth] = fi

        qspec = QuerySpec(self._roots,[],[],[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(),qspec)

    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    def join(self, *expressions):
        if self._where:
            raise TypeError(("The 'join' condition must come before the "
                             "'where' condition"))
        if self._joins:
            raise TypeError("Cannot specify 'join' multiple times")
        if not expressions:
            raise TypeError("Empty 'join' expression")
        self._joins = process_join(expressions, self._roots)

        # Make a query plan in case there is no other inputs
        qspec = QuerySpec(self._roots,self._joins,[],[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(),qspec)
        return self

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
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
        qspec = QuerySpec(self._roots,joins,where,[])
        self._queryplan = make_query_plan(basic_join_order_heuristic,
                                          self._path2factindex.keys(),qspec)
        return self

    #--------------------------------------------------------------------------
    # Functions currently mirroring the old interface
    # --------------------------------------------------------------------------

    def execute(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        # Make an alignment of the roots to the todelete
        align_qin = make_input_alignment_functor(self._roots, self._todelete)

        # Build sets of facts to delete associated by ptype
        to_delete = tuple([ set() for ptype in self._todelete ])
        for intuple in query():
            for idx, f in enumerate(align_qin(intuple)):
                to_delete[idx].add(f)

        # Delete the facts
        count=0
        for ppath in self._todelete:
            factmap = self._factbase.factmaps[ppath.meta.predicate]
            for f in to_delete[idx]:
                count+= 1
                factmap.discard(f)
        return count

#------------------------------------------------------------------------------
# Select V2 API
#------------------------------------------------------------------------------
class Select2Impl(object):

    def __init__(self,factbase, queryspec,join_order_heuristic=None):
        self._factbase = factbase
        self._qspec = queryspec
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
        if self._qspec.where:
            raise TypeError(("The 'join' condition must come before the "
                             "'where' condition"))
        if self._qspec.order_by:
            raise TypeError(("The 'join' condition must come before the "
                             "'order_by' condition"))
        if self._qspec.join:
            raise TypeError("Cannot specify 'join' multiple times")
        if not expressions:
            raise TypeError("Empty 'join' expression")

        join=process_join(expressions, self._qspec.roots)
        return Select2Impl(self._factbase,
                           modify_query_spec(self._qspec, join=join))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
        if self._qspec.order_by:
            raise TypeError(("The 'where' condition must come before the "
                             "'order_by' condition"))
        if self._qspec.where:
            raise TypeError("Cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("Empty 'where' expression")
        elif len(expressions) == 1:
            where = process_where(expressions[0],self._qspec.roots)
        else:
            where = process_where(and_(*expressions),self._qspec.roots)

        return Select2Impl(self._factbase,
                           modify_query_spec(self._qspec, where=where))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self, *expressions):
        if self._qspec.order_by:
            raise TypeError("Cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("Empty 'order_by' expression")
        order_by = process_orderby(expressions,self._qspec.roots)

        return Select2Impl(self._factbase,
                           modify_query_spec(self._qspec, order_by=order_by))

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def query_plan(self,*args,**kwargs):
        if not self._qplan:
            joh = basic_join_order_heuristic
            if self._join_order_heuristic: joh = self._join_order_heuristic
            self._qplan = make_query_plan(joh, self._path2factindex.keys(),
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

        return QueryOutput(self._factbase,self._qspec,gqplan,query)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
