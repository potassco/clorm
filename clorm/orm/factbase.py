# -----------------------------------------------------------------------------
# Clorm ORM FactBase implementation. FactBase provides a set-like container
# specifically for storing facts (Predicate instances).
# ------------------------------------------------------------------------------

import abc
import io
import itertools
import sys
from typing import (Any, Callable, Iterable, Iterator, List, Optional, TextIO,
                    Tuple, Type, Union, cast, overload)

from ._typing import _T0, _T1, _T2, _T3, _T4
from ._queryimpl import UnGroupedQuery
from .core import (Predicate, PredicateDefn, PredicatePath, and_,
                   validate_root_paths)
from .factcontainers import FactMap, factset_equality
from .query import (QueryExecutor, QuerySpec, make_query_plan, process_orderby,
                    process_where)

__all__ = [
    'FactBase',
    'Select',
    'Delete',
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
_Facts = Union[Iterable[Predicate], Callable[[], Iterable[Predicate]]]

#------------------------------------------------------------------------------
# Support function for printing ASP facts: Note: _trim_docstring() is taken from
# PEP 257 (modified for Python 3): https://www.python.org/dev/peps/pep-0257/
# ------------------------------------------------------------------------------

_builtin_sorted=sorted

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

def _trim_docstring(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)

def _endstrip(string):
    if not string: return
    nl=string[-1]=='\n'
    tmp=string.rstrip()
    return tmp + '\n' if nl else tmp

def _format_docstring(docstring,output):
    if not docstring: return
    tmp=_trim_docstring(docstring)
    tmpstr = "".join(_endstrip("%     " + l) for l in tmp.splitlines(True))
    if tmpstr:
        print("% Description:",file=output)
        print(tmpstr,file=output)

def _maxwidth(lines):
    return max([len(l) for l in lines])

def _format_commented(fm: FactMap, out: TextIO) -> None:
    pm: PredicateDefn = fm.predicate.meta
    docstring = _trim_docstring(fm.predicate.__doc__) \
        if fm.predicate.__doc__ else ""
    indent = "    "
    if pm.arity == 0:
        lines = [ "Unary predicate signature:", indent + pm.name ]
    else:
        def build_signature(p: Type[Predicate]) -> str:
            args = []
            for pp in p:
                complex = pp.meta.field.complex
                args.append(cast(str, pp._pathseq[1]) if not complex else build_signature(complex))
            return f"{p.meta.name}({','.join(args)})"

        lines = [ "Predicate signature:",
                  indent + build_signature(fm.predicate) ]
    if docstring:
        lines.append("Description:")
        for l in docstring.splitlines():lines.append(indent + l)
    bar = "-" * _maxwidth(lines)
    lines.insert(0,bar)
    lines.append(bar)
    for l in lines:
        tmp = l.rstrip()
        if tmp: print("% {}".format(tmp),file=out)
        else: print("%",file=out)
    return

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
        self._delayed_init: Optional[Callable[[], None]] = None

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

    def _add(self, arg: Union[Predicate, Iterable[Predicate]]) -> None:
        if isinstance(arg, Predicate):
            ptype = arg.__class__
            if not ptype  in self._factmaps:
                self._factmaps[ptype] = FactMap(ptype)
            return self._factmaps[ptype].add_fact(arg)

        if isinstance(arg, str) or not isinstance(arg, Iterable):
            raise TypeError(f"'{arg}' is not a Predicate instance")

        sorted_facts = sorted(arg, key=lambda x: x.__class__.__name__)
        for type_, grouped_facts in itertools.groupby(sorted_facts, lambda x: x.__class__):
            if not issubclass(type_, Predicate):
                raise TypeError(f"{list(grouped_facts)} are not Predicate instances")
            if not type_ in self._factmaps:
                self._factmaps[type_] = FactMap(type_)
            self._factmaps[type_].add_facts(grouped_facts)
        return

    def _remove(self, fact, raise_on_missing):
        ptype = type(fact)
        if not isinstance(fact, Predicate) or ptype not in self._factmaps:
            raise KeyError(fact)

        return self._factmaps[ptype].remove(fact,raise_on_missing)

    #--------------------------------------------------------------------------
    # Initiliser
    #--------------------------------------------------------------------------
    def __init__(self, facts: Optional[_Facts] = None, indexes: Optional[Iterable[PredicatePath]] = None) -> None:
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
    def add(self, arg: Union[Predicate, Iterable[Predicate]]) -> None:
        """Add a single fact or a collection of facts.

        Because a ``FactBase`` can only hold :class:`~Predicate` sub-class
        instances this member function has been overloaded to take either a
        single :class:`~Predicate` sub-class instance or a collection of
        :class:`~Predicate` sub-class instances.

        Args:
          arg: a single fact or a collection of facts.

        """
        self._check_init()  # Check for delayed init
        return self._add(arg)

    def remove(self, arg: Predicate) -> None:
        """Remove a fact from the fact base (raises an exception if no fact). """
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=True)

    def discard(self, arg: Predicate) -> None:
        """Remove a fact from the fact base. """
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=False)

    def pop(self) -> Predicate:
        """Pop an element from the FactBase. """
        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items():
            if fm: return fm.pop()
        raise KeyError("pop from an empty FactBase")

    def clear(self):
        """Clear the fact base of all facts."""

        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items(): fm.clear()

    #--------------------------------------------------------------------------
    # Special FactBase member functions
    #--------------------------------------------------------------------------
    def select(self, root):
        """Define a select query using the old Query API.

        .. note::

           This interface will eventually be deprecated when the new
           :class:`Query API<Query>` is finalised. The entry point to this Query
           API is through the :meth:`FactBase.query` method.

        Args:
           predicate: The predicate to query.

        Returns:
           Returns a Select query object for specifying a query.

        """
        self._check_init()  # Check for delayed init

        roots = validate_root_paths([root])
        ptypes = set([ root.meta.predicate for root in roots])

        # Make sure there are factmaps for each referenced predicate type
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return SelectImpl(self, QuerySpec(roots=roots))

    def delete(self, root):
        self._check_init()  # Check for delayed init

        roots = validate_root_paths([root])
        ptypes = set([ root.meta.predicate for root in roots])

        # Make sure there are factmaps for each referenced predicate type
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        return _Delete(self, QuerySpec(roots=roots))

    # START OVERLOADED FUNCTIONS self.query;UnGroupedQuery[{0}];1;5;Type;

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py

    @overload
    def query(
        self, __ent0: Type[_T0]
    ) -> 'UnGroupedQuery[_T0]':
        ...

    @overload
    def query(
        self, __ent0: Type[_T0], __ent1: Type[_T1]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1]]':
        ...

    @overload
    def query(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def query(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def query(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    # END OVERLOADED FUNCTIONS self.query
   
    @overload
    def query(self, *roots: Any) -> 'UnGroupedQuery[Any]': ...

    def query(self, *roots):
        """Define a query using the new Query API :class:`Query`.

        The parameters consist of a predicates (or aliases) to query (like an
        SQL FROM clause).

        Args:
           *predicates: predicate or predicate aliases

        Returns:
           Returns a Query object for specifying a query.

        """

        self._check_init()  # Check for delayed init

        # Make sure there are factmaps for each referenced predicate type
        ptypes = set([r.meta.predicate for r in validate_root_paths(roots)])
        for ptype in ptypes: self._factmaps.setdefault(ptype, FactMap(ptype))

        qspec = QuerySpec(roots=roots)
        return UnGroupedQuery(self._factmaps, qspec)

    @property
    def predicates(self) -> Tuple[Type[Predicate], ...]:
        """Return the list of predicate types that this fact base contains."""

        self._check_init()  # Check for delayed init
        return tuple([pt for pt, fm in self._factmaps.items() if fm])

    @property
    def indexes(self) -> Tuple[PredicatePath, ...]:
        self._check_init()  # Check for delayed init
        return self._indexes

    def facts(self) -> List[Predicate]:
        """Return all facts."""

        self._check_init()  # Check for delayed init
        tmp = [ fm.factset for fm in self._factmaps.values() if fm]
        return list(itertools.chain(*tmp))

    def asp_str(self, *, width: int = 0, commented: bool = False, sorted: bool = False) -> str:
        """Return a ASP string representation of the fact base.

        The generated ASP string representation is syntactically correct ASP
        code so is suitable for adding as the input to to an ASP program (or
        writing to a file for later use in an ASP program).

        By default the order of the facts in the string is arbitrary. Because
        `FactBase` is built on a `OrderedDict` (which preserves insertion
        order) the order of the facts will be deterministic between runs of the
        same program. However two FactBases containing the same facts but
        constructed in different ways will not produce the same output
        string. In order to guarantee the same output the `sorted` flag can be
        specified.

        Args:
            width: tries to fill to a given width by putting more than one
                   fact on a line if necessary (default: 0).
            commented: produces commented ASP code by adding a predicate
                       signature and turning the Predicate sub-class docstring
                       into a ASP comments (default: False).
            sorted: sort the output facts, first by predicates (name,arity) and
                    then by the natural order of the instances for that
                    predicate (default :False).

        """
        self._check_init()  # Check for delayed init
        out = io.StringIO()

        first=True
        if sorted:
            names = _builtin_sorted(self._factmaps.keys(),key=lambda pt:
                                    (pt.meta.name, pt.meta.arity,pt.__name__))
            fms = [self._factmaps[n] for n in names]
        else:
            fms = self._factmaps.values()
        for fm in fms:
            if commented:
                if first: first=False
                else: print("",file=out)
                _format_commented(fm,out)
            if sorted:
                _format_asp_facts(_builtin_sorted(fm.factset),out,width)
            else:
                _format_asp_facts(fm.factset,out,width)

        data = out.getvalue()
        out.close()
        return data

    def __str__(self) -> str:
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

    def __iter__(self) -> Iterator[Predicate]:
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

    def __getstate__(self):
        self._check_init()
        return self.__dict__


    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self, *others: _Facts) -> 'FactBase':
        """Implements the set union() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        fb = FactBase()
        predicates = set(self._factmaps.keys())
        for o in factbases: predicates.update(o._factmaps.keys())

        for p in predicates:
            pothers = [o._factmaps[p] for o in factbases if p in o._factmaps]
            if p in self._factmaps:
                fb._factmaps[p] = self._factmaps[p].union(*pothers)
            else:
                fb._factmaps[p] = FactMap(p).union(*pothers)
        return fb

    def intersection(self, *others: _Facts) -> 'FactBase':
        """Implements the set intersection() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        fb = FactBase()
        predicates = set(self._factmaps.keys())
        for fb_ in factbases: predicates.intersection_update(fb_._factmaps.keys())

        for p in predicates:
            pothers = [o._factmaps[p] for o in factbases if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].intersection(*pothers)
        return fb

    def difference(self, *others: _Facts) -> 'FactBase':
        """Implements the set difference() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        fb = FactBase()
        predicates = set(self._factmaps.keys())

        for p in predicates:
            pothers = [o._factmaps[p] for o in factbases if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].difference(*pothers)
        return fb

    def symmetric_difference(self, other: _Facts) -> 'FactBase':
        """Implements the set symmetric_difference() function"""
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() # Check for delayed init
        other._check_init()

        fb = FactBase()
        predicates = set(self._factmaps.keys())
        predicates.update(other._factmaps.keys())

        for p in predicates:
            in_self = p in self._factmaps ; in_other = p in other._factmaps
            if in_self and in_other:
                fb._factmaps[p] = self._factmaps[p].symmetric_difference(other._factmaps[p])
            elif in_self:
                fb._factmaps[p] = self._factmaps[p].copy()
            elif in_other:
                fb._factmaps[p] = other._factmaps[p].copy()

        return fb

    def update(self, *others: _Facts) -> None:
        """Implements the set update() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        for fb in factbases:
            for p,fm in fb._factmaps.items():
                if p in self._factmaps: self._factmaps[p].update(fm)
                else: self._factmaps[p] = fm.copy()

    def intersection_update(self, *others: _Facts) -> None:
        """Implements the set intersection_update() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        predicates = set(self._factmaps.keys())
        for fb in factbases: predicates.intersection_update(fb._factmaps.keys())
        pred_to_delete = set(self._factmaps.keys()) - predicates

        for p in pred_to_delete: self._factmaps[p].clear()
        for p in predicates:
            pothers = [o._factmaps[p] for o in factbases if p in o._factmaps]
            self._factmaps[p].intersection_update(*pothers)

    def difference_update(self, *others: _Facts) -> None:
        """Implements the set difference_update() function"""
        factbases = [o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for fb in factbases: fb._check_init()

        for p in self._factmaps.keys():
            pothers = [o._factmaps[p] for o in factbases if p in o._factmaps]
            self._factmaps[p].difference_update(*pothers)

    def symmetric_difference_update(self, other: _Facts) -> None:
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

    def copy(self) -> 'FactBase':
        """Implements the set copy() function"""
        self._check_init() # Check for delayed init
        fb = FactBase()
        for p, _ in self._factmaps.items():
            fb._factmaps[p] = self._factmaps[p].copy()
        return fb

#------------------------------------------------------------------------------
# Select is an interface query over a FactBase.
# ------------------------------------------------------------------------------

class Select(abc.ABC):
    """An abstract class that defines the interface to original Query API.

    .. note::

       This interface will eventually be deprecated when the new :class:`Query
       API<Query>` is finalised.

    ``Select`` query objects cannot be constructed directly. Instead a
    ``Select`` object is returned by the :meth:`FactBase.select` function. Given
    a ``FactBase`` object ``fb``, a specification is of the form:

          ``query = fb.select(<predicate>).where(<expression>).order_by(<ordering>)``

    where ``<predicate>`` specifies the predicate type to search for,
    ``<expression>`` specifies the search criteria and ``<ordering>`` specifies
    a sort order when returning the results. The ``where()`` and ``order_by()``
    clauses are omitted when not required.

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

    def get_unique(self, *args, **kwargs):
        """Return the unique matching entry (or raise an exception)"""
        pass

    def count(self, *args, **kwargs):
        """Return the number of matches."""
        pass

#------------------------------------------------------------------------------
# Delete is an interface to perform a query delete from a FactBase.
# ------------------------------------------------------------------------------

class Delete(abc.ABC):
    """An abstract class that defines the interface to a original delete query API.

    .. note::

       This interface will eventually be deprecated when the new :class:`Query
       API<Query>` is finalised.

    ``Delete`` query objects cannot be constructed directly. Instead a
    ``Delete`` object is returned by the ``FactBase.delete()`` function. Given a
    ``FactBase`` object ``fb``, a specification is of the form:

          ``query = fb.delete(<predicate>).where(<expression>)``

    where ``<predicate>`` specifies the predicate type to search for,
    ``<expression>`` specifies the search criteria. The ``where()`` clause can
    be omitted in which case all predicates of that type will be deleted.

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

    def __init__(self, factbase, qspec):
        self._factbase = factbase
        self._qspec = qspec

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self, *expressions):
        if self._qspec.where:
            raise TypeError("Cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("Empty 'where' expression")

        try:
            if len(expressions) == 1:
                where = process_where(expressions[0],self._qspec.roots)
            else:
                where = process_where(and_(*expressions),self._qspec.roots)
            nqspec = self._qspec.newp(where=where)
        except ValueError as e:
            raise TypeError(str(e)) from None
        return SelectImpl(self._factbase,nqspec)

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self, *expressions):
        if self._qspec.order_by:
            raise TypeError("Cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("Empty 'order_by' expression")
        try:
            order_by=process_orderby(expressions,self._qspec.roots)
            nqspec = self._qspec.newp(order_by=order_by)
        except ValueError as e:
            raise TypeError(str(e)) from None
        return SelectImpl(self._factbase,nqspec)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def query_plan(self,*args,**kwargs):
        qspec = self._qspec.fill_defaults()

        (factsets,factindexes) = \
            QueryExecutor.get_factmap_data(self._factbase.factmaps, qspec)
        qplan = make_query_plan(factindexes.keys(), qspec)

        return qplan.ground(*args,**kwargs)

    #--------------------------------------------------------------------------
    # Functions currently mirroring the old interface
    # --------------------------------------------------------------------------

    def get(self, *args, **kwargs):
        qspec = self._qspec
        if args or kwargs:
            if self._qspec.where is None:
                raise ValueError(("No where clause to ground"))
            qspec = self._qspec.bindp(*args, **kwargs)

        qe = QueryExecutor(self._factbase.factmaps, qspec)
        return list(qe.all())

    def get_unique(self, *args, **kwargs):
        qspec = self._qspec
        if args or kwargs:
            if self._qspec.where is None:
                raise ValueError(("No where clause to ground"))
            qspec = self._qspec.bindp(*args, **kwargs)

        qe = QueryExecutor(self._factbase.factmaps, qspec)
        found = None
        for out in qe.all():
            if found: raise ValueError("Query returned more than a single element")
            found = out
        return found

    def count(self, *args, **kwargs):
        qspec = self._qspec
        if args or kwargs:
            if self._qspec.where is None:
                raise ValueError(("No where clause to ground"))
            qspec = self._qspec.bindp(*args, **kwargs)

        qe = QueryExecutor(self._factbase.factmaps, qspec)
        count = 0
        for _ in qe.all(): count += 1
        return count

#------------------------------------------------------------------------------
# The Delete class
#------------------------------------------------------------------------------

class _Delete(Delete):

    def __init__(self, factbase, qspec):
        self._factbase = factbase
        self._root = qspec.roots[0]
        self._select = SelectImpl(factbase,qspec)
        self._has_where = False

    def where(self, *expressions):
        self._has_where = True
        self._select = self._select.where(*expressions)
        return self

    def execute(self, *args, **kwargs):
        factmap = self._factbase.factmaps[self._root.meta.predicate]

        # If there is no where clause then delete everything
        if not self._has_where:
            num_deleted = len(factmap.facts())
            factmap.clear()
            return num_deleted

        # Gather all the facts to delete and remove them
        to_delete = [ f for f in self._select.get(*args, **kwargs) ]
        for fact in to_delete: factmap.remove(fact)
        return len(to_delete)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
