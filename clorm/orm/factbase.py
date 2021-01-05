# -----------------------------------------------------------------------------
# Clorm ORM FactBase implementation. FactBase provides a set-like container
# specifically for storing facts (Predicate instances). It also provides the
# rich query API.
# ------------------------------------------------------------------------------

#import logging
#import os
import io
import contextlib
import inspect
import operator
import collections
import bisect
import abc
import functools
import itertools
import clingo
import typing
import re

from .core import *
from .core import get_field_definition, Conditional, PredicatePath, \
    kwargs_check_keys

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

# Note: Some other 3rd party libraries that were tried but performanced worse on
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
    'SymbolPredicateUnifier',
    'desc',
    'asc',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'not_',
    'and_',
    'or_',
    'unify'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------


#------------------------------------------------------------------------------
# Defining and manipulating conditional elements
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Placeholder allows for variable substituion of a query. Placeholder is
# an abstract class that exposes no API other than its existence.
# ------------------------------------------------------------------------------
class Placeholder(abc.ABC):

    """An abstract class for defining parameterised queries.

    Currently, Clorm supports 4 placeholders: ph1\_, ph2\_, ph3\_, ph4\_. These
    correspond to the positional arguments of the query execute function call.

    """
    pass

class _NamedPlaceholder(Placeholder):
    # None could be a legitimate value so cannot use it to test for default
    def __init__(self, name, *args, **kwargs):
        self._name = name
        # Check for unexpected arguments
        badkeys = kwargs_check_keys(set(["default"]), set(kwargs.keys()))
        if badkeys:
            mstr = "Named placeholder unexpected keyword arguments: "
            raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

        # Check the match between positional and keyword arguments
        if "default" in kwargs and len(args) > 0:
            raise TypeError(("Named placeholder got multiple values for "
                             "argument 'default'"))
        if len(args) > 1:
            raise TypeError(("Named placeholder takes from 0 to 2 positional"
                             "arguments but {} given").format(len(args)+1))

        # Set the keyword argument
        if "default" in kwargs: self._default = (True, kwargs["default"])
        else: self._default = (False,None)

    @property
    def name(self):
        return self._name
    @property
    def has_default(self):
        return self._default[0]
    @property
    def default(self):
        return self._default[1]
    def __str__(self):
        tmpstr = "" if not self._default[0] else ",{}".format(self._default[1])
        return "ph_(\"{}\"{})".format(self._name, tmpstr)
    def __repr__(self):
        return self.__str__()
    def __eq__(self, other):
        if not isinstance(other, _NamedPlaceholder): return NotImplemented
        if self.name != other.name: return False
        if self._default != other._default: return False
        return True
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

class _PositionalPlaceholder(Placeholder):
    def __init__(self, posn):
        self._posn = posn
    @property
    def posn(self):
        return self._posn
    def __str__(self):
        return "ph{}_".format(self._posn+1)
    def __repr__(self):
        return self.__str__()
    def __eq__(self, other):
        if not isinstance(other, _PositionalPlaceholder): return NotImplemented
        return self._posn == other._posn
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

#def ph_(value,default=None):

def ph_(value, *args, **kwargs):
    ''' A function for building new placeholders, either named or positional.'''

    badkeys = kwargs_check_keys(set(["default"]), set(kwargs.keys()))
    if badkeys:
        mstr = "ph_() unexpected keyword arguments: "
        raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

    # Check the match between positional and keyword arguments
    if "default" in kwargs and len(args) > 0:
        raise TypeError("ph_() got multiple values for argument 'default'")
    if len(args) > 1:
        raise TypeError(("ph_() takes from 0 to 2 positional"
                         "arguments but {} given").format(len(args)+1))

    # Set the default argument
    if "default" in kwargs: default = default = (True, kwargs["default"])
    elif len(args) > 0: default = (True, args[0])
    else: default = (False,None)

    try:
        idx = int(value)
    except ValueError:
        # It's a named placeholder
        nkargs = { "name" : value }
        if default[0]: nkargs["default"] = default[1]
        return _NamedPlaceholder(**nkargs)

    # Its a positional placeholder
    if default[0]:
        raise TypeError("Positional placeholders don't support default values")
    idx -= 1
    if idx < 0:
        raise ValueError("Index {} is not a positional argument".format(idx+1))
    return _PositionalPlaceholder(idx)

#------------------------------------------------------------------------------
# Some pre-defined positional placeholders
#------------------------------------------------------------------------------

ph1_ = _PositionalPlaceholder(0)
ph2_ = _PositionalPlaceholder(1)
ph3_ = _PositionalPlaceholder(2)
ph4_ = _PositionalPlaceholder(3)


def _hashable_paths(cond):
    if not isinstance(cond,Conditional): return set([])
    tmp=set([])
    for a in cond.args:
        if isinstance(a, PredicatePath): tmp.add(a.meta.hashable)
        elif isinstance(a, Conditional): tmp.update(_hashable_paths(a))
    return tmp

def _placeholders(cond):
    if not isinstance(cond,Conditional): return set([])
    tmp=set([])
    for a in cond.args:
        if isinstance(a, Placeholder): tmp.add(a.meta.hashable)
        elif isinstance(a, Conditional): tmp.update(_placeholders(a))
    return tmp


# ------------------------------------------------------------------------------
# User callable functions to build boolean conditions
# ------------------------------------------------------------------------------

def not_(*conditions):
    return Conditional(operator.not_,*conditions)
def and_(*conditions):
    return functools.reduce((lambda x,y: Conditional(operator.and_,x,y)),conditions)
def or_(*conditions):
    return functools.reduce((lambda x,y: Conditional(operator.or_,x,y)),conditions)



#------------------------------------------------------------------------------
# Functions to check, simplify, resolve placeholders, and execute queries
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Check a query condition for errors. Raises exceptions if there is an error
# otherwise does nothing.
# ------------------------------------------------------------------------------
def check_query_condition(qcond):

    def check_comp_condition(ccond):
        for arg in ccond.args:
            if isinstance(arg,PredicatePath): continue
            if callable(arg):
                raise ValueError(("Invalid functor '{}' as argument to a comparison"
                                  "operator in query '{}'").format(arg,qcond))
    def check_bool_condition(bcond):
        for a in bcond.args: check_condition(a)
        if bcond.operator in [ operator.and_, operator.or_, operator.not_ ]: return
        raise TypeError(("Internal bug: unknown boolean operator '{}' in query "
                         "condition '{}'").format(bcond.operator, qcond))

    def check_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid condition '{}' in query '{}': a Placeholder must be "
                              "part of a comparison condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid condition '{}' in query '{}': a PredicatePath must be "
                              "part of a comparison condition").format(cond, qcond))
        if callable(cond): return
        if isinstance(cond,Conditional):
            if Conditional.operators[cond.operator].isbool:
                check_bool_condition(cond)
            else:
                check_comp_condition(cond)

    return check_condition(qcond)

# ------------------------------------------------------------------------------
# Simplify a query condition by generating static values for any conditional
# that is not dependant on the value of a fact field or a placeholder and
# propagating up any evaluations.
#
# NOTE: this function will not pick up all errors in the query condition so you
# must first test with check_query_condition()
# ------------------------------------------------------------------------------
def simplify_query_condition(qcond):

    def getcomparable(arg):
        if isinstance(arg,PredicatePath): return arg.meta.hashable
        return arg

    def isdynamicarg(arg):
        if isinstance(arg,Placeholder): return True
        elif isinstance(arg,PredicatePath): return True
        elif callable(arg):
            raise ValueError(("Invalid functor '{}' as argument to a comparison"
                              "operator in query '{}'").format(arg,qcond))
        return False

    def isdynamiccond(cond):
        if isinstance(cond,Conditional): return True
        if callable(cond): return True
        return False

    def simplify_comp_condition(ccond):
        if ccond.operator in [ operator.eq, operator.ne, operator.gt, operator.ge, \
                               operator.lt,operator.le ]:
            if getcomparable(ccond.args[0]) == getcomparable(ccond.args[1]):
                return ccond.operator(1,1)

        if any(map(isdynamicarg, ccond.args)): return ccond
        return ccond.operator(*ccond.args)

    def simplify_bool_condition(bcond):
        if bcond.operator == operator.not_:
            newsubcond = simplify_condition(bcond.args[0])
            if not isdynamiccond(newsubcond): return bcond.operator(newsubcond)
            if newsubcond is bcond.args[0]: return bcond
            return Conditional(bcond.operator,newsubcond)
        if bcond.operator != operator.and_ and bcond.operator != operator.or_:
            print("dfd")
            raise TypeError(("Internal bug: unknown boolean operator '{}' in query "
                             "condition '{}'").format(bcond.operator, qcond))

        newargs = [simplify_condition(a) for a in bcond.args]
        if bcond.operator == operator.and_:
            if not isdynamiccond(newargs[0]):
                return False if not newargs[0] else newargs[1]
            if not isdynamiccond(newargs[1]):
                return False if not newargs[1] else newargs[0]
            if newargs[0] is bcond.args[0] and newargs[1] is bcond.args[1]:
                return bcond
            return Conditional(bcond.operator,*newargs)

        if bcond.operator == operator.or_:
            if not isdynamiccond(newargs[0]):
                return True if newargs[0] else newargs[1]
            if not isdynamiccond(newargs[1]):
                return True if newargs[1] else newargs[0]
            if newargs[0] is bcond.args[0] and newargs[1] is bcond.args[1]:
                return bcond
            return Conditional(bcond.operator,*newargs)

    def simplify_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid condition '{}' in query '{}': a Placeholder must be "
                              "part of a comparison condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid condition '{}' in query '{}': a PredicatePath must be "
                              "part of a comparison condition").format(cond, qcond))
        if callable(cond): return cond
        if not isinstance(cond,Conditional): return bool(cond)
        if Conditional.operators[cond.operator].isbool:
            return simplify_bool_condition(cond)
        else:
            return simplify_comp_condition(cond)

    return simplify_condition(qcond)

# ------------------------------------------------------------------------------
# Instantiate/resolve placeholders within a query conditional against a set of
# positional and keyword arguments. Raises a ValueError if there are any
# unresolved placeholders. Note: for a function or lambda it is impossible to
# tell what placeholder values to expect. If we find a function or lambda we
# wrap it in a FunctionalPlaceholderWrapper and assume we have all the necessary
# arguments.
# ------------------------------------------------------------------------------

class FuncConditionWrapper(object):
    def __init__(self,func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __call__(self,fact):
        return self._func(fact, *self._args, **self._kwargs)

    def __str__(self):
        result = ("FuncConditionWrapper(\n\tfunc={},\n\targs={},\n\t"
                  "kwargs={})").format(self._func,self._args,self._kwargs)
        return result

def instantiate_query_condition(qcond, *args, **kwargs):

    def checkarg(a):
        if isinstance(a,Placeholder):
            raise ValueError(("Invalid Placeholder argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(a,qcond,args,kwargs))
        if isinstance(a,PredicatePath):
            raise ValueError(("Invalid PredicatePath argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(a,qcond,args,kwargs))

    def instantiate(cond):
        if isinstance(cond,PredicatePath): return cond
        elif isinstance(cond,FuncConditionWrapper): return cond
        elif callable(cond): return FuncConditionWrapper(cond,*args,**kwargs)
        elif isinstance(cond,_PositionalPlaceholder):
            if cond.posn < len(args): return args[cond.posn]
            raise ValueError(("Missing positional placeholder argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(cond,qcond,args,kwargs))
        elif isinstance(cond,_NamedPlaceholder):
            v = kwargs.get(cond.name,None)
            if v: return v
            if cond.has_default: return cond.default
            raise ValueError(("Missing named placeholder argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(cond,qcond,args,kwargs))
        elif isinstance(cond,Conditional):
            newsubargs = []
            changed=False
            for subarg in cond.args:
                newsubarg = instantiate(subarg)
                if newsubarg is not subarg: changed=True
                newsubargs.append(newsubarg)
            if changed: return Conditional(cond.operator,*newsubargs)
        return cond

    # argument values cannot be a placeholder or predicatepath
    for a in args: checkarg(a)
    for a in kwargs.values(): checkarg(a)

    return instantiate(qcond)

# ------------------------------------------------------------------------------
# Evaluate whether a given fact satisfies a query condition. Note: the function
# will raise exceptions if there are any placeholders. So you should only use
# this function with the output instantiate_query_condition().
# ------------------------------------------------------------------------------

def evaluate_query_condition(qcond, fact):

    # Get the value of a leaf argument - special case for predicate tuples
    def getargval(arg):
        if isinstance(arg, PredicatePath):
            v = arg(fact)
            if isinstance(v,Predicate) and v.meta.is_tuple: return tuple(v)
            return v
        elif isinstance(arg, Placeholder):
            raise ValueError(("Unresolved Placeholder {} in "
                             "query condition {}").format(arg, qcond))
        return arg

    # Evaluate query conditions with a boolean operator
    def evaluate_bool_condition(bcond):
        if bcond.operator == operator.not_:
            return operator.not_(evaluate(bcond.args[0]))
        elif bcond.operator == operator.and_:
            for subcond in bcond.args:
                if not evaluate(subcond): return False
            return True
        elif bcond.operator == operator.or_:
            for subcond in bcond.args:
                if evaluate(subcond): return True
            return False
        raise TypeError(("Internal bug: unknown boolean operator {} in query "
                          "condition {}").format(bcond.operator, qcond))

    # Evaluate query conditions with a comparison operator
    def evaluate_comp_condition(ccond):
        args=[ getargval(a) for a in ccond.args ]
        return ccond.operator(*args)

    # Evaluate an arbitrary query condition
    def evaluate(cond):
        if isinstance(cond,Conditional):
            if Conditional.operators[cond.operator].isbool:
                return evaluate_bool_condition(cond)
            else:
                return evaluate_comp_condition(cond)
        elif isinstance(cond,FuncConditionWrapper):
            return cond(fact)
        elif callable(cond):
            raise TypeError(("Functor '{}' in '{}' has not been wrapped in a "
                             "FuncConditionWrapper object").format(cond,qcond))
        return bool(cond)

    return evaluate(qcond)

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
# Select is an interface query over a FactBase.
# ------------------------------------------------------------------------------

class Select(abc.ABC):

    @abc.abstractmethod
    def where(self, *expressions):
        """Set the select statement's where clause.

        The where clause consists of a set of comparison expressions. A
        comparison expression is simply a test functor that takes a predicate
        instance and returns whether or not that instance satisfies some
        requirement. Hence any lambda or function with this signature can be
        passed.

        Such test functors can also be generated using a more natural syntax,
        simply by making a boolean comparison between a field and a some other
        object. This is acheived by overloading the field boolean comparison
        operators to return a functor.

        The second parameter can point to an arbitrary value or a special
        placeholder value that issubstituted when the query is actually
        executed. These placeholders are named ``ph1_``, ``ph2_``, ``ph3_``, and
        ``ph4_`` and correspond to the 1st to 4th arguments of the ``get``,
        ``get_unique`` or ``count`` function call.

        Args:
          expressions: one or more comparison expressions.

        """
        pass

    @abc.abstractmethod
    def order_by(self, *fieldorder):
        """Provide an ordering over the results."""
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

    @abc.abstractmethod
    def where(self, *expressions):
        pass

    @abc.abstractmethod
    def execute(self, *args, **kwargs):
        pass

#------------------------------------------------------------------------------
# Specification of an ordering over a field of a predicate/complex-term
#------------------------------------------------------------------------------
class OrderBy(object):
    def __init__(self, path, asc):
        self._path = path
        self.asc = asc
    def compare(self, a,b):
        va = self._path(a)
        vb = self._path(b)
        if  va == vb: return 0
        if self.asc and va < vb: return -1
        if not self.asc and va > vb: return -1
        return 1

    @property
    def path(self):
        return self._path

    def __str__(self):
        return "OrderBy(path={},asc={})".format(self._path, self.asc)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Helper functions to return a OrderBy in descending and ascending order. Input
# is a PredicatePath. The ascending order function is provided for completeness
# since the order_by parameter will treat a path as ascending order by default.
# ------------------------------------------------------------------------------
def desc(path):
    return OrderBy(path,asc=False)
def asc(path):
    return OrderBy(path,asc=True)

#------------------------------------------------------------------------------
# Helper function to check a where clause for errors
#------------------------------------------------------------------------------
def _check_where_clause(where, ptype):
    # Note: the expression may not be a Condition, in which case at least check
    # that it is a function/functor
    try:
        check_query_condition(where)
        hashable_paths = _hashable_paths(where)

        for p in hashable_paths:
            if p.path.meta.predicate != ptype:
                msg = ("'where' expression contains path '{}' that doesn't match "
                       "predicate type '{}'").format(p.path, ptype.__name__)
                raise TypeError(msg)

    except AttributeError:
        if not callable(where):
            raise TypeError("'{}' object is not callable".format(type(where).__name__))


#------------------------------------------------------------------------------
# A selection over a _FactMap
#------------------------------------------------------------------------------

class _Select(Select):

    def __init__(self, factmap):
        self._factmap = factmap
        self._index_priority = { path.meta.hashable: idx \
                                 for (idx,path) in enumerate(factmap.indexes) }
        self._where = None
        self._indexable = None
        self._key = None

    def where(self, *expressions):
        if self._where:
            raise TypeError("cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("empty 'where' expression")
        elif len(expressions) == 1:
#            self._where = expressions[0]
            self._where = simplify_query_condition(expressions[0])
        else:
#            self._where = and_(*expressions)
            self._where = simplify_query_condition(and_(*expressions))

        self._indexable = self._primary_search(self._where)

        # Check that the where clause only refers to the correct predicate
        _check_where_clause(self._where, self._factmap.predicate)
        return self

    @property
    def has_where(self):
        return bool(self._where)

    def order_by(self, *expressions):
        if self._key:
            raise TypeError("cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("empty 'order_by' expression")
        field_orders = []
        # If a PredicatePath is specified assume ascending order
        for exp in expressions:
            if isinstance(exp, OrderBy): field_orders.append(exp)
            elif isinstance(exp, PredicatePath):
                field_orders.append(asc(exp))
            else: raise TypeError("Invalid 'order_by' expression: {}".format(exp))

        # Check that all the paths refer to the correct predicate type
        ptype = self._factmap.predicate
        for f in field_orders:
            if f.path.meta.predicate != ptype:
                msg = ("'order_by' expression contains path '{}' that doesn't match "
                       "predicate type '{}'").format(f.path, ptype.__name__)
                raise TypeError(msg)


        # Create a comparator function
        def mycmp(a, b):
            for ford in field_orders:
                value = ford.compare(a,b)
                if value == 0: continue
                return value
            return 0

        self._key = functools.cmp_to_key(mycmp)
        return self

    def _primary_search(self, cond):

        def get_indexable(where):
            if isinstance(where.args[1], PredicatePath): return None
            return (where.args[0], where.operator, where.args[1])

        def validate_indexable(indexable):
            if not indexable: return None
            if indexable[0].meta.hashable not in self._index_priority: return None
            return indexable

        if isinstance(cond, Conditional) and not Conditional.operators[cond.operator].isbool:
            return validate_indexable(get_indexable(cond))
        indexable = None
        if isinstance(cond, Conditional) and cond.operator == operator.and_:
            for arg in cond.args:
                tmp = self._primary_search(arg)
                if tmp:
                    if not indexable: indexable = tmp
                    elif self._index_priority[tmp[0].meta.hashable] < \
                         self._index_priority[indexable[0].meta.hashable]:
                        indexable = tmp
        return indexable

#    @property
    def _debug(self):
        return self._indexable

    # Function to execute the select statement
    def get(self, *args, **kwargs):

        if self._where is None:
            where = True
        else:
            where = instantiate_query_condition(self._where, *args, **kwargs)
            where = simplify_query_condition(where)

        indexable = self._primary_search(where)

        # If there is no index test all instances else use the index
        result = []
        if not indexable:
            for f in self._factmap.facts():
                if where is True: result.append(f)
                elif evaluate_query_condition(where,f): result.append(f)
        else:
            findex = self._factmap.get_factindex(indexable[0])
            value = indexable[2]
            field = findex.path.meta.field
            if field:
                cmplx = field.complex
                if cmplx and isinstance(value, tuple): value = cmplx(*value)
            for f in findex.find(indexable[1], value):
                if evaluate_query_condition(where,f): result.append(f)

        # Return the results - sorted if necessary
        if self._key: result.sort(key=self._key)
        return result

    def get_unique(self, *args, **kwargs):
        count=0
        fact=None
        for f in self.get(*args, **kwargs):
            fact=f
            count += 1
            if count > 1:
                raise ValueError("Multiple facts found - exactly one expected")
        if count == 0:
            raise ValueError("No facts found - exactly one expected")
        return fact

    def count(self, *args, **kwargs):
        return len(self.get(*args, **kwargs))

#------------------------------------------------------------------------------
# A deletion over a _FactMap
# - a stupid implementation that iterates over all facts and indexes
#------------------------------------------------------------------------------

class _Delete(Delete):

    def __init__(self, factmap):
        self._factmap = factmap
        self._select = _Select(factmap)

    def where(self, *expressions):
        self._select.where(*expressions)
        return self

    def execute(self, *args, **kwargs):
        # If there is no where clause then delete everything
        if not self._select.has_where:
            num_deleted = len(self._factmap.facts())
            self._factmap.clear()
            return num_deleted

        # Gather all the facts to delete and remove them
        to_delete = [ f for f in self._select.get(*args, **kwargs) ]
        for fact in to_delete: self._factmap.remove(fact)
        return len(to_delete)

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
        return _Select(self)

    def delete(self):
        return _Delete(self)

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
# A fact generator that takes a list of predicates to unify against (order
# matters) and a set of raw clingo symbols against this list.
# ------------------------------------------------------------------------------

def _unify(predicates, symbols):
    def unify_single(cls, r):
        try:
            return cls._unify(r)
        except ValueError:
            return None

    # To make things a little more efficient use the name/arity signature as a
    # filter. However, Python doesn't have a built in multidict class, and I
    # don't want to add a dependency to an external library just for one small
    # feature, so implement a simple structure here.
    sigs = [((cls.meta.name, len(cls.meta)),cls) for cls in predicates]
    types = {}
    for sig,cls in sigs:
        if sig not in types: types[sig] = [cls]
        else: types[sig].append(cls)

    # Loop through symbols and yield when we have a match
    for raw in symbols:
        classes = types.get((raw.name, len(raw.arguments)))
        if not classes: continue
        for cls in classes:
            f = unify_single(cls,raw)
            if f:
                yield f
                break


#------------------------------------------------------------------------------
# SymbolPredicateUnifier offers a decorator interface for gathering predicate and index
# definitions to be used in defining a FactBase subclass.
# ------------------------------------------------------------------------------
class SymbolPredicateUnifier(object):
    """A fact base builder simplifies the task of unifying raw clingo.Symbol objects
    with Clorm predicates. Predicates classes are registered using the
    'register' function (which can be called as a normal function or as a class
    decorator.
    """

    def __init__(self, predicates=[], indexes=[], suppress_auto_index=False):
        self._predicates = ()
        self._indexes = ()
        self._suppress_auto_index = suppress_auto_index
        tmppreds = []
        tmpinds = []
        tmppredset = set()
        tmpindset = set()
        for pred in predicates:
                self._register_predicate(pred,tmppreds,tmpinds,tmppredset,tmpindset)
        for fld in indexes:
                self._register_index(fld,tmppreds,tmpinds,tmppredset,tmpindset)
        self._predicates = tuple(tmppreds)
        self._indexes = tuple(tmpinds)

    def _register_predicate(self, cls, predicates, indexes, predicateset, indexset):
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        if cls in predicateset: return
        predicates.append(cls)
        predicateset.add(cls)
        if self._suppress_auto_index: return

        # Add all fields (and sub-fields) that are specified as indexed
        for fp in cls.meta.indexes:
            self._register_index(fp,predicates,indexes,predicateset,indexset)

    def _register_index(self, path, predicates, indexes, predicateset, indexset):
        if path.meta.hashable in indexset: return
        if isinstance(path, PredicatePath) and path.meta.predicate in predicateset:
            indexset.add(path.meta.hashable)
            indexes.append(path)
        else:
            raise TypeError("{} is not a predicate field for one of {}".format(
                path, [ p.__name__ for p in predicates ]))

    def register(self, cls):
        if cls in self._predicates: return cls
        predicates = list(self._predicates)
        indexes = list(self._indexes)
        tmppredset = set(self._predicates)
        tmpindset = set([p.meta.hashable for p in self._indexes])
        self._register_predicate(cls,predicates,indexes,tmppredset,tmpindset)
        self._predicates = tuple(predicates)
        self._indexes = tuple(indexes)
        return cls

    def unify(self, symbols, delayed_init=False, raise_on_empty=False):
        def _populate():
            facts=list(_unify(self.predicates, symbols))
            if not facts and raise_on_empty:
                raise ValueError("FactBase creation: failed to unify any symbols")
            return facts

        if delayed_init:
            return FactBase(facts=_populate, indexes=self._indexes)
        else:
            return FactBase(facts=_populate(), indexes=self._indexes)

    @property
    def predicates(self): return self._predicates
    @property
    def indexes(self): return self._indexes

#------------------------------------------------------------------------------
# Generate facts from an input array of Symbols.  The `unifier` argument takes a
# list of predicate classes or a SymbolPredicateUnifer object to unify against
# the symbol object contained in `symbols`.
# ------------------------------------------------------------------------------

def unify(unifier,symbols,ordered=False):
    '''Unify raw symbols against a list of predicates or a SymbolPredicateUnifier.

    Symbols are tested against each predicate unifier until a match is
    found. Since it is possible to define multiple predicate types that can
    unify with the same symbol, the order of the predicates in the unifier
    matters. With the `ordered` option set to `True` a list is returned that
    preserves the order of the input symbols.

    Args:
      unifier: a list of predicate classes or a SymbolPredicateUnifier object.
      symbols: the symbols to unify.
      ordered (default: False): optional to return a list rather than a FactBase.
    Return:
      a FactBase containing the unified facts, indexed by any specified indexes,
         or a list if the ordered option is specified

    '''
    if not unifier:
        raise ValueError(("The unifier must be a list of predicates "
                          "or a SymbolPredicateUnifier"))
    if ordered:
        if isinstance(unifier, SymbolPredicateUnifier):
            unifier=unifier.predicates
        return list(_unify(unifier,symbols))
    else:
        if not isinstance(unifier, SymbolPredicateUnifier):
            unifier=SymbolPredicateUnifier(predicates=unifier)
        return unifier.unify(symbols)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
