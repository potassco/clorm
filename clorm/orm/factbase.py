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
    FuncInputSpec, FunctionComparator, QuerySpec

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
# Implementing Queries - the abstraction underneath Select and Delete
# statements.
# ------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Creates a mechanism for sorting using the order_by statements within queries.
#
# Works by creating a list of pairs consisting of a keyfunction and reverse
# flag, corresponding to the orderbyblocks in reverse order. A list can then by
# sorted by successively applying each sort function. Stable sort guarantees
# that the the result is a multi-criteria sort.
#------------------------------------------------------------------------------
class InQuerySorter(object):
    def __init__(self, orderbyblock, insig=None):
        if insig is None and len(orderbyblock.roots) > 1:
            raise ValueError(("Cannot create an InQuerySorter with no input "
                              "signature and an OrderByBlock with multiple "
                              "roots '{}'").format(orderbyblock))
        if insig is not None and not insig:
            raise ValueError("Cannot create an InQuerySorter with an empty signature")
        if not insig: insig=()

        # Create the list of (keyfunction,reverse flag) pairs then reverse it.
        self._sorter = []
        rp2idx = { hashable_path(rp) : idx for idx,rp in enumerate(insig) }
        for ob in orderbyblock:
            kf = ob.path.meta.attrgetter
            if insig:
                idx = rp2idx[hashable_path(ob.path.meta.root)]
                ig=operator.itemgetter(idx)
                kf = lambda f, kf=kf,ig=ig : kf(ig(f))
            self._sorter.append((kf,not ob.asc))
        self._sorter = tuple(reversed(self._sorter))

    # List in-place sorting
    def listsort(self, inlist):
        for kf, reverse in self._sorter:
            inlist.sort(key=kf,reverse=reverse)

    # Sort an iterable input and return an output list
    def sorted(self, input):
        for idx, (kf, reverse) in enumerate(self._sorter):
            if idx == 0:
                outlist = sorted(input,key=kf,reverse=reverse)
            else:
                outlist.sort(key=kf,reverse=reverse)
        return outlist

# ------------------------------------------------------------------------------
# prejoin query is the querying of the underlying factset or factindex
# - factsets - a dictionary mapping a predicate to a factset
# - factindexes - a dictionary mapping a hashable_path to a factindex
# ------------------------------------------------------------------------------

def make_first_prejoin_query(jqp, factsets, factindexes):
    factset = factsets.get(jqp.root.meta.predicate, FactSet())

    prejcl = jqp.prejoin_key
    prejcb = jqp.prejoin_clauses
    factindex = None
    if prejcl:
        factindex=factindexes.get(hashable_path(prejcl.paths[0]),None)
        if not factindex:
            raise ValueError(("Internal error: missing FactIndex for "
                              "path '{}'").format(prejcl.args[0]))

    def unsorted_query():
        if prejcb: cc = prejcb.make_callable([jqp.root.meta.dealiased])
        else: cc = lambda _ : True

        if factindex:
            for sc in prejcl:
                for f in factindex.find(sc.operator,sc.args[1]):
                    if cc((f,)): yield (f,)
        else:
            for f in factset:
                    if cc((f,)): yield (f,)

    return unsorted_query

# ------------------------------------------------------------------------------
#
# - factsets - a dictionary mapping a predicate to a factset
# - factindexes - a dictionary mapping a hashable_path to a factindex
# ------------------------------------------------------------------------------

def make_first_join_query(jqp, factsets, factindexes):

    if jqp.input_signature:
        raise ValueError(("A first JoinQueryPlan must have an empty input "
                          "signature but '{}' found").format(jqp.input_signature))
    if jqp.prejoin_orderbys and jqp.postjoin_orderbys:
        raise ValueError(("Internal error: it doesn't make sense to have both "
                          "a prejoin and join orderby sets for the first sub-query"))

    base_query=make_first_prejoin_query(jqp,factsets, factindexes)
    iqs=None
    if jqp.prejoin_orderbys:
        iqs = InQuerySorter(jqp.prejoin_orderbys,(jqp.root,))
    elif jqp.postjoin_orderbys:
        iqs = InQuerySorter(jqp.postjoin_orderbys,(jqp.root,))

    def sorted_query():
        return iqs.sorted(base_query())
    if iqs: return sorted_query
    else: return base_query

# ------------------------------------------------------------------------------
# Returns a function that takes no arguments and returns a populated data
# source.  The data source can be either a FactIndex, a FactSet, or a list.  In
# the simplest case this function simply passes through a reference to the
# underlying factset or factindex object. If it is a list then either the order
# doesn't matter or it is sorted by the prejoin_orderbys sort order.
#
# NOTE: We don't use this for the first JoinQueryPlan as that is handled as a
# special case.
# ------------------------------------------------------------------------------

def make_prejoin_query_source(jqp, factsets, factindexes):
    pjk  = jqp.prejoin_key
    pjc  = jqp.prejoin_clauses
    pjob = jqp.prejoin_orderbys
    jk   = jqp.join_key
    predicate = jqp.root.meta.predicate
    factset = factsets.get(jqp.root.meta.predicate, FactSet())

    # If there is a prejoin key clause
    if pjk:
        tmp = pjk.dealias().paths
        pjk_path = hashable_path(tmp[0])
        if len(tmp) != 1 or pjk_path not in factindexes \
           or tmp[0].meta.predicate != predicate:
            raise ValueError(("Internal error: prejoin key clause '{}' is invalid "
                              "for JoinQueryPlan {}").format(pjk,jqp))
        factindex = factindexes[pjk_path]

    # A prejoin_key query uses the factindex
    def query_pjk():
        for sc in pjk:
            for f in factindex.find(sc.operator,sc.args[1]):
                yield (f,)

    # If there is a set of prejoin clauses
    if pjc:
        pjc = pjc.dealias()
        pjc_root = pjc.roots[0]
        if len(pjc.roots) != 1 and pjc_root.meta.predicate != predicate:
            raise ValueError(("Internal error: prejoin clauses '{}' is invalid "
                              "for JoinQueryPlan {}").format(pjc,jqp))
        pjc_check = pjc.make_callable([pjc_root])

    # prejoin_clauses query uses the prejoin_key query or the underlying factset
    def query_pjc():
        if pjk:
            for (f,) in query_pjk():
                if pjc_check((f,)): yield (f,)
        else:
            for f in factset:
                if pjc_check((f,)): yield (f,)

    # If there is a join key
    if jk:
        jk_key_path = hashable_path(jk.args[0].meta.dealiased)
        if jk.args[0].meta.predicate != predicate:
            raise ValueError(("Internal error: join key '{}' is invalid "
                              "for JoinQueryPlan {}").format(jk,jqp))

    if pjob: pjiqs = InQuerySorter(pjob)
    else: pjiqs = None

    # If there is either a pjk or pjc then we need to create a temporary source
    # (using a FactIndex if there is a join key or a list otherwise). If there
    # is no pjk or pjc but there is a key then use an existing FactIndex if
    # there is one or create it.
    def query_source():
        if jk:
            if pjc:
                fi = FactIndex(path(jk_key_path))
                for (f,) in query_pjc(): fi.add(f)
                return fi
            elif pjk:
                fi = FactIndex(path(jk_key_path))
                for (f,) in query_pjk(): fi.add(f)
                return fi
            else:
                fi = factindexes.get(hashable_path(jk_key_path),None)
                if fi: return fi
                fi = FactIndex(path(jk_key_path))
                for f in factset: fi.add(f)
                return fi
        else:
            source = None
            if not pjc and not pjk and not pjob: return factset
            elif pjc: source = [f for (f,) in query_pjc() ]
            elif pjk: source = [f for (f,) in query_pjk() ]
            if source and not pjob: return source

            if not source and pjob:
                if len(pjob) == 1:
                    pjo = pjob[0]
                    fi = factindexes.get(hashable_path(pjo.path),None)
                    if fi and pjo.asc: return fi
                    elif fi: return list(reversed(fi))

            if source is None: source = factset

            # If there is only one sort order use attrgetter
            return pjiqs.sorted(source)

    return query_source

# ------------------------------------------------------------------------------
#
# - factsets - a dictionary mapping a predicate to a factset
# - factindexes - a dictionary mapping a hashable_path to a factindex
# ------------------------------------------------------------------------------

def make_chained_join_query(jqp, inquery, factsets, factindexes):

    if not jqp.input_signature:
        raise ValueError(("A non-first JoinQueryPlan must have a non-empty input "
                          "signature but '{}' found").format(jqp.input_signature))

    pjob = jqp.prejoin_orderbys
    jk   = jqp.join_key
    jc   = jqp.postjoin_clauses
    job  = jqp.postjoin_orderbys
    predicate = jqp.root.meta.predicate

    pjiqs = None
    if jk and pjob: pjiqs = InQuerySorter(pjob)

    # query_source will return a FactSet, FactIndex, or list
    query_source = make_prejoin_query_source(jqp, factsets, factindexes)

    # Setup any join clauses
    if jc:
        jc_check = jc.make_callable(list(jqp.input_signature) + [jqp.root])
    else:
        jc_check = lambda _: True

    def query_jk():
        operator = jk.operator
        align_query_input = make_input_alignment_functor(
            jqp.input_signature,(jk.args[1],))
        fi = query_source()
        for intuple in inquery():
            v, = align_query_input(intuple)
            result = list(fi.find(operator,v))
            if pjob: pjiqs.listsort(result)

            for f in result:
                out = tuple(intuple + (f,))
                if jc_check(out): yield out

    def query_no_jk():
        source = query_source()
        for intuple in inquery():
            for f in source:
                out = tuple(intuple + (f,))
                if jc_check(out): yield out


    if jk: unsorted_query=query_jk
    else: unsorted_query=query_no_jk
    if not job: return unsorted_query

    jiqs = InQuerySorter(job,list(jqp.input_signature) + [jqp.root])
    def sorted_query():
        return iter(jiqs.sorted(unsorted_query()))

    return sorted_query

#------------------------------------------------------------------------------
# Makes a query given a ground QueryPlan and the underlying data. The returned
# query object is a Python generator function that takes no arguments.
# ------------------------------------------------------------------------------

def make_query(qp, factsets, factindexes):
    if qp.placeholders:
        raise ValueError(("Cannot execute an ungrounded query. Missing values "
                          "for placeholders: "
                          "{}").format(", ".join([str(p) for p in qp.placeholders])))
    query = None
    for idx,jqp in enumerate(qp):
        if not query:
            query = make_first_join_query(
                jqp,factsets,factindexes)
        else:
            query = make_chained_join_query(
                jqp,query,factsets,factindexes)
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
    def __init__(self, factmaps, qspec, qplan, query):
        self._factmaps = factmaps
        self._qspec = qspec
        self._qplan = qplan
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

        # Running the query adds the facts to the appropriate delete set
        for input in self._query():
            for fact, action in zip(input,actions):
                action(fact)

        # Delete the facts
        count = 0
        for pt,ds in deletesets.items():
            count += len(ds)
            fm = self._factmaps[pt]
            for f in ds: fm.remove(f)
        return count

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
    def run(self, *args, **kwargs):
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
# Select V2 query engine with V1 API
#------------------------------------------------------------------------------

class SelectImpl(object):

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

        qspec = QuerySpec(roots=self._roots, join=self._joins,
                          where=self._where, order_by=self._orderbys)
        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
        return list(qo.all())

    def get_unique(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        qspec = QuerySpec(roots=self._roots, join=self._joins,
                          where= self._where,order_by= self._orderbys)
        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
        return qo.singleton()

    def count(self, *args, **kwargs):
        gqplan = self._queryplan.ground(*args,**kwargs)
        query = make_query(gqplan, self._pred2factset, self._path2factindex)

        qspec = QuerySpec(roots=self._roots, join=self._joins,
                          where= self._where,order_by= self._orderbys)
        qo = QueryOutput(self._factbase.factmaps,qspec,gqplan,query)
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

        qspec = QuerySpec(roots=self._roots,join=[],where=[],order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(),qspec)

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
        qspec = QuerySpec(roots=self._roots,join=self._joins,
                          where=[],order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(),qspec)
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
        qspec = QuerySpec(roots=self._roots,join=joins,where=where,order_by=[])
        self._queryplan = make_query_plan(self._path2factindex.keys(),qspec)
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
class Select2Impl(Select):

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
# QueryExecutor - actually executes the query and does the appropriate action
# (eg., displaying to the user or deleting from the factbase)
# ------------------------------------------------------------------------------

class QueryExecutor(object):

    #--------------------------------------------------------------------------
    # factmaps - dictionary mapping predicates to FactMap.
    # roots - the roots
    # qspec - dictionary containing the specification of the query and output
    #--------------------------------------------------------------------------
    def __init__(self, factmaps, qspec):
        self._factmaps = factmaps
        self._qspec = qspec.fill_defaults()


    #--------------------------------------------------------------------------
    # Support function
    #--------------------------------------------------------------------------
    @classmethod
    def get_factmap_data(cls, factmaps, qspec):
        roots = qspec.roots
        ptypes = set([ path(r).meta.predicate for r in roots])
        factsets = {}
        factindexes = {}
        for ptype in ptypes:
            fm =factmaps[ptype]
            factsets[ptype] = fm.factset
            for hpth, fi in fm.path2factindex.items(): factindexes[hpth] = fi
        return (factsets,factindexes)

    # --------------------------------------------------------------------------
    # Internal support function
    # --------------------------------------------------------------------------
    def _make_plan_and_query(self):
        (factsets,factindexes) = \
            QueryExecutor.get_factmap_data(self._factmaps, self._qspec)
        qplan = make_query_plan(factindexes.keys(), self._qspec)
        query = make_query(qplan,factsets,factindexes)
        return (qplan,query)


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

        unwrapkey = self._qspec.group_by == 1 and not self._qspec.tuple

        group_by_keyfunc = make_input_alignment_functor(
            self._qplan.output_signature, self._group_by)
        for k,g in itertools.groupby(self._query(), group_by_keyfunc):
            if unwrapkey: yield k[0], groupiter(g)
            else: yield k, groupiter(g)


    #--------------------------------------------------------------------------
    # Function to return a generator of the query output
    # --------------------------------------------------------------------------

    def all(self):
        (qplan,self._query) = self._make_plan_and_query()

        outsig = self._qspec.getp("select", qplan.output_signature)
        self._outputter = make_outputter(qplan.output_signature, outsig)
        self._unwrap = not self._qspec.tuple and len(outsig) == 1
        self._unique = self._qspec.unique

        if self._qspec.group_by > 0: return self._group_by_all()
        else: return self._all()

    # --------------------------------------------------------------------------
    # Delete a selection of facts. Maintains a set for each predicate type
    # and adds the selected fact to that set. The delete the facts in each set.
    # --------------------------------------------------------------------------

    def delete(self,*subroots):
        if self._executed:
            raise RuntimeError("The query instance has already been executed")
        if self._group_by:
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

        # Running the query adds the facts to the appropriate delete set
        for input in self._query():
            for fact, action in zip(input,actions):
                action(fact)

        # Delete the facts
        count = 0
        for pt,ds in deletesets.items():
            count += len(ds)
            fm = self._factmaps[pt]
            for f in ds: fm.remove(f)
        return count

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
