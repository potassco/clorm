# -----------------------------------------------------------------------------
# Supporting containers for FactBase. In particular FactIndex, FactSet, and
# FactMap.
# ------------------------------------------------------------------------------

import operator
import collections
import bisect
import itertools
from typing import Any, Iterable, List, Type

from .core import *
from .core import notcontains, PredicatePath

# ------------------------------------------------------------------------------
# In order to implement FactBase I originally used the built in 'set'
# class. However this uses the hash value, which for Predicate instances uses
# the underlying clingo.Symbol.__hash__() function. This in-turn depends on the
# c++ std::hash function. Like the Python standard hash function this uses
# random seeds at program startup which means that between successive runs of
# the same program the ordering of the set can change. This is bad for producing
# deterministic ASP solving. So using an OrderedSet instead.

from ..util import OrderedSet as FactSet

from ..util import OrderedSet

#FactSet=set                                # The Python standard set class. Note
                                           # fails some unit tests because I'm
                                           # testing for the ordering.

# Note: Some other 3rd party libraries that were tried but performed worse on
# a basic FactBase creation process:
#
#from ordered_set import OrderedSet as FactSet

#from orderedset import OrderedSet as FactSet   # Note: broken implementation so
                                               # fails some unit tests - union
                                               # operator only accepts a single
                                               # argument

#from blist import sortedset as FactSet
#from sortedcontainers import SortedSet as FactSet
# ------------------------------------------------------------------------------

__all__ = [
    'FactSet',
    'FactIndex',
    'FactMap',
    'factset_equality',
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
            self._attrgetter = self._path.meta.attrgetter
            self._predicate = self._path.meta.predicate
            self._keylist = []
            self._key2values = collections.OrderedDict()
        except:
            raise TypeError("{} is not a valid PredicatePath object".format(path))

    @property
    def path(self):
        return self._path

    def add(self, fact):
        if not isinstance(fact, self._predicate):
            raise TypeError("{} is not a {}".format(fact, self._predicate))
        key = self._attrgetter(fact)

        # Index the fact by the key - Note: using OrderedSet to preserve
        # insertion order for repeatability
        if key not in self._key2values: self._key2values[key] = OrderedSet()
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
        key = self._attrgetter(fact)

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
        self._key2values = collections.OrderedDict()

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
        left = self._keylist[:posn1]
        posn2 = bisect.bisect_right(self._keylist, key)
        right = self._keylist[posn2:]
        return left + right

    def _keys_lt(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        return self._keylist[:posn]

    def _keys_le(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        return self._keylist[:posn]

    def _keys_gt(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        return self._keylist[posn:]

    def _keys_ge(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        return self._keylist[posn:]

    def _keys_contains(self, seq):
        tmp = []
        for key in seq:
            if key in self._key2values: tmp.append(key)
        tmp.sort()
        return tmp

    def _keys_notcontains(self, seq):
        tmp = []
        for key in self._keylist:
            if key not in seq:
                tmp.append(key)
        return tmp

    #--------------------------------------------------------------------------
    # Find elements based on boolean match to a key
    #--------------------------------------------------------------------------
    def find(self, op, val,reverse=False):
        keys = []
        if op == operator.eq: keys = self._keys_eq(val)
        elif op == operator.ne: keys = self._keys_ne(val)
        elif op == operator.lt: keys = self._keys_lt(val)
        elif op == operator.le: keys = self._keys_le(val)
        elif op == operator.gt: keys = self._keys_gt(val)
        elif op == operator.ge: keys = self._keys_ge(val)
        elif op == operator.contains: keys = self._keys_contains(val)
        elif op == notcontains: keys = self._keys_notcontains(val)
        else: raise ValueError("unsupported operator {}".format(op))

        if reverse:
            for k in reversed(keys):
                for fact in self._key2values[k]: yield fact
        else:
            for k in keys:
                for fact in self._key2values[k]: yield fact

    #--------------------------------------------------------------------------
    # Iterate in descending key order
    #--------------------------------------------------------------------------

    def __reversed__(self):
        for key in reversed(self._keylist):
            for f in self._key2values[key]: yield f

    #--------------------------------------------------------------------------
    # Iterate in key ascending order
    #--------------------------------------------------------------------------

    def __iter__(self):
        for key in self._keylist:
            for f in self._key2values[key]: yield f

    def __bool__(self):
        for facts in self._key2values.values():
            if facts: return True
        return False

    def __len__(self):
        return sum([len(facts) for facts in self._key2values.values()])

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        if hashable_path(self._path) != hashable_path(other._path): return False
        return self._key2values == other._key2values

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

def factset_equality(s1,s2):
    if len(s1) != len(s2): return False
    for elem in s1:
        if elem not in s2: return False
    return True

#------------------------------------------------------------------------------
# FactMap is simply a meta-container for FactSet and FactIndex containers.
#
# For each predicate type it holds a FactSet and any associated FactIndexes.
#
# FactMap only implements the operations for adding and deleting facts (and set
# operations that add/delete facts). The reason is that this is complicated by
# having to add and delete the facts from multiple source (the FactSet and
# multiple FactIndex objects).
#
# For accessing facts and testing the inclusion of a fact in the map you must
# access the underlying FactSet or FactIndex object. For example, the query
# engine is passed the FactMap and then choses the appropriate way of accessing
# the data.
#
# ------------------------------------------------------------------------------

def _fm_iterable(other):
    if isinstance(other, FactMap): return other.factset
    else: return other

class FactMap(object):
    def __init__(self, ptype: Type[Predicate], indexes: Iterable[Any]=[]) -> None:
        def clean_path(p):
            p = path(p)
            if hashable_path(p) != hashable_path(p.meta.dealiased):
                raise ValueError(("It doesn't make sense to index on an alias "
                                  "'{}'").format(p))
            if p.meta.is_root:
                raise ValueError(("It doesn't make sense to index a root path "
                                  "'{}'").format(p))
            if p.meta.predicate != ptype:
                raise ValueError(("Cannot index path '{}' that doesn't match "
                                  "the predicate '{}'").format(p,ptype))
            return hashable_path(p)

        self._ptype = ptype
        self._factset = FactSet()
        self._path2factindex = collections.OrderedDict()

        # Validate the paths to be indexed
        allindexes = set([clean_path(p) for p in indexes])
        factindexes: List[FactIndex] = []
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
            factindexes.append(tmpfi)
        self._factindexes = tuple(factindexes)

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
    def predicate(self) -> Type[Predicate]:
        return self._ptype

    @property
    def factset(self):
        return self._factset

    @property
    def path2factindex(self):
        return self._path2factindex

    def __len__(self):
        return len(self._factset)

    def __bool__(self):
        return bool(self._factset)

    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [_fm_iterable(o) for o in others]
        tmp = self.factset.union(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def intersection(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [_fm_iterable(o) for o in others]
        tmp = self.factset.intersection(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def difference(self,*others):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmpothers = [_fm_iterable(o) for o in others]
        tmp = self.factset.difference(*tmpothers)
        nfm.add_facts(tmp)
        return nfm

    def symmetric_difference(self,other):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        tmp = self.factset.symmetric_difference(_fm_iterable(other))
        nfm.add_facts(tmp)
        return nfm

    def update(self,*others):
        self.add_facts(itertools.chain(*[_fm_iterable(o) for o in others]))

    def intersection_update(self,*others):
        for f in set(self.factset):
            for o in others:
                if f not in _fm_iterable(o): self.discard(f)

    def difference_update(self,*others):
        for f in itertools.chain(*[o.factset for o in others]):
            self.discard(f)

    def symmetric_difference_update(self, other):
        to_remove=OrderedSet()
        to_add=OrderedSet()
        for f in self._factset:
            if f in _fm_iterable(other): to_remove.add(f)
        for f in _fm_iterable(other):
            if f not in self._factset: to_add.add(f)
        for f in to_remove: self.discard(f)
        self.add_facts(to_add)

    def copy(self):
        nfm = FactMap(self.predicate, self._path2factindex.keys())
        nfm.add_facts(self.factset)
        return nfm


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
