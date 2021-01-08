# -----------------------------------------------------------------------------
# Clorm ORM FactBase implementation. FactBase provides a set-like container
# specifically for storing facts (Predicate instances).
# ------------------------------------------------------------------------------

import io
import operator
import collections
import bisect
import abc
import functools
import itertools

from .core import *
from .core import get_field_definition, PredicatePath, kwargs_check_keys

from .query import *
from .query import Placeholder, check_query_condition, simplify_query_condition, \
    instantiate_query_condition, evaluate_query_condition, SelectImpl, DeleteImpl

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
    'FactBase'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# _FactIndex indexes facts by a given field
#------------------------------------------------------------------------------

class _FactIndex(object):
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

        sets = [ self._key2values[k] for k in keys ]
        if not sets: return set()
        return set.union(*sets)

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

class _FactMap(object):
    def __init__(self, ptype, indexes=[]):
        self._ptype = ptype
        self._allfacts = _FactSet()

        self._findexes = None
        self._indexes = ()
        if not issubclass(ptype, Predicate):
            raise TypeError("{} is not a subclass of Predicate".format(ptype))
        if indexes:
            self._indexes = tuple(indexes)
            self._findexes = collections.OrderedDict(
                (p.meta.hashable, _FactIndex(p)) for p in self._indexes )
            preds = set([p.meta.predicate for p in self._indexes])
            if len(preds) != 1 or preds != set([ptype]):
                raise TypeError("Fields in {} do not belong to {}".format(indexes,preds))

    def _add_fact(self,fact):
        self._allfacts.add(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.add(fact)

    def add(self, arg):
        if isinstance(arg, Predicate): return self._add_fact(arg)
        for f in arg: self._add_fact(f)

    def discard(self, fact):
        self.remove(fact, False)

    def remove(self, fact, raise_on_missing=True):
        if raise_on_missing: self._allfacts.remove(fact)
        else: self._allfacts.discard(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.remove(fact,raise_on_missing)

    @property
    def predicate(self):
        return self._ptype

    @property
    def indexes(self):
        return self._indexes

    def get_factindex(self, path):
        return self._findexes[path.meta.hashable]

    def facts(self):
        return self._allfacts

    def clear(self):
        self._allfacts.clear()
        if self._findexes:
            for f, findex in self._findexes.items(): findex.clear()

    def select(self):
        return SelectImpl(self)

    def delete(self):
        return DeleteImpl(self)

    def asp_str(self):
        out = io.StringIO()
        for f in self._allfacts:
            print("{}.".format(f), file=out)
        data = out.getvalue()
        out.close()
        return data

    def pop(self):
        if not self._allfacts: raise KeyError("Cannot pop() an empty _FactMap")
        fact = next(iter(self._allfacts))
        self.remove(fact)
        return fact

    def __str__(self):
        return self.asp_str()

    def __repr__(self):
        return self.__str__()

    #--------------------------------------------------------------------------
    # Special functions to support container operations
    #--------------------------------------------------------------------------

    def __contains__(self, fact):
        if not isinstance(fact, self._ptype): return False
        return fact in self._allfacts

    def __bool__(self):
        return bool(self._allfacts)

    def __len__(self):
        return len(self._allfacts)

    def __iter__(self):
        return iter(self._allfacts)

    def __eq__(self,other):
        return _is_set_equal(self._allfacts,other._allfacts)

    def __ne__(self,other):
        return not _is_set_equal(self._allfacts,other._allfacts)

    def __lt__(self,other):
        return self._allfacts < other._allfacts

    def __le__(self,other):
        return self._allfacts <= other._allfacts

    def __gt__(self,other):
        return self._allfacts > other._allfacts

    def __ge__(self,other):
        return self._allfacts >= other._allfacts


    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().union(*tmpothers)
        nfm.add(tmp)
        return nfm

    def intersection(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().intersection(*tmpothers)
        nfm.add(tmp)
        return nfm

    def difference(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().difference(*tmpothers)
        nfm.add(tmp)
        return nfm

    def symmetric_difference(self,other):
        nfm = _FactMap(self.predicate, self.indexes)
        tmp = self.facts().symmetric_difference(other)
        nfm.add(tmp)
        return nfm

    def update(self,*others):
        for f in itertools.chain(*[o.facts() for o in others]):
            self._add_fact(f)

    def intersection_update(self,*others):
        for f in set(self.facts()):
            for o in others:
                if f not in o: self.discard(f)

    def difference_update(self,*others):
        for f in itertools.chain(*[o.facts() for o in others]):
            self.discard(f)

    def symmetric_difference_update(self, other):
        to_remove=set()
        to_add=set()
        for f in self._allfacts:
            if f in other._allfacts: to_remove.add(f)
        for f in other._allfacts:
            if f not in self._allfacts: to_add.add(f)
        for f in to_remove: self.discard(f)
        for f in to_add: self._add_fact(f)

    def copy(self):
        nfm = _FactMap(self.predicate, self.indexes)
        nfm.add(self.facts())
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

        # Create _FactMaps for the predicate types with indexed fields
        grouped = {}

        self._indexes = tuple(indexes)
        for path in self._indexes:
            if path.meta.predicate not in grouped: grouped[path.meta.predicate] = []
            grouped[path.meta.predicate].append(path)
        self._factmaps = { pt : _FactMap(pt, idxs) for pt, idxs in grouped.items() }

        if facts is None: return
        self._add(facts)

    # Make sure the FactBase has been initialised
    def _check_init(self):
        if self._delayed_init: self._delayed_init()  # Check for delayed init

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------

    def _add(self, arg):
        if isinstance(arg, Predicate): return self._add_fact(arg)
        for f in arg: self._add_fact(f)

    # Helper for _add
    def _add_fact(self, fact):
        ptype = type(fact)
        if not issubclass(ptype,Predicate):
            raise TypeError(("type of object {} is not a Predicate "
                             "(or sub-class)").format(fact))
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        self._factmaps[ptype].add(fact)

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
    def select(self, ptype):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].select()

    def delete(self, ptype):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].delete()

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
        tmp = [ fm.facts() for fm in self._factmaps.values() if fm]
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
                _format_asp_facts(fm,out,width)

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
        return fact in self._factmaps[ptype].facts()

    def __bool__(self):
        """Implemement set bool operator."""

        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            if fm: return True
        return False

    def __len__(self):
        self._check_init() # Check for delayed init
        return sum([len(fm) for fm in self._factmaps.values()])

    def __iter__(self):
        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            for f in fm: yield f

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
            if not _is_set_equal(fm1.facts(),fm2.facts()): return False

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
            if spfm < opfm: known_ne=True
            elif spfm > opfm: return False

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
            if spfm > opfm: return False
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
                fb._factmaps[p] = _FactMap(p).union(*pothers)
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
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
