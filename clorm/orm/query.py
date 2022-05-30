# -----------------------------------------------------------------------------
# Clorm ORM FactBase query implementation. It provides the rich query API.
# ------------------------------------------------------------------------------

import io
import sys
import operator
import collections
import bisect
import abc
import functools
import itertools
import inspect
import enum
from typing import Any, Generator

from ..util import OrderedSet as FactSet
from ..util.tools import all_equal
from .core import *
from .core import get_field_definition, QCondition, PredicatePath, \
    validate_root_paths, kwargs_check_keys, trueall, falseall, notcontains
from .factcontainers import FactSet, FactIndex, FactMap

__all__ = [
    'Query',
    'Placeholder',
    'desc',
    'asc',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'func',
    'fixed_join_order',
    'basic_join_order',
    'oppref_join_order',
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

    r"""An abstract class for defining parameterised queries.

    Currently, Clorm supports 4 placeholders: ph1\_, ph2\_, ph3\_, ph4\_. These
    correspond to the positional arguments of the query execute function call.

    """
    @abc.abstractmethod
    def __eq__(self, other): pass

    @abc.abstractmethod
    def __hash__(self): pass


class NamedPlaceholder(Placeholder):

    # Only keyword arguments are allowd. Note: None could be a legitimate value
    # so cannot use it to test for default
    def __init__(self, *, name, **kwargs):
        self._name = name
        # Check for unexpected arguments
        badkeys = kwargs_check_keys(set(["default"]), set(kwargs.keys()))
        if badkeys:
            mstr = "Named placeholder unexpected keyword arguments: "
            raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

        # Set the keyword argument
        if "default" in kwargs: self._default = (True, kwargs["default"])
#        elif len(args) > 1
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
        if not isinstance(other, NamedPlaceholder): return NotImplemented
        if self.name != other.name: return False
        if self._default != other._default: return False
        return True
    def __hash__(self):
        return hash(self._name)

class PositionalPlaceholder(Placeholder):
    def __init__(self, *, posn):
        self._posn = posn
    @property
    def posn(self):
        return self._posn
    def __str__(self):
        return "ph{}_".format(self._posn+1)
    def __repr__(self):
        return self.__str__()
    def __eq__(self, other):
        if not isinstance(other, PositionalPlaceholder): return NotImplemented
        return self._posn == other._posn
    def __hash__(self):
        return hash(self._posn)

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
        return NamedPlaceholder(**nkargs)

    # Its a positional placeholder
    if default[0]:
        raise TypeError("Positional placeholders don't support default values")
    idx -= 1
    if idx < 0:
        raise ValueError("Index {} is not a positional argument".format(idx+1))
    return PositionalPlaceholder(posn=idx)

#------------------------------------------------------------------------------
# Some pre-defined positional placeholders
#------------------------------------------------------------------------------

ph1_ = PositionalPlaceholder(posn=0)
ph2_ = PositionalPlaceholder(posn=1)
ph3_ = PositionalPlaceholder(posn=2)
ph4_ = PositionalPlaceholder(posn=3)


# ------------------------------------------------------------------------------
# API function to build a functor wrapper object as part of a specifying a where
# clause or an output statement.
# ------------------------------------------------------------------------------

FuncInputSpec = collections.namedtuple('FuncInputSpec', 'paths functor')
def func(paths, func):
    '''Wrap a boolean functor with predicate paths for use as a query condition'''
    return FuncInputSpec(paths,func)
    return FunctionComparator.from_specification(paths,func)

# ------------------------------------------------------------------------------
# QCondition objects are generated by the Clorm API. But we want to treat the
# different components differently depending on whether they are a comparison
# (either using standard operators or using a functor), or a boolean, or a join
# condition.
#
# So we create separate classes for the different components.  Note: these
# object are treated as immutable. So when manipulating such objects the
# following functions make modified copies of the objects rather than modifying
# the objects themselves. So if a function doesn't need to modify an object at
# all it simply returns the object itself.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Support function returns True if all the elements of the list are root paths
# ------------------------------------------------------------------------------

def is_root_paths(paths):
    for raw in paths:
        p = path(raw)
        if not p.meta.is_root: return False
    return True

# ------------------------------------------------------------------------------
# Support function to make sure we have a list of paths
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# support function - give an iterable that may include a predicatepath return a
# list copy where any predicatepaths are replaced with hashable paths. Without
# this comparison operators will fail.
# ------------------------------------------------------------------------------

def _hashables(seq):
    f = lambda x : x.meta.hashable if isinstance(x,PredicatePath) else x
    return map(f,seq)


# ------------------------------------------------------------------------------
# MembershipSeq is used for holding a reference to some form of sequence that is
# used as part of a query membership "in_" (or "notin_") condition. When a query
# is executed the sequence is turned into a set which is then used for
# membership comparisons. So any update of the reference sequence after the
# query is declared but before the query is executed will affect the execution
# of the query. It also also for the sequence to be specified as a sub-query.
# ------------------------------------------------------------------------------

class MembershipSeq(object):

    def __init__(self, src):
        self._src = src

    def fixed(self):
        if isinstance(self._src, Placeholder):
            raise ValueError(("Cannot fix unground sequence specification : "
                              "{}").format(self))
        if isinstance(self._src, Query):
            return frozenset(self._src.all())
        else:
             return frozenset(self._src)

    def ground(self,*args,**kwargs):
        def get(arg):
            if not isinstance(arg,Placeholder): return arg
            if isinstance(arg,PositionalPlaceholder):
                if arg.posn < len(args): return args[arg.posn]
                raise ValueError(("Missing positional placeholder argument '{}' "
                                  "when grounding '{}' with positional arguments: "
                                  "{}").format(arg,self,args))
            elif isinstance(arg,NamedPlaceholder):
                v = kwargs.get(arg.name,None)
                if v: return v
                if arg.has_default: return arg.default
                raise ValueError(("Missing named placeholder argument '{}' "
                                  "when grounding '{}' with arguments: "
                                  "{}").format(arg,self,kwargs))


        if isinstance(self._src, Query):
            where = self._src.qspec.where
            if where is None: return self
            return MembershipSeq(self._src.bind(*args,**kwargs))

        elif not isinstance(self._src, Placeholder): return self
        return MembershipSeq(get(self._src))

    @property
    def placeholders(self):
        if isinstance(self._src, Placeholder): return set([self._src])
        elif not isinstance(self._src, Query): return set()
        where = self._src.qspec.where
        if where is None: return set()
        return where.placeholders

    def __eq__(self,other):
        if not isinstance(other, MembershipSeq): return NotImplemented
        return self._src is other._src

    def __hash__(self):
        return hash(id(self._src))

    def __str__(self):
        return "MS:{}".format(self._src.__str__())
        return self._src.__str__()

    def __repr__(self):
        return self._src.__repr__()


# ------------------------------------------------------------------------------
# functions to validate a QCondition objects for a standard comparator objects
# from QCondition objects for either a join or where condition. Returns a pair
# consisting of the operator and validated and normalised arguments. The
# function will raise exceptions if there are any problems.
# ------------------------------------------------------------------------------

def _normalise_op_args(arg):
    p=path(arg,exception=False)
    if p is None: return arg
    return p

def _is_static_op_arg(arg):
    return not isinstance(arg,PredicatePath)

def where_comparison_op(qcond):
    newargs = [_normalise_op_args(a) for a in qcond.args]

    if all(map(_is_static_op_arg, newargs)):
        raise ValueError(("Invalid comparison of only static inputs "
                          "(at least one argument must reference a "
                          "a component of a fact): {}").format(qcond))

    spec = StandardComparator.operators.get(qcond.operator,None)
    if spec is None:
        raise TypeError(("Internal bug: cannot create StandardComparator() with "
                         "non-comparison operator '{}' ").format(qcond.operator))
    if not spec.where and spec.join:
        raise ValueError(("Invalid 'where' comparison operator '{}' is only "
                          "valid for a join specification").format(qcond.operator))
    return (qcond.operator,newargs)

def where_membership_op(qcond):
    pth = _normalise_op_args(qcond.args[1])
    seq = qcond.args[0]
    if not isinstance(pth,PredicatePath):
        raise ValueError(("Invalid 'where' condition '{}': missing path in "
                          "membership declaration").format(qcond))
    if isinstance(seq,PredicatePath):
        raise ValueError(("Invalid 'where' condition '{}': invalid sequence in "
                          "membership declaration").format(qcond))

    return (qcond.operator, [MembershipSeq(seq),pth])

def join_comparison_op(qcond):
    if qcond.operator == falseall:
        raise ValueError("Internal bug: cannot use falseall operator in QCondition")

    paths = list(filter(lambda x: isinstance(x,PredicatePath), qcond.args))
    paths = set(map(lambda x: hashable_path(x), paths))
    roots = set(map(lambda x: hashable_path(path(x).meta.root), paths))
    if len(roots) != 2:
        raise ValueError(("Invalid join expression '{}'. A join expression must join "
                          "paths with two distinct predicate roots").format(qcond))

    if qcond.operator == trueall:
        if paths != roots:
            raise ValueError(("Cross-product expression '{}' must contain only "
                              "root paths").format(qcond))
    return (qcond.operator,qcond.args)


# ------------------------------------------------------------------------------
# keyable functions are operator specific functions to extract keyable/indexable
# information form StandardComparator instances. This is then used to give keyed
# lookups on a FactIndex. If the function returns None then the comparator
# cannot be used to key on the given list of indexes.
# ------------------------------------------------------------------------------

def comparison_op_keyable(sc, indexes):
    indexes = set([hashable_path(p) for p in indexes])
    swapop = {
        operator.eq : operator.eq,  operator.ne : operator.ne,
        operator.lt : operator.gt,  operator.gt : operator.lt,
        operator.le : operator.ge,  operator.ge : operator.le,
        trueall : trueall,  falseall : falseall }

    def hp(a):
        try:
            return hashable_path(a)
        except:
            return a

    a0 = hp(sc.args[0])
    a1 = hp(sc.args[1])
    if isinstance(a0,PredicatePath.Hashable) and a0 in indexes:
        return (a0, sc.operator, sc.args[1])
    if isinstance(a1,PredicatePath.Hashable) and a1 in indexes:
        return (a1, swapop[sc.operator], sc.args[0])
    return None

def membership_op_keyable(sc,indexes):
    indexes = set([hashable_path(p) for p in indexes])
    hpa1 = hashable_path(sc.args[1])
    if hpa1 not in indexes: return None
    return (hpa1, sc.operator, sc.args[0])



# ------------------------------------------------------------------------------
# Comparator for the standard operators
#
# Implementation detail: with the use of membership operators
# ('operator.contains' and 'notcontains') we want to pass an arbitrary sequence
# to the object. This object may be mutable and will therefore not be
# hashable. To support hashing and adding comparators to a set, the hash of the
# comparator only takes into account predicate paths. The main thing is that
# equality works properly. While this is a bit of a hack I think it is ok
# provided StandardComparator is used only in this specific way within clorm and
# is not exposed outside clorm.
# ------------------------------------------------------------------------------

class StandardComparator(Comparator):
    class Preference(enum.IntEnum):
        LOW= 0
        MEDIUM= 1
        HIGH=2

    OpSpec = collections.namedtuple('OpSpec','pref join where negop swapop keyable form')
    operators = {
        operator.eq : OpSpec(pref=Preference.HIGH,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.ne, swapop=operator.eq,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        operator.ne : OpSpec(pref=Preference.LOW,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.eq, swapop=operator.ne,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        operator.lt : OpSpec(pref=Preference.MEDIUM,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.ge, swapop=operator.gt,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        operator.le : OpSpec(pref=Preference.MEDIUM,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.gt, swapop=operator.ge,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        operator.gt : OpSpec(pref=Preference.MEDIUM,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.le, swapop=operator.lt,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        operator.ge : OpSpec(pref=Preference.MEDIUM,
                             join=join_comparison_op,
                             where=where_comparison_op,
                             negop=operator.lt, swapop=operator.le,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.INFIX),
        trueall     : OpSpec(pref=Preference.LOW,
                             join=join_comparison_op,
                             where=None,
                             negop=falseall, swapop=trueall,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.FUNCTIONAL),
        falseall    : OpSpec(pref=Preference.HIGH,
                             join=join_comparison_op,
                             where=None,
                             negop=trueall, swapop=falseall,
                             keyable=comparison_op_keyable,
                             form=QCondition.Form.FUNCTIONAL),
        operator.contains : OpSpec(pref=Preference.HIGH,
                                   join=None,
                                   where=where_membership_op,
                                   negop=notcontains, swapop=None,
                                   keyable=membership_op_keyable,
                                   form=QCondition.Form.INFIX),
        notcontains       : OpSpec(pref=Preference.LOW,
                                   join=None,
                                   where=where_membership_op,
                                   negop=operator.contains, swapop=None,
                                   keyable=membership_op_keyable,
                                   form=QCondition.Form.INFIX)}

    def __init__(self,operator,args):
        spec = StandardComparator.operators.get(operator,None)
        if spec is None:
            raise TypeError(("Internal bug: cannot create StandardComparator() with "
                             "non-comparison operator '{}' ").format(operator))
        self._operator = operator
        self._args = tuple(args)
        self._hashableargs =tuple([ hashable_path(a) if isinstance(a,PredicatePath) \
                                    else a for a in self._args])
        self._paths=tuple(filter(lambda x : isinstance(x,PredicatePath),self._args))

        tmppaths = set([])
        tmproots = set([])
        for a in self._args:
            if isinstance(a,PredicatePath):
                tmppaths.add(hashable_path(a))
                tmproots.add(hashable_path(a.meta.root))
        self._paths=tuple([path(hp) for hp in tmppaths])
        self._roots=tuple([path(hp) for hp in tmproots])

    # -------------------------------------------------------------------------
    # non-ABC functions
    # -------------------------------------------------------------------------

    @classmethod
    def from_where_qcondition(cls,qcond):
        if not isinstance(qcond, QCondition):
            raise TypeError(("Internal bug: trying to make StandardComparator() "
                             "from non QCondition object: {}").format(qcond))

        spec = StandardComparator.operators.get(qcond.operator,None)
        if spec is None:
            raise TypeError(("Internal bug: cannot create StandardComparator() with "
                             "non-comparison operator '{}' ").format(qcond.operator))
        if not spec.where and spec.join:
            raise ValueError(("Invalid 'where' comparison operator '{}' is only "
                              "valid for a join specification").format(qcond.operator))
        if not spec.where:
            raise ValueError(("Invalid 'where' comparison operator "
                              "'{}'").format(qcond.operator))
        op, newargs = spec.where(qcond)
        return cls(op,newargs)

    @classmethod
    def from_join_qcondition(cls,qcond):
        if not isinstance(qcond, QCondition):
            raise TypeError(("Internal bug: trying to make Join() "
                             "from non QCondition object: {}").format(qcond))

        spec = StandardComparator.operators.get(qcond.operator,None)
        if spec is None:
            raise TypeError(("Internal bug: cannot create StandardComparator() with "
                             "non-comparison operator '{}' ").format(qcond.operator))

        if not spec.join and spec.where:
            raise ValueError(("Invalid 'join' comparison operator '{}' is only "
                              "valid for a join specification").format(qcond.operator))
        if not spec.join:
            raise ValueError(("Invalid 'join' comparison operator "
                              "'{}'").format(qcond.operator))

        op, newargs = spec.join(qcond)
        return cls(op,newargs)


    # -------------------------------------------------------------------------
    # Implement ABC functions
    # -------------------------------------------------------------------------

    def fixed(self):
        gself = self.ground()
        if gself._operator not in [ operator.contains, notcontains]: return gself
        elif isinstance(gself._args[0],frozenset): return gself
        elif not isinstance(gself._args[0],MembershipSeq):
            raise ValueError(("Internal error: unexpected sequence type object: "
                              "'{}'").format(gself._args[0]))
        return StandardComparator(self._operator,
                                  [gself._args[0].fixed(),gself._args[1]])

    def ground(self,*args,**kwargs):
        def get(arg):
            if not isinstance(arg,Placeholder): return arg
            if isinstance(arg,PositionalPlaceholder):
                if arg.posn < len(args): return args[arg.posn]
                raise ValueError(("Missing positional placeholder argument '{}' "
                                  "when grounding '{}' with positional arguments: "
                                  "{}").format(arg,self,args))
            elif isinstance(arg,NamedPlaceholder):
                v = kwargs.get(arg.name,None)
                if v: return v
                if arg.has_default: return arg.default
                raise ValueError(("Missing named placeholder argument '{}' "
                                  "when grounding '{}' with arguments: "
                                  "{}").format(arg,self,kwargs))

        if self._operator not in [ operator.contains, notcontains] or \
           not isinstance(self._args[0],MembershipSeq):
            newargs = tuple([get(a) for a in self._args])
        else:
            newargs = tuple([self._args[0].ground(*args,**kwargs), self._args[1]])

        if _hashables(newargs) == _hashables(self._args): return self
        return StandardComparator(self._operator, newargs)

    def negate(self):
        spec = StandardComparator.operators[self._operator]
        return StandardComparator(spec.negop, self._args)

    def dealias(self):
        def getdealiased(arg):
            if isinstance(arg,PredicatePath): return arg.meta.dealiased
            return arg
        newargs = tuple([getdealiased(a) for a in self._args])
        if _hashables(newargs) == _hashables(self._args): return self
        return StandardComparator(self._operator, newargs)

    def swap(self):
        spec = StandardComparator.operators[self._operator]
        if not spec.swapop:
            raise ValueError(("Internal bug: comparator '{}' doesn't support "
                              "the swap operation").format(self._operator))
        return StandardComparator(spec.swapop, reversed(self._args))

    def keyable(self, indexes):
        spec = StandardComparator.operators[self._operator]
        return spec.keyable(self, indexes)

    @property
    def paths(self):
        return self._paths

    @property
    def placeholders(self):
        tmp = set(filter(lambda x : isinstance(x,Placeholder), self._args))
        if self._operator not in [ operator.contains, notcontains]: return tmp
        elif not isinstance(self._args[0], MembershipSeq): return tmp
        tmp.update(self._args[0].placeholders)
        return tmp

    @property
    def preference(self):
        pref = StandardComparator.operators[self._operator].pref
        if pref is None:
            raise ValueError(("Operator '{}' does not have a join "
                              "preference").format(self._operator))
        return pref

    @property
    def form(self):
        return StandardComparator.operators[self._operator].form

    @property
    def operator(self):
        return self._operator

    @property
    def args(self):
        return self._args

    @property
    def roots(self):
        return self._roots

    @property
    def executable(self):
        for arg in self._args:
            if isinstance(arg,PositionalPlaceholder): return False
            if isinstance(arg,NamedPlaceholder) and \
               not arg.has_default: return False
        return True

    def make_callable(self, root_signature):
        for arg in self._args:
            if isinstance(arg,Placeholder):
                raise TypeError(("Internal bug: cannot make a non-ground "
                                 "comparator callable: {}").format(self))
        sig = make_input_alignment_functor(root_signature, self._args)
        return ComparisonCallable(self._operator,sig)

    def __eq__(self,other):
        def getval(val):
            if isinstance(val,PredicatePath): return val.meta.hashable
            return val

        if not isinstance(other, StandardComparator): return NotImplemented
        if self._operator != other._operator: return False
        for a,b in zip(self._args,other._args):
            if getval(a) != getval(b):
                return False
        return True

    def __hash__(self):
        return hash((self._operator,) + self._hashableargs)

    def __str__(self):
        # For convenience just return a QCondition string
        return str(QCondition(self._operator, *self._args))

    def __repr__(self):
        return self.__str__()

# ------------------------------------------------------------------------------
# Comparator for arbitrary functions. From the API generated with func()
# The constructor takes a reference to the function and a path signature.
# ------------------------------------------------------------------------------

class FunctionComparator(Comparator):
    def __init__(self,func,path_signature,negative=False,assignment=None):
        self._func = func
        self._funcsig = collections.OrderedDict()
        self._pathsig = tuple([ hashable_path(p) for p in path_signature])
        self._negative = negative
        self._assignment = None if assignment is None else dict(assignment)
        self._placeholders = set()  # Create matching named placeholders

        # Calculate the root paths
        tmproots = set([])
        tmppaths = set([])
        for a in self._pathsig:
            if isinstance(a,PredicatePath.Hashable):
                tmppaths.add(a)
                tmproots.add(hashable_path(path(a).meta.root))
        self._paths=tuple([path(hp) for hp in tmppaths])
        self._roots=tuple([path(hp) for hp in tmproots])

        # The function signature must be compatible with the path signature
        funcsig = inspect.signature(func)
        if len(funcsig.parameters) < len(self._pathsig):
            raise ValueError(("More paths specified in the path signature '{}' "
                              "than there are in the function "
                              "signature '{}'").format(self._pathsig, funcsig))

        # Track the parameters that are not part of the path signature but are
        # part of the function signature. This determines if the
        # FunctionComparator is "ground".
        for i,(k,v) in enumerate(funcsig.parameters.items()):
            if i >= len(self._pathsig):
                self._funcsig[k]=v
                if assignment and k in assignment: continue
                if v.default == inspect.Parameter.empty:
                    ph = NamedPlaceholder(name=k)
                else:
                    ph = NamedPlaceholder(name=k,default=v.default)
                self._placeholders.add(ph)

        # Check the path signature
        if not self._pathsig:
            raise ValueError("Invalid empty path signature")

        for pp in self._pathsig:
            if not isinstance(pp,PredicatePath.Hashable):
                raise TypeError(("The boolean functor call signature must "
                                  "consist of predicate paths"))

        # if there is an assigned ordereddict then check the keys
        if self._assignment is not None:
            self._check_assignment()

        # Used for the hash function
        if self._assignment:
            self._assignment_tuple = tuple(self._assignment.items())
        else:
            self._assignment_tuple = ()


    #-------------------------------------------------------------------------
    # Internal function to check the assigment. Will set default values if the
    # assigment is non-None.
    # -------------------------------------------------------------------------
    def _check_assignment(self):
        assignmentkeys=set(list(self._assignment.keys()))
        funcsigkeys=set(list(self._funcsig.keys()))
        tmp = assignmentkeys-funcsigkeys
        if tmp:
            raise ValueError(("FunctionComparator is being given "
                             "an assignment for unrecognised function "
                             "parameters '{}'").format(tmp))

        unassigned = funcsigkeys-assignmentkeys
        if not unassigned: return

        # There are unassigned so check if there are default values
        tmp = set()
        for name in unassigned:
            default = self._funcsig[name].default
            if default == inspect.Parameter.empty:
                tmp.add(name)
            else:
                self._assignment[name] = default

        if tmp:
            raise ValueError(("Missing functor parameters for '{}'").format(tmp))

    @classmethod
    def from_specification(cls,paths,func):
        def get_paths():
            return [ path(p) for p in paths]
        return cls(func, get_paths())

    # -------------------------------------------------------------------------
    # ABC functions
    # -------------------------------------------------------------------------
    @property
    def form(self):
        return QCondition.Form.FUNCTIONAL

    @property
    def paths(self):
        return self._paths

    @property
    def placeholders(self):
        return set(self._placeholders)

    @property
    def roots(self):
        return self._roots

    @property
    def executable(self):
        for ph in self._placeholders:
            if not ph.has_default: return False
        return True

    def negate(self):
        neg = not self._negative
        return FunctionComparator(self._func,self._pathsig,neg,
                                          assignment=self._assignment)

    def dealias(self):
        newpathsig = [path(hp).meta.dealiased for hp in self._pathsig]
        if _hashables(newpathsig) == _hashables(self._pathsig): return self
        return FunctionComparator(self._func, newpathsig, self._negative,
                                          assignment=self._assignment)

    def fixed(self):
        return self.ground()

    def ground(self, *args, **kwargs):
        if self._assignment is not None: return self
        assignment = {}
        # Assign any positional arguments first then add the keyword arguments
        # and make sure there is no repeats. Finally, assign any placeholders
        # with defaults. Note: funcsig is an orderedDict
        for idx,(k,_) in enumerate(self._funcsig.items()):
            if idx >= len(args): break
            assignment[k] = args[idx]
        for k,v in kwargs.items():
            if k in assignment:
                raise ValueError(("Both positional and keyword values given "
                                  "for the argument '{}'").format(k))
            assignment[k] = v
        for ph in self._placeholders:
            if isinstance(ph, NamedPlaceholder) and ph.name not in assignment:
                if ph.has_default:
                    assignment[ph.name] = ph.default
                else:
                    raise ValueError(("Missing named placeholder argument '{}' "
                                      "when grounding '{}' with arguments: "
                                      "{}").format(ph.name,self,kwargs))

        return FunctionComparator(self._func,self._pathsig,
                                  self._negative,assignment)

    def make_callable(self, root_signature):
        if self._assignment is None:
            raise RuntimeError(("Internal bug: make_callable called on a "
                                "ungrounded object: {}").format(self))

        # from the function signature and the assignment generate the fixed
        # values for the non-path items
        funcsigparam = [ self._assignment[k] for k,_ in self._funcsig.items() ]
        outputsig = tuple(list(self._pathsig) + funcsigparam)
        alignfunc = make_input_alignment_functor(root_signature,outputsig)
        op = self._func if not self._negative else lambda *args : not self._func(*args)
        return ComparisonCallable(op,alignfunc)

    def __eq__(self, other):
        if not isinstance(other, FunctionComparator): return NotImplemented
        if self._func != other._func: return False
        if self._pathsig != other._pathsig: return False
        if self._negative != other._negative: return False
        if self._assignment != other._assignment: return False
        return True

    def __hash__(self):
        return hash((self._func,) + self._pathsig + self._assignment_tuple)

    def __str__(self):
        assignstr = ": {}".format(self._assignment) if self._assignment else ""
        funcstr = "func({}{}, {})".format(self._pathsig,assignstr,self._func,)
        if not self._negative: return funcstr
        return "not_({})".format(funcstr)

    def __repr__(self):
        return self.__str__()

# ------------------------------------------------------------------------------
# Comparators (Standard and Function) have a comparison function and input of
# some form; eg "F.anum == 3" has operator.eq_ and input (F.anum,3) where F.anum
# is a path and will be replaced by some fact sub-field value.
#
# We need to extract the field input from facts and then call the comparison
# function with the appropriate input. But it is not straight forward to get the
# field input. If the query search is on a single predicate type then the input
# will be a singleton tuple. However, if there is a join in the query there will
# be multiple elements to the tuple. Furthermore, the order of facts will be
# determined by the query optimiser as it may be more efficient to join X with Y
# rather than Y with X.
#
# With this complication we need a way to remap a search input fact-tuple into
# the expected form for each query condition component.
#
# make_input_alignment_functor() returns a function that takes a tuple
# of facts as given by the input signature and returns a tuple of values as
# given by the output signature.
# ------------------------------------------------------------------------------
def make_input_alignment_functor(input_root_signature, output_signature):

    # Input signature are paths that must correspond to predicate types
    def validate_input_signature():
        if not input_root_signature:
            raise TypeError("Empty input predicate path signature")
        inputs=[]
        try:
            for p in input_root_signature:
                pp = path(p)
                if not pp.meta.is_root:
                    raise ValueError("path '{}' is not a predicate root".format(pp))
                inputs.append(pp)
        except Exception as e:
            raise TypeError(("Invalid input predicate path signature {}: "
                              "{}").format(input_root_signature,e)) from None
        return inputs

    # Output signature are field paths or statics (but not placeholders)
    def validate_output_signature():
        if not output_signature: raise TypeError("Empty output path signature")
        outputs=[]
        for a in output_signature:
            p = path(a,exception=False)
            outputs.append(p if p else a)
            if p: continue
            if isinstance(a, Placeholder):
                raise TypeError(("Output signature '{}' contains a placeholder "
                                  "'{}'").format(output_signature,a))
        return outputs

    insig = validate_input_signature()
    outsig = validate_output_signature()

    # build a list of lambdas one for each output item that chooses the
    # appropriate item from the input.
    pp2idx = { hashable_path(pp) : idx for idx,pp in enumerate(insig) }
    getters = []
    for out in outsig:
        if isinstance(out,PredicatePath):
            idx = pp2idx.get(hashable_path(out.meta.root),None)
            if idx is None:
                raise TypeError(("Invalid signature match between {} and {}: "
                                 "missing input predicate path for "
                                 "{}").format(input_root_signature,
                                              output_signature,out))
            ag=out.meta.attrgetter
            getters.append(lambda facts, ag=ag, idx=idx: ag(facts[idx]))
        else:
            getters.append(lambda facts, out=out: out)

    getters = tuple(getters)

    # Create the getter
    def func(facts):
        try:
            return tuple(getter(facts) for getter in getters)
        except IndexError as e:
            raise TypeError(("Invalid input to getter function: expecting "
                             "a tuple with {} elements and got a tuple with "
                             "{}").format(len(insig),len(facts))) from None
        except TypeError as e:
            raise TypeError(("Invalid input to getter function: "
                             "{}").format(e)) from None
        except AttributeError as e:
            raise TypeError(("Invalid input to getter function: "
                             "{}").format(e)) from None
    return func


# ------------------------------------------------------------------------------
# ComparisonCallable is a functional object that wraps a comparison operator and
# ensures the comparison operator gets the correct input. The input to a
# ComparisonCallable is a tuple of facts (the form of which is determined by a
# signature) and returns whether the facts satisfy some condition.
# ------------------------------------------------------------------------------

class ComparisonCallable(object):
    def __init__(self, operator, getter_map):
        self._operator = operator
        self._getter_map = getter_map

    def __call__(self, facts):
        args = self._getter_map(facts)
        return self._operator(*args)


# ------------------------------------------------------------------------------
# 'Where' query clauses handling.
#
# The goal is to turn the where clause into a CNF clausal normal form. So
# functions to validate the 'where' clause and then turn it into NNF, then CNF,
# and then a pure clausal form.
# ------------------------------------------------------------------------------

g_bool_operators = {
    operator.and_ : True, operator.or_ : True, operator.not_ : True }

def is_boolean_qcondition(cond):
#    if isinstance(cond, FunctionComparator): return False
    if isinstance(cond, FuncInputSpec): return False
    elif not isinstance(cond, QCondition): return False
    v = g_bool_operators.get(cond.operator,False)
    return v

def is_comparison_qcondition(cond):
    if not isinstance(cond, QCondition): return False
    spec = StandardComparator.operators.get(cond.operator,None)
    if not spec: return False
    return True

# ------------------------------------------------------------------------------
# Validates and turns non-boolean QCondition objects into the appropriate
# comparator (functors are wrapped in a FunctionComparator object - and
# FuncInputSpec are also turned into FunctionComparator objects).  Also
# simplifies any static conditions (conditions that can be evaluated without a
# fact) which are replaced with their a boolean evaluation.
#
# The where expression is validated with respect to a sequence of predicate root
# paths that indicate the valid predicates (and aliases) that are being
# reference in the query.
# ------------------------------------------------------------------------------

def validate_where_expression(qcond, roots=[]):

    # Make sure we have a set of hashable paths
    try:
        roots = set([ hashable_path(r) for r in roots ])
    except Exception as e:
        raise ValueError(("Invalid predicate paths signature {}: "
                          "{}").format(roots,e)) from None
    for pp in roots:
        if not pp.path.meta.is_root:
            raise ValueError(("Invalid roots element {} does not refer to "
                              "the root of a predicate path ").format(pp))

    # Check that the path is a sub-path of one of the roots
    def check_path(path):
        if hashable_path(path.meta.root) not in roots:
            raise ValueError(("Invalid 'where' expression '{}' contains a path "
                              "'{}' that is not a sub-path of one of the "
                              "roots '{}'").format(qcond, path, roots))

    # Check if a condition is static - to be called after validating the
    # sub-parts of the conidition.
    def is_static_condition(cond):
        if isinstance(cond,Comparator): return False
        if isinstance(cond,QCondition): return False
        if callable(cond):
            raise TYpeError(("Internal bug: invalid static test "
                             "with callable: {}").format(cond))
        return True

    # Check callable - construct a FunctionComparator
    def validate_callable(func):
        if len(roots) != 1:
            raise ValueError(("Incompatible usage between raw functor {} and "
                              "non-singleton predicates {}").format(func,roots))
        return FunctionComparator.from_specification(roots,func)

    # Check boolean condition - simplifying if it is a static condition
    def validate_bool_condition(bcond):
        if bcond.operator == operator.not_:
            newsubcond = validate_condition(bcond.args[0])
            if is_static_condition(newsubcond): return bcond.operator(newsubcond)
            if newsubcond == bcond.args[0]: return bcond
            return QCondition(bcond.operator,newsubcond)
        newargs = [validate_condition(a) for a in bcond.args]
        if is_static_condition(newargs[0]) and is_static_condition(newargs[1]):
            return bcond.operator(newargs[0],newargs[1])
        if bcond.operator == operator.and_:
            if is_static_condition(newargs[0]):
                return False if not newargs[0] else newargs[1]
            if is_static_condition(newargs[1]):
                return False if not newargs[1] else newargs[0]
        if bcond.operator == operator.or_:
            if is_static_condition(newargs[0]):
                return True if newargs[0] else newargs[1]
            if is_static_condition(newargs[1]):
                return True if newargs[1] else newargs[0]
        if bcond.args == newargs: return bcond
        return QCondition(bcond.operator,*newargs)

    # Check comparison condition - at least one argument must be a predicate path
    def validate_comp_condition(ccond):
        for a in ccond.args:
            if isinstance(a,PredicatePath): check_path(a)
        return StandardComparator.from_where_qcondition(ccond)

    # Validate a condition
    def validate_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid 'where' condition '{}' in query '{}': a "
                              "placeholder must be part of a comparison "
                              "condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid 'where' condition '{}' in query '{}': a "
                              "reference to fact (or fact field) must be part of "
                              "a comparison condition").format(cond, qcond))

        if callable(cond): return validate_callable(cond)
        elif isinstance(cond,FuncInputSpec):
            return FunctionComparator.from_specification(cond.paths,cond.functor)
        elif isinstance(cond,Comparator): return cond
        elif is_boolean_qcondition(cond): return validate_bool_condition(cond)
        elif is_comparison_qcondition(cond): return validate_comp_condition(cond)
        else: return bool(cond)

#    where = validate_condition(qcond)
#    hroots = set([ hashable_path(r) for r in where.roots])
    return  validate_condition(qcond)

# ------------------------------------------------------------------------------
# negate a query condition and push the negation into the leaf nodes - note:
# input must have already been validated. Because we can negate all comparison
# conditions we therefore end up with no explicitly negated boolean conditions.
# ------------------------------------------------------------------------------
def negate_where_expression(qcond):

    # Note: for the not operator negate twice to force negation inward
    def negate_bool_condition(bcond):
        if bcond.operator == operator.not_:
            return negate_condition(negate_condition(bcond.args[0]))
        if bcond.operator == operator.and_:
            return or_(negate_condition(bcond.args[0]),
                       negate_condition(bcond.args[1]))
        if bcond.operator == operator.or_:
            return and_(negate_condition(bcond.args[0]),
                        negate_condition(bcond.args[1]))
        raise TypeError(("Internal bug: unknown boolean operator '{}' in query "
                         "condition '{}'").format(bcond.operator, qcond))

    # Negate the condition
    def negate_condition(cond):
        if isinstance(cond, Comparator): return cond.negate()
        if not is_boolean_qcondition(cond):
            raise TypeError(("Internal bug: unexpected non-boolean condition '{}' "
                             "in query '{}'").format(cond, qcond))
        return negate_bool_condition(cond)

    return negate_condition(qcond)

# ------------------------------------------------------------------------------
# Convert the where expression to negation normal form by pushing any negations
# inwards. Because we can negate all comparators we therefore end up with no
# explicit negated boolean conditions. Note: input must have been validated
# ------------------------------------------------------------------------------
def where_expression_to_nnf(where):
    # Because negate_where_expression pushes negation inward, so negating twice
    # produces a formula in NNF
    return negate_where_expression(negate_where_expression(where))

# ------------------------------------------------------------------------------
# Convert the query condition to conjunctive normal form. Because we can negate
# all comparison conditions we therefore end up with no explicit negated boolean
# conditions.  Note: input must have been validated
# ------------------------------------------------------------------------------
def where_expression_to_cnf(qcond):

    def dist_if_or_over_and(bcond):
        if bcond.operator != operator.or_: return bcond
        if isinstance(bcond.args[0],QCondition):
            if bcond.args[0].operator == operator.and_:
                x = bcond.args[0].args[0]
                y = bcond.args[0].args[1]
                return and_(or_(x,bcond.args[1]),or_(y,bcond.args[1]))
        if isinstance(bcond.args[1],QCondition):
            if bcond.args[1].operator == operator.and_:
                x = bcond.args[1].args[0]
                y = bcond.args[1].args[1]
                return and_(or_(bcond.args[0],x),or_(bcond.args[0],y))
        return bcond

    def bool_condition_to_cnf(bcond):
        oldbcond = bcond
        while True:
            bcond = dist_if_or_over_and(oldbcond)
            if bcond is oldbcond: break
            oldbcond = bcond
        arg0 = condition_to_cnf(bcond.args[0])
        arg1 = condition_to_cnf(bcond.args[1])
        if arg0 is bcond.args[0] and arg1 is bcond.args[1]:
            return bcond
        return QCondition(bcond.operator,arg0,arg1)

    def condition_to_cnf(cond):
        if isinstance(cond, Comparator): return cond
        if not is_boolean_qcondition(cond):
            raise TypeError(("Internal bug: unexpected non-boolean condition '{}' "
                             "in 'where' expression '{}'").format(cond, qcond))
        if cond.operator == operator.not_:
            c1 = cond
            cond = where_expression_to_nnf(cond)
            if isinstance(cond,Comparator): return cond
        return bool_condition_to_cnf(cond)
    return condition_to_cnf(qcond)

# ------------------------------------------------------------------------------
# A Clause is a list of comparisons that should be interpreted as a disjunction.
# ------------------------------------------------------------------------------

class Clause(object):

    def __init__(self, comparators):
        if not comparators:
            raise ValueError("Empty list of comparison expressions")
        for comp in comparators:
            if not isinstance(comp,Comparator):
                raise ValueError(("Internal bug: only Comparator objects "
                                  "allowed: {} ").format(comp))
        self._comparators = tuple(comparators)

        tmppaths = set([])
        tmproots = set([])
        for comp in self._comparators:
            for p in comp.paths: tmppaths.add(hashable_path(p))
            for r in comp.roots: tmproots.add(hashable_path(r))
        self._paths=tuple([path(hp) for hp in tmppaths])
        self._roots=tuple([path(hp) for hp in tmproots])


    def make_callable(self, root_signature):
        callables = [ c.make_callable(root_signature) for c in self._comparators]
        callables = tuple(callables)
        def comparison_callable(facts):
            for c in callables:
                if c(facts): return True
            return False
        return comparison_callable

    @property
    def paths(self):
        return self._paths

    @property
    def placeholders(self):
        return set(itertools.chain.from_iterable(
            [p.placeholders for p in self._comparators]))

    @property
    def roots(self):
        return self._roots

    @property
    def executable(self):
        for c in self._comparators:
            if not c.executable: return False
        return True

    def dealias(self):
        newcomps = [ c.dealias() for c in self._comparators]
        if newcomps == self._comparators: return self
        return Clause(newcomps)

    def fixed(self):
        newcomps = tuple([ c.fixed() for c in self._comparators])
        if self._comparators == newcomps: return self
        return Clause(newcomps)

    def ground(self,*args, **kwargs):
        newcomps = tuple([ comp.ground(*args,**kwargs) for comp in self._comparators])
        if newcomps == self._comparators: return self
        return Clause(newcomps)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._comparators == other._comparators

    def __len__(self):
        return len(self._comparators)

    def __getitem__(self, idx):
        return self._comparators[idx]

    def __iter__(self):
        return iter(self._comparators)

    def __hash__(self):
        return hash(self._comparators)

    def __str__(self):
        return "[ {} ]".format(" | ".join([str(c) for c in self._comparators]))

    def __repr__(self):
       return self.__str__()


# ------------------------------------------------------------------------------
# A group of clauses. This should be interpreted as a conjunction of clauses.
# We want to maintain multiple blocks where each block is identified by a single
# predicate/alias root or by a catch all where there is more than one. The idea
# is that the query will consists of multiple queries for each predicate/alias
# type. Then the joins are performed and finally the joined tuples are filtered
# by the multi-root clause block.
# ------------------------------------------------------------------------------

class ClauseBlock(object):

    def __init__(self, clauses=[]):
        self._clauses = tuple(clauses)
        if not clauses:
            raise ValueError("Empty list of clauses")

        tmppaths = set([])
        tmproots = set([])
        for clause in self._clauses:
            if not isinstance(clause, Clause):
                raise ValueError(("A ClauseBlock must consist of a list of "
                                  "Clause elements. '{}' is of type "
                                  "'{}'").format(clause,type(clause)))
            for p in clause.paths: tmppaths.add(hashable_path(p))
            for r in clause.roots: tmproots.add(hashable_path(r))
        self._paths=tuple([path(hp) for hp in tmppaths])
        self._roots=tuple([path(hp) for hp in tmproots])

    @property
    def paths(self):
        return self._paths

    @property
    def placeholders(self):
        return set(itertools.chain.from_iterable(
            [c.placeholders for c in self._clauses]))

    @property
    def roots(self):
        return self._roots

    @property
    def clauses(self):
        return self._clauses

    @property
    def executable(self):
        for cl in self._clauses:
            if not cl.executable: return False
        return True

    def fixed(self):
        newclauses = tuple([cl.fixed() for cl in self._clauses])
        if self._clauses == newclauses: return self
        return ClauseBlock(newclauses)

    def ground(self,*args, **kwargs):
        newclauses = [ clause.ground(*args,**kwargs) for clause in self._clauses]
        if newclauses == self._clauses: return self
        return ClauseBlock(newclauses)

    def dealias(self):
        newclauses = [ c.dealias() for c in self._clauses]
        if newclauses == self._clauses: return self
        return ClauseBlock(newclauses)

    def make_callable(self, root_signature):
        callables = [ c.make_callable(root_signature) for c in self._clauses]
        callables = tuple(callables)
        def comparison_callable(facts):
            for c in callables:
                if not c(facts): return False
            return True
        return comparison_callable

    def __add__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return ClauseBlock(self._clauses + other._clauses)

    def __radd__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return ClauseBlock(other._clauses + self._clauses)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._clauses == other._clauses

    def __len__(self):
        return len(self._clauses)

    def __getitem__(self, idx):
        return self._clauses[idx]

    def __iter__(self):
        return iter(self._clauses)

    def __hash__(self):
        return hash(self._clauses)

    def __str__(self):
        return "( {} )".format(" & ".join([str(c) for c in self._clauses]))

    def __repr__(self):
       return self.__str__()

# ------------------------------------------------------------------------------
# Normalise takes a formula and turns it into a clausal CNF (a list of
# disjunctive clauses). Note: input must have been validated.
# ------------------------------------------------------------------------------
def normalise_where_expression(qcond):
    NEWCL = "new_clause"
    stack=[NEWCL]

    def is_leaf(arg):
        return isinstance(arg, Comparator)

    def stack_add(cond):
        if is_leaf(cond):
            stack.append(cond)
        else:
            for arg in cond.args:
                if cond.operator == operator.and_: stack.append(NEWCL)
                stack_add(arg)
                if cond.operator == operator.and_: stack.append(NEWCL)

    def build_clauses():
        clauses = []
        tmp = []
        for a in stack:
            if a == NEWCL:
                if tmp: clauses.append(Clause(tmp))
                tmp = []
            elif a != NEWCL:
                tmp.append(a)
        if tmp: clauses.append(Clause(tmp))
        return clauses

    stack.append(NEWCL)
    stack_add(where_expression_to_cnf(qcond))
    return (ClauseBlock(build_clauses()))


# ------------------------------------------------------------------------------
#  process_where takes a where expression from the user select statement as well
#  as a list of roots; validates the where statement (ensuring that it only
#  refers to paths derived from one of the roots) and turns it into CNF in the
#  form of a clauseblock.
#  ------------------------------------------------------------------------------

def process_where(where_expression, roots=[]):
    def _prevalidate(w):
        if isinstance(w,QCondition): return w
        if isinstance(w,Comparator): return w
        if callable(w) and not isinstance(w,PredicatePath): return w
        raise TypeError("'{}' is not a valid query 'where' expression".format(w))

    where = validate_where_expression(_prevalidate(where_expression),roots)
    return normalise_where_expression(where)

# ------------------------------------------------------------------------------
# Given a list of clauses breaks the clauses up into two pairs. The first
# contains a list of clausal blocks consisting of blocks for clauses that refer
# to only one root path. The second is a catch all block containing clauses that
# references multiple roots. The second can also be None. This is used to break
# up the query into separate parts for the different join components
# ------------------------------------------------------------------------------
def partition_clauses(clauses=[]):
    catchall = []
    root2clauses = {}
    # Separate the clauses
    for clause in clauses:
        roots = [hashable_path(p) for p in clause.roots]
        if len(roots) == 1:
            root2clauses.setdefault(roots[0],[]).append(clause)
        else:
            catchall.append(clause)

    # Generate clause blocks
    clauseblocks = []
    for root,clauses in root2clauses.items():
        clauseblocks.append(ClauseBlock(clauses))

    if catchall: return (clauseblocks, ClauseBlock(catchall))
    else: return (clauseblocks, None)

# ------------------------------------------------------------------------------
# To support database-like inner joins.  Join conditions are made from
# QCondition objects with the standard comparison operators
# ------------------------------------------------------------------------------

def is_join_qcondition(cond):
    if not isinstance(cond, QCondition): return False
    spec = StandardComparator.operators.get(cond.operator, None)
    if spec is None: return False
    return spec.join

# ------------------------------------------------------------------------------
# validate join expression. Turns QCondition objects into Join objects Note:
# joinall (the trueall operator) are used for ensure a connected graph but are
# then removed as they don't add anything.
# ------------------------------------------------------------------------------

def validate_join_expression(qconds, roots):
    jroots = set()    # The set of all roots in the join clauses
    joins = []        # The list of joins
    edges = {}       # Edges to ensure a fully connected graph

    def add_join(join):
        nonlocal edges, joins, jroots

        joins.append(join)
        jr = set([ hashable_path(r) for r in join.roots])
        jroots.update(jr)
        if len(jr) != 2:
            raise ValueError(("Internal bug: join specification should have "
                              "exactly two root paths: '{}'").format(jr))
        x,y = jr
        edges.setdefault(x,[]).append(y)
        edges.setdefault(y,[]).append(x)
        remain = jr - broots
        if remain:
            raise ValueError(("Join specification '{}' contains unmatched "
                              "root paths '{}'").format(jr,remain))

    # Check that the join graph is connected by counting the visited nodes from
    # some starting point.
    def is_connected():
        nonlocal edges, joins, jroots
        visited = set()
        def visit(r):
            visited.add(r)
            for c in edges[r]:
                if c in visited: continue
                visit(c)

        for start in jroots:
            visit(start)
            break
        return visited == jroots

    # Make sure we have a set of hashable paths
    try:
        broots = set([ hashable_path(root) for root in roots ])
    except Exception as e:
        raise ValueError(("Invalid predicate paths signature {}: "
                          "{}").format(roots,e)) from None
    if not broots:
        raise ValueError(("Specification of join without root paths "
                          "doesn't make sense"))
    for p in broots:
        if not p.path.meta.is_root:
            raise ValueError(("Invalid field specification {} does not refer to "
                              "the root of a predicate path ").format(p))

    for qcond in qconds:
        if not is_join_qcondition(qcond):
            if not isinstance(qcond,QCondition):
                raise ValueError(("Invalid join element '{}': expecting a "
                                  "comparison specifying the join "
                                  "between two fields").format(qcond))
            else:
                raise ValueError(("Invalid join operator '{}' in "
                                  "{}").format(qcond.operator,qcond))

        add_join(StandardComparator.from_join_qcondition(qcond))

    # Check that we have all roots in the join matches the base roots
    if jroots != broots:
        raise ValueError(("Invalid join specification: missing joins for "
                          "'{}'").format(broots-jroots))
    if not is_connected():
        raise ValueError(("Invalid join specification: contains un-joined "
                          "components '{}'").format(qconds))

    # Now that we've validated the graph can remove all the pure
    # cross-product/join-all joins.
    return list(filter(lambda x: x.operator != trueall, joins))


# ------------------------------------------------------------------------------
#  process_join takes a join expression (a list of join statements) from the
#  user select statement as well as a list of roots; validates the join
#  statements (ensuring that they only refers to paths derived from one of the
#  roots) and turns it into a list of validated StandardComparators that have
#  paths as both arguments
#  ------------------------------------------------------------------------------

def process_join(join_expression, roots=[]):
    def _prevalidate():
        for j in join_expression:
            if not isinstance(j,QCondition):
                raise TypeError("'{}' ({}) is not a valid 'join' in '{}'".format(
                    j,type(j),join_expression))
    _prevalidate()
    return validate_join_expression(join_expression,roots)


#------------------------------------------------------------------------------
# Specification of an ordering over a field of a predicate/complex-term
#------------------------------------------------------------------------------
class OrderBy(object):
    def __init__(self, path, asc):
        self._path = path
        self._asc = asc

    @property
    def path(self):
        return self._path

    @property
    def asc(self):
        return self._asc

    def dealias(self):
        dealiased = path(self._path).meta.dealiased
        if hashable_path(self._path) == hashable_path(dealiased): return self
        return OrderBy(dealiased,self._asc)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        if hashable_path(self._path) != hashable_path(other._path): return False
        return self._asc == other._asc

    def __hash__(self):
        return hash((hashable_path(self._path),self._asc))

    def __str__(self):
        if self._asc: return "asc({})".format(self._path)
        else: return "desc({})".format(self._path)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Helper functions to return a OrderBy in descending and ascending order. Input
# is a PredicatePath. The ascending order function is provided for completeness
# since the order_by parameter will treat a path as ascending order by default.
# ------------------------------------------------------------------------------
def desc(pth):
    return OrderBy(path(pth),asc=False)
def asc(pth):
    return OrderBy(path(pth),asc=True)

# ------------------------------------------------------------------------------
# OrderByBlock groups together an ordering of OrderBy statements
# ------------------------------------------------------------------------------

class OrderByBlock(object):
    def __init__(self,orderbys=[]):
        self._orderbys = tuple(orderbys)
        self._paths = tuple([path(ob.path) for ob in self._orderbys])
#        if not orderbys:
#            raise ValueError("Empty list of order_by statements")

    @property
    def paths(self):
        return self._paths

    @property
    def roots(self):
        return set([hashable_path(p.meta.root) for p in self._paths])

    def dealias(self):
        neworderbys = tuple([ob.dealias() for ob in self._orderbys])
        if self._orderbys == neworderbys: return self
        return OrderByBlock(neworderbys)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._orderbys == other._orderbys
        if isinstance(other, tuple):
            return self._orderbys == other
        if isinstance(other, list):
            return self._orderbys == tuple(other)
        return NotImplemented

    def __len__(self):
        return len(self._orderbys)

    def __getitem__(self, idx):
        return self._orderbys[idx]

    def __iter__(self):
        return iter(self._orderbys)

    def __hash__(self):
        return hash(self._orderbys)

    def __bool__(self):
        return bool(self._orderbys)

    def __str__(self):
        return "[{}]".format(",".join([str(ob) for ob in self._orderbys]))

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------
# Validate the order_by expression - returns an OrderByBlock
# ------------------------------------------------------------------------------

def validate_orderby_expression(orderby_expressions, roots=[]):
    if not is_root_paths(roots):
        raise ValueError("roots='{}' must contain only root paths".format(roots))
    hroots = set([hashable_path(rp) for rp in roots])

    path_ordering = []
    # If only a PredicatePath is specified assume ascending order
    for exp in orderby_expressions:
        if isinstance(exp, OrderBy): path_ordering.append(exp)
        elif isinstance(exp, PredicatePath):
            path_ordering.append(asc(exp))
        elif inspect.isclass(exp) and issubclass(exp, Predicate):
            path_ordering.append(asc(path(exp)))
        else: raise ValueError("Invalid 'order_by' expression: {}".format(exp))
    obb = OrderByBlock(path_ordering)

    if  not obb.roots.issubset(hroots):
        raise ValueError(("Invalid 'order_by' expression '{}' refers to root paths that "
                    "are not in '{}'").format(obb, hroots))
    return obb

# ------------------------------------------------------------------------------
# Return an OrderByBlock corresponding to the validated order by expression
# ------------------------------------------------------------------------------

def process_orderby(orderby_expressions, roots=[]):
    return validate_orderby_expression(orderby_expressions,roots)

# ------------------------------------------------------------------------------
# Return an OrderByBlock for an ordered flag
# ------------------------------------------------------------------------------

def process_ordered(roots):
    ordering=[asc(r) for r in roots]
    return OrderByBlock(ordering)

# ------------------------------------------------------------------------------
# make_prejoin_pair(indexed_paths, clauses)
#
# Given a set of indexed paths and a set of clauses that refer to a single root
# try to extract a preferred clause that can be used for indexing.
#
# - indexed_paths - a list of paths for which there is a factindex
# - clauses - a clause block that can only refer to a single root
# ------------------------------------------------------------------------------
def make_prejoin_pair(indexed_paths, clauseblock):
    def preference(cl):
        c = min(cl, key=lambda c: c.preference)
        return c.preference

    def is_candidate_sc(indexes, sc):
        if len(sc.paths) != 1: return False
        return hashable_path(sc.paths[0].meta.dealiased) in indexes

    def is_candidate(indexes, cl):
        for c in cl:
            if not isinstance(c, StandardComparator): return False
            if not is_candidate_sc(indexes,c): return False
        return True

    if not clauseblock: return (None,None)

    tmp = set([hashable_path(p.meta.dealiased) for p in clauseblock.paths])
    indexes = set(filter(lambda x: x in tmp,
                         [hashable_path(p) for p in indexed_paths]))

    # Search for a candidate to use with a fact index
    keyclause = None
    candidates = []
    rest = []
    for cl in clauseblock:
        if is_candidate(indexes, cl): candidates.append(cl)
        else: rest.append(cl)
    if not candidates: return (None, clauseblock)

    # order the candidates by their comparator preference and take the first
    candidates.sort(key=lambda cl : preference(cl), reverse=True)
    rest.extend(candidates[1:])
    cb = ClauseBlock(rest) if rest else None
    return (candidates[0],cb)

# ------------------------------------------------------------------------------
# make_join_pair(joins, clauseblock)
# - a list of join StandardComparators
# - an existing clauseblock (or None)
# - a list of orderby statements
#
# Takes a list of joins and picks the best one for indexing (based on their
# operator preference and the orderby statements). Returns a pair that is the
# chosen join and the rest of the joins added to the input clauseblock.
# ------------------------------------------------------------------------------
def make_join_pair(joins, clauseblock, orderbys=[]):
    opaths=set([hashable_path(ob.path) for ob in orderbys])
    def num(sc):
        return len(opaths & (set([hashable_path(p) for p in sc.paths])))

    if not joins: return (None,clauseblock)
    joins = sorted(joins, key=lambda x : (x.preference, num(x)), reverse=True)
    joinsc = joins[0]
    remainder = joins[1:]
    if remainder:
        remainder = ClauseBlock([Clause([sc]) for sc in remainder])
        if clauseblock: return (joinsc, clauseblock + remainder)
        else: return (joinsc, remainder)
    else:
        if clauseblock: return (joinsc, clauseblock)
        else: return (joinsc, None)

# ------------------------------------------------------------------------------
# JoinQueryPlan support functions. The JQP is a part of the query plan that
# describes the plan to execute a single link in a join.
# ------------------------------------------------------------------------------

# Check that the formula only refers to paths with the allowable roots
def _check_roots(allowable_roots, formula):
    if not formula: return True
    allowable_hroots = set([hashable_path(rp) for rp in allowable_roots])
    hroots = set([hashable_path(rp) for rp in formula.roots])
    return hroots.issubset(allowable_hroots)

# Align the arguments in a standard comparator so that the first argument is a
# path whose root is the given root
def _align_sc_path(root, sc):
    hroot = hashable_path(root)
    if not sc: return None
    if isinstance(sc.args[0], PredicatePath) and \
       hashable_path(sc.args[0].meta.root) == hroot: return sc
    sc = sc.swap()
    if not isinstance(sc.args[0], PredicatePath) or \
       hashable_path(sc.args[0].meta.root) != hroot:
        raise ValueError(("Cannot align key comparator '{}' with root '{}' since "
                          "it doesn't reference the root").format(root,sc))
    return sc

# Extract the placeholders
def _extract_placeholders(elements):
    output = set()
    for f in elements:
        if not f: continue
        output.update(f.placeholders)
    return output

# ------------------------------------------------------------------------------
# JoinQueryPlan class is a single join within a broader QueryPlan
# ------------------------------------------------------------------------------

class JoinQueryPlan(object):
    '''Input:
       - input_signature tuple,
       - root,
       - indexes associated with the underlying fact type
       - a prejoin clause for indexed quering (or None),
       - a prejoin clauseblock (or None),
       - a prejoin orderbyblock (or None)
       - a join standard comparator (or None),
       - a postjoin clauseblock (or None)
       - a postjoin orderbyblock (or None)
    '''
    def __init__(self,input_signature, root, indexes,
                 prejoincl, prejoincb, prejoinobb,
                 joinsc, postjoincb, postjoinobb):
        if not indexes: indexes = []
        self._insig = tuple([path(r) for r in input_signature])
        self._root = path(root)
        self._predicate = self._root.meta.predicate
        self._indexes = tuple([p for p in indexes \
                               if path(p).meta.predicate == self._predicate])
        self._joinsc = _align_sc_path(self._root, joinsc)
        self._postjoincb = postjoincb
        self._postjoinobb = postjoinobb
        self._prejoincl = prejoincl
        self._prejoincb = prejoincb
        self._prejoinobb = prejoinobb

        # Check that the input signature and root are valid root paths
        if not self._root.meta.is_root:
            raise ValueError("Internal bug: '{}' is not a root path".format(self._root))
        for p in self._insig:
            if not p.meta.is_root:
                raise ValueError(("Internal bug: '{}' in input signature is not a "
                                  "root path").format(p))

        # The prejoin parts must only refer to the dealised root
        if not _check_roots([self._root.meta.dealiased], prejoincl):
            raise ValueError(("Pre-join comparator '{}' refers to non '{}' "
                              "paths").format(prejoincl,self._root))
        if not _check_roots([self._root.meta.dealiased], prejoincb):
            raise ValueError(("Pre-join clause block '{}' refers to non '{}' "
                              "paths").format(prejoincb,self._root))
        if not _check_roots([self._root.meta.dealiased], prejoinobb):
            raise ValueError(("Pre-join clause block '{}' refers to non '{}' "
                              "paths").format(prejoinobb,self._root))

        # The joinsc cannot have placeholders
        if self._joinsc and self._joinsc.placeholders:
            raise ValueError(("A comparator with a placeholder is not valid as "
                              "a join specificaton: {}").format(joinsc))

        # The joinsc, postjoincb, and postjoinobb must refer only to the insig + root
        allroots = list(self._insig) + [self._root]
        if not _check_roots(allroots, joinsc):
            raise ValueError(("Join comparator '{}' refers to non '{}' "
                              "paths").format(joinsc,allroots))
        if not _check_roots(allroots, postjoincb):
            raise ValueError(("Post-join clause block '{}' refers to non '{}' "
                              "paths").format(postjoincb,allroots))

        if not _check_roots(allroots, postjoinobb):
            raise ValueError(("Post-join order by block '{}' refers to non '{}' "
                              "paths").format(postjoinobb,allroots))

        self._placeholders = _extract_placeholders(
            [self._postjoincb, self._prejoincl, self._prejoincb])


    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------
    @classmethod
    def from_specification(cls, indexes, input_signature,
                           root, joins=[], clauses=[],
                           orderbys=[]):
        def _paths(inputs):
            return [ path(p) for p in inputs]

        input_signature = _paths(input_signature)
        root = path(root)

        rootcbs, catchall = partition_clauses(clauses)
        if not rootcbs:
            (prejoincl,prejoincb) = (None,None)
        elif len(rootcbs) == 1:
            (prejoincl,prejoincb) = make_prejoin_pair(indexes, rootcbs[0])
            prejoincl = prejoincl.dealias() if prejoincl else None
            prejoincb = prejoincb.dealias() if prejoincb else None

        else:
            raise ValueError(("Internal bug: unexpected multiple single root "
                              "clauses '{}' when we expected only "
                              "clauses for root {}").format(rootcbs,root))

        (joinsc,postjoincb) = make_join_pair(joins, catchall)

        prejoinobb = None
        postjoinobb = None
        if orderbys:
            orderbys = OrderByBlock(orderbys)
            hroots = [ hashable_path(r) for r in orderbys.roots ]
            postjoinobb = OrderByBlock(orderbys)

# BUG: NEED TO RETHINK BELOW - THE FOLLOWING ONLY WORKS IN SPECIAL CASES

#       if len(hroots) > 1 or hroots[0] !=
#            hashable_path(root): postjoinobb = OrderByBlock(orderbys) else:
#            prejoinobb = orderbys.dealias()

        return cls(input_signature,root, indexes,
                   prejoincl,prejoincb,prejoinobb,
                   joinsc,postjoincb,postjoinobb)


    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------
    @property
    def input_signature(self): return self._insig

    @property
    def root(self): return self._root

    @property
    def indexes(self): return self._indexes
 
    @property
    def prejoin_key_clause(self): return self._prejoincl

    @property
    def join_key(self): return self._joinsc

    @property
    def prejoin_clauses(self): return self._prejoincb

    @property
    def prejoin_orderbys(self): return self._prejoinobb

    @property
    def postjoin_clauses(self): return self._postjoincb

    @property
    def postjoin_orderbys(self): return self._postjoinobb

    @property
    def placeholders(self):
        return self._placeholders

    @property
    def executable(self):
        if self._prejoincl and not self._prejoincl.executable: return False
        if self._prejoincb and not self._prejoincb.executable: return False
        if self._postjoincb and not self._postjoincb.executable: return False
        return True

    def ground(self,*args,**kwargs):
        gprejoincl  = self._prejoincl.ground(*args,**kwargs)  if self._prejoincl else None
        gprejoincb  = self._prejoincb.ground(*args,**kwargs)  if self._prejoincb else None
        gpostjoincb = self._postjoincb.ground(*args,**kwargs) if self._postjoincb else None

        if gprejoincl == self._prejoincl and gprejoincb == self._prejoincb and \
           gpostjoincb == self._postjoincb: return self
        return JoinQueryPlan(self._insig,self._root, self._indexes,
                             gprejoincl,gprejoincb,self._prejoinobb,
                             self._joinsc,gpostjoincb,self._postjoinobb)

    def print(self,file=sys.stdout,pre=""):
        print("{}QuerySubPlan:".format(pre), file=file)
        print("{}\tInput Signature: {}".format(pre,self._insig), file=file)
        print("{}\tRoot path: {}".format(pre,self._root), file=file)
        print("{}\tIndexes: {}".format(pre,self._indexes), file=file)
        print("{}\tPrejoin keyed search: {}".format(pre,self._prejoincl), file=file)
        print("{}\tPrejoin filter clauses: {}".format(pre,self._prejoincb), file=file)
        print("{}\tPrejoin order_by: {}".format(pre,self._prejoinobb), file=file)
        print("{}\tJoin key: {}".format(pre,self._joinsc), file=file)
        print("{}\tPost join clauses: {}".format(pre,self._postjoincb), file=file)
        print("{}\tPost join order_by: {}".format(pre,self._postjoinobb), file=file)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        if self._insig != other._insig: return False
        if self._root.meta.hashable != other._root.meta.hashable: return False
        if self._prejoincl != other._prejoincl: return False
        if self._prejoincb != other._prejoincb: return False
        if self._prejoinobb != other._prejoinobb: return False
        if self._joinsc != other._joinsc: return False
        if self._postjoincb != other._postjoincb: return False
        return True

    def __str__(self):
        out = io.StringIO()
        self.print(out)
        result=out.getvalue()
        out.close()
        return result

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------
# QueryPlan is a complete plan for a query. It consists of a sequence of
# JoinQueryPlan objects that represent increasing joins in the query.
# ------------------------------------------------------------------------------

class QueryPlan(object):
    def __init__(self, subplans):
        if not subplans:
            raise ValueError("An empty QueryPlan is not valid")
        sig = []
        for jqp in subplans:
            insig = [hashable_path(rp) for rp in jqp.input_signature]
            if sig != insig:
                raise ValueError(("Invalid 'input_signature' for JoinQueryPlan. "
                                  "Got '{}' but expecting '{}'").format(insig, sig))
            sig.append(hashable_path(jqp.root))
        self._jqps = tuple(subplans)

    @property
    def placeholders(self):
        return set(itertools.chain.from_iterable(
            [jqp.placeholders for jqp in self._jqps]))

    @property
    def output_signature(self):
        jqp = self._jqps[-1]
        return tuple(jqp.input_signature + (jqp.root,))

    @property
    def executable(self):
        for jqp in self._jqps:
            if not jqp.executable: return False
        return True

    def ground(self,*args,**kwargs):
        newqpjs = [qpj.ground(*args,**kwargs) for qpj in self._jqps]
        if tuple(newqpjs) == self._jqps: return self
        return QueryPlan(newqpjs)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._jqps == other._jqps

    def __len__(self):
        return len(self._jqps)

    def __getitem__(self, idx):
        return self._jqps[idx]

    def __iter__(self):
        return iter(self._jqps)

    def print(self,file=sys.stdout,pre=""):
        print("------------------------------------------------------",file=file)
        for qpj in self._jqps: qpj.print(file,pre)
        print("------------------------------------------------------",file=file)

    def __str__(self):
        out = io.StringIO()
        self.print(out)
        result=out.getvalue()
        out.close()
        return result
        return self.to_str()

    def __repr__(self):
        return self.__str__()


# ------------------------------------------------------------------------------
# Sort the orderby statements into partitions based on the root_join_order,
# where an orderby statement cannot appear at an index before its root
# node. Note: there will be exactly the same number of partitions as the number
# of roots.
# ------------------------------------------------------------------------------
def make_orderby_partitions(root_join_order,orderbys=[]):
    if not orderbys: return [OrderByBlock([]) for r in root_join_order]

    visited=set({})
    orderbys=list(orderbys)

    # For a list of orderby statements return the largest pure subsequence that
    # only refers to the visited root nodes
    def visitedorderbys(visited, obs):
        out = []
        count = 0
        for ob in obs:
            if hashable_path(ob.path.meta.root) in visited:
                count += 1
                out.append(ob)
            else: break
        while count > 0:
            obs.pop(0)
            count -= 1
        return out

    partitions = []
    for idx,root in enumerate(root_join_order):
        visited.add(hashable_path(root))
        part = visitedorderbys(visited, orderbys)
        partitions.append(OrderByBlock(part))

    return partitions


# ------------------------------------------------------------------------------
# Remove the gaps between partitions by moving partitions down
# ------------------------------------------------------------------------------
def remove_orderby_gaps(partitions):
    def gap(partitions):
        startgap = -1
        for idx,obs in enumerate(partitions):
            if obs and startgap == -1: startgap = idx
            elif obs and startgap != -1 and startgap == idx-1: startgap = idx
            elif obs and startgap != -1: return (startgap,idx)
        return (-1,-1)

    # Remove any gaps by merging
    while True:
        startgap,endgap = gap(partitions)
        if startgap == -1: break
        partitions[endgap-1] = partitions[startgap]
        partitions[startgap] = OrderByBlock([])
    return partitions


# ------------------------------------------------------------------------------
# After the first orderby partition all subsequent partitions can only refer to their
# own root. So start from the back of the list and move up till we find a
# non-root partition then pull everything else down into this partition.
# ------------------------------------------------------------------------------

def merge_orderby_partitions(root_join_order, partitions):
    partitions = list(partitions)
    root_join_order = [ hashable_path(r) for r in root_join_order ]

    # Find the last (from the end) non-root partition
    for nridx,part in reversed(list(enumerate(partitions))):
        if part:
            hroots = [ hashable_path(r) for r in part.roots ]
            if len(hroots) > 1 or hroots[0] != root_join_order[nridx]:
                break
    if nridx == 0: return partitions

    # Now merge all other partitions from 0 to nridx-1 into nridx
    bigone = []
    tozero=[]
    for idx,part in (enumerate(partitions)):
        if idx > nridx: break
        if part:
            bigone = list(bigone) + list(part)
            tozero.append(idx)
            break
    if not bigone: return partitions
    for idx in tozero: partitions[idx] = OrderByBlock([])
    partitions[nridx] = OrderByBlock(bigone + list(partitions[nridx]))
    return partitions

# ------------------------------------------------------------------------------
# guaranteed to return a list the same size as the root_join_order.  The ideal
# case is that the orderbys are in the same order as the root_join_order.  BUG
# NOTE: This partitioning scheme is flawed. It only works in a special case
# (when the join clause matches the ordering statement). See below for temporary
# fix.
# ------------------------------------------------------------------------------

def partition_orderbys(root_join_order, orderbys=[]):
    partitions = make_orderby_partitions(root_join_order,orderbys)
    partitions = remove_orderby_gaps(partitions)
    partitions = merge_orderby_partitions(root_join_order,partitions)
    return partitions


# ------------------------------------------------------------------------------
# Because of the logical bug generating valid sorts (what I was doing previously
# only works for a special case), a temporary solution is to merge all
# partitions into the lowest root with an orderby statement.
# ------------------------------------------------------------------------------

def partition_orderbys_simple(root_join_order, orderbys=[]):
    partitions = [OrderByBlock([])]*len(root_join_order)

    if not orderbys: return partitions
    visited = set([hashable_path(ob.path.meta.root) for ob in orderbys])

    # Loop through the root_join_order until all orderby statements have been
    # visited.
    for i,root in enumerate(root_join_order):
        rp = hashable_path(root)
        visited.discard(rp)
        if not visited:
            partitions[i] = OrderByBlock(orderbys)
            return partitions
    raise RuntimeError("Shouldn't reach here")


#------------------------------------------------------------------------------
# QuerySpec stores all the parameters needed to generate a query plan in one
# data-structure
# ------------------------------------------------------------------------------

class QuerySpec(object):
    allowed = [ "roots", "join", "where", "order_by", "ordered",
                "group_by", "tuple", "distinct", "bind", "select",
                "heuristic", "joh" ]

    def __init__(self,**kwargs):
        for k,v in kwargs.items():
            if k not in QuerySpec.allowed:
                raise ValueError("Trying to set unknown parameter '{}'".format(k))
            if v is None:
                raise ValueError(("Error for QuerySpec parameter '{}': 'None' "
                                  "values are not allowed").format(k))
        self._params = dict(kwargs)

    # Return a new QuerySpec with added parameters
    def newp(self, **kwargs):
        if not kwargs: return self
        nparams = dict(self._params)
        for k,v in kwargs.items():
            if v is None:
                raise ValueError("Cannot specify empty '{}'".format(v))
            if k in self._params:
                raise ValueError("Cannot specify '{}' multiple times".format(k))
            nparams[k] = v
        return QuerySpec(**nparams)

    # Return a new QuerySpec with modified parameters
    def modp(self, **kwargs):
        if not kwargs: return self
        nparams = dict(self._params)
        for k,v in kwargs.items():
            if v is None:
                raise ValueError("Cannot specify empty '{}'".format(v))
            nparams[k] = v
        return QuerySpec(**nparams)

    # Return a new QuerySpec with specified parameters deleted
    def delp(self, keys=[]):
        if not keys: return self
        nparams = dict(self._params)
        for k in keys: nparams.pop(k,None)
        return QuerySpec(**nparams)

    # Return the value of a parameter - behaves slightly differently to simply
    # specify the parameter as an attribute because you can return a default
    # value if the parameter is not set.
    def getp(self,name,default=None):
        return self._params.get(name,default)


    def bindp(self, *args, **kwargs):
        where = self.where
        if where is None:
            raise ValueError("'where' must be specified before binding placeholders")
        np = {}
        pp = {}
        for p in where.placeholders:
            if isinstance(p, NamedPlaceholder): np[p.name] = p
            elif isinstance(p, PositionalPlaceholder): pp[p.posn] = p
        for idx, v in enumerate(args):
            if idx not in pp:
                raise ValueError(("Trying to bind value '{}' to positional "
                                  "argument '{}'  but there is no corresponding "
                                  "positional placeholder in where clause "
                                  "'{}'").format(v,idx,where))
        for k,v in kwargs.items():
            if k not in np:
                raise ValueError(("Trying to bind value '{}' to named "
                                  "argument '{}' but there is no corresponding "
                                  "named placeholder in where clause "
                                  "'{}'").format(v,k,where))
        nwhere = where.ground(*args, **kwargs)
        return self.modp(where=nwhere,bind=True)

    def fill_defaults(self):
        toadd = dict(self._params)
        for n in [ "roots","join","where","order_by" ]:
            v = self._params.get(n,None)
            if v is None: toadd[n]=[]
        toadd["group_by"] = self._params.get("group_by",[])
        toadd["bind"] = self._params.get("bind",{})
        toadd["tuple"] = self._params.get("tuple",False)
        toadd["distinct"] = self._params.get("distinct",False)
        toadd["heuristic"] = self._params.get("heuristic",False)
        toadd["joh"] = self._params.get("joh",oppref_join_order)

        # Note: No default values for "select" so calling its attribute will
        # return None


        if toadd: return QuerySpec(**toadd)
        else: return self

    def __getattr__(self, item):
        if item not in QuerySpec.allowed:
            raise ValueError(("Trying to get the value of unknown parameter "
                              "'{}'").format(item))
        return self._params.get(item,None)

    def __str__(self):
        return str(self._params)

    def __repr__(self):
        return repr(self._params)


# Replace any None with a []
def fix_query_spec(inspec):
    join = inspec.join if inspec.join else []
    where = inspec.where if inspec.where else []
    order_by = inspec.order_by if inspec.order_by else []
    return QuerySpec(roots=inspec.roots, join=join,
                     where=where, order_by=order_by)

# ------------------------------------------------------------------------------
# Takes a list of paths that have an index, then based on a
# list of root paths and a query specification, builds the queryplan.
# ------------------------------------------------------------------------------

def make_query_plan_preordered_roots(indexed_paths, root_join_order,
                                     qspec):

    qspec = fix_query_spec(qspec)
    joins = qspec.join
    whereclauses = qspec.where
    orderbys = qspec.order_by

    joinset=set(joins)
    clauseset=set(whereclauses)
    visited=set({})
    orderbys=list(orderbys)

    if not root_join_order:
        raise ValueError("Cannot make query plan with empty root join order")

#    orderbygroups = partition_orderbys(root_join_order, orderbys)
    orderbygroups = partition_orderbys_simple(root_join_order, orderbys)

    # For a set of visited root paths and a set of comparator
    # statements return the subset of join statements that only reference paths
    # that have been visited.  Removes these joins from the original set.
    def visitedsubset(visited, inset):
        outlist=[]
        for comp in inset:
            if visited.issuperset([hashable_path(r) for r in comp.roots]):
                outlist.append(comp)
        for comp in outlist: inset.remove(comp)
        return outlist


    # Generate a list of JoinQueryPlan consisting of a root path and join
    # comparator and clauses that only reference previous plans in the list.
    output=[]
    for idx,(root,rorderbys) in enumerate(zip(root_join_order,orderbygroups)):
        if rorderbys: rorderbys = OrderByBlock(rorderbys)
        visited.add(hashable_path(root))
        rpjoins = visitedsubset(visited, joinset)
        rpclauses = visitedsubset(visited, clauseset)
        if rpclauses: rpclauses = ClauseBlock(rpclauses)
        joinsc, rpclauses = make_join_pair(rpjoins, rpclauses,rorderbys)
        if not rpclauses: rpclauses = []
        rpjoins = [joinsc] if joinsc else []

        output.append(JoinQueryPlan.from_specification(indexed_paths,
                                                       root_join_order[:idx],
                                                       root,rpjoins,rpclauses,
                                                       rorderbys))
    return QueryPlan(output)

# ------------------------------------------------------------------------------
# Join-order heuristics. The heuristic is a function that takes a set of
# indexes, and a query specification with a set of roots and join/where/order_by
# expressions. It then returns an ordering over the roots that are used to
# determine how the joins are built. To interpret the returned list of root
# paths: the first element will be the outer loop query and the last will be the
# inner loop query.
#
# Providing two fixed heuristics: 1) fixed_join_order is a heuristic generator
# and the user specifies the exact ordering, 2) basic_join_order simply retains
# the ordering given as part of the query specification.
#
# The default heuristic, oppref_join_order, is a operator preference heuristic.
# The idea is to assign a preference value to each join expression based on the
# number of join expressions connected with a root path and the operator
# preference. The higher the value the further it is to the outer loop. The
# intuition is that the joins reduce the number of tuples, so by assigning the
# joins early you generate the fewest tuples. Note: not sure about my intuitions
# here. Need to look more closely at the mysql discussion on query execution.
# ------------------------------------------------------------------------------

def fixed_join_order(*roots):
    def validate(r):
        r=path(r)
        if not r.meta.is_root:
            raise ValueError(("Bad query roots specification '{}': '{}' is not "
                             "a root path").format(roots, r))
        return r

    if not roots:
        raise ValueError("Missing query roots specification: cannot create "
                         "a fixed join order heuristic from an empty list")
    paths = [validate(r) for r in roots]
    hashables = set([ hashable_path(r) for r in roots ])

    def fixed_join_order_heuristic(indexed_paths, qspec):
        hps = set([hashable_path(r) for r in qspec.roots])
        if hps != set(hashables):
            raise ValueError(("Mis-matched query roots: fixed join order "
                              "heuristic '{}' must contain exactly the "
                              "roots '{}").format(roots, qspec.roots))
        return list(paths)
    return fixed_join_order_heuristic

def basic_join_order(indexed_paths, qspec):
    return [path(r) for r in qspec.roots]


def oppref_join_order(indexed_paths, qspec):
    roots= qspec.roots
    joins= qspec.join

    root2val = { hashable_path(rp) : 0 for rp in roots }
    for join in joins:
        for rp in join.roots:
            hrp = hashable_path(rp)
            v = root2val.setdefault(hrp, 0)
            root2val[hrp] += join.preference
    return [path(hrp) for hrp in \
            sorted(root2val.keys(), key = lambda k : root2val[k], reverse=True)]


# ------------------------------------------------------------------------------
# Take a join order heuristic, a list of joins, and a list of clause blocks and
# and generates a query.
# ------------------------------------------------------------------------------

def make_query_plan(indexed_paths, qspec):
    qspec = qspec.fill_defaults()
    root_order = qspec.joh(indexed_paths, qspec)
    return make_query_plan_preordered_roots(indexed_paths, root_order, qspec)


#------------------------------------------------------------------------------
# Implementing Queries - taking a QuerySpec, QueryPlan, and a FactMap and
# generating an actual query.
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

    pjk = jqp.prejoin_key_clause
    prejcb = jqp.prejoin_clauses
    factindex = None

    # If there is a prejoin key clause then every comparator within it must
    # refer to exactly one index
    if pjk:
        factindex_sc = []

        for sc in pjk:
            keyable = sc.keyable(factindexes)
            if keyable is None:
                raise ValueError(("Internal error: prejoin key clause '{}' "
                                  "is invalid for JoinQueryPlan "
                                  "{}").format(pjk,jqp))
            kpath,op,key = keyable
            factindex_sc.append((factindexes[kpath],op,key))

    def unsorted_query():
        if prejcb: cc = prejcb.make_callable([jqp.root.meta.dealiased])
        else: cc = lambda _ : True

        if pjk:
            for fi,op,key in factindex_sc:
                for f in fi.find(op,key):
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
    pjk  = jqp.prejoin_key_clause
    pjc  = jqp.prejoin_clauses
    pjob = jqp.prejoin_orderbys
    jk   = jqp.join_key
    predicate = jqp.root.meta.predicate
    factset = factsets.get(jqp.root.meta.predicate, FactSet())

    # If there is a prejoin key clause then every comparator within it must
    # refer to exactly one index
    if pjk:
        factindex_sc = []
        for sc in pjk:
            keyable = sc.keyable(factindexes)
            if keyable is None:
                raise ValueError(("Internal error: prejoin key clause '{}' "
                                  "is invalid for JoinQueryPlan "
                                  "{}").format(pjk,jqp))
            kpath,op,key = keyable
            factindex_sc.append((factindexes[kpath],op,key))

    # A prejoin_key_clause query uses the factindex
    def query_pjk():
        for fi,op,key in factindex_sc:
            for f in fi.find(op,key):
                yield (f,)

    # If there is a set of prejoin clauses
    if pjc:
        pjc = pjc.dealias()
        pjc_root = pjc.roots[0]
        if len(pjc.roots) != 1 and pjc_root.meta.predicate != predicate:
            raise ValueError(("Internal error: prejoin clauses '{}' is invalid "
                              "for JoinQueryPlan {}").format(pjc,jqp))
        pjc_check = pjc.make_callable([pjc_root])

    # prejoin_clauses query uses the prejoin_key_clause query or the underlying factset
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

    prej_order = jqp.prejoin_orderbys
    jk   = jqp.join_key
    jc   = jqp.postjoin_clauses
    postj_order  = jqp.postjoin_orderbys
    predicate = jqp.root.meta.predicate

    prej_iqs = None
    if jk and prej_order:
        prej_iqs = InQuerySorter(prej_order)

    # query_source is a function that returns a FactSet, FactIndex, or list
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
            if prej_order: prej_iqs.listsort(result)
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
    if not postj_order: return unsorted_query

    jiqs = InQuerySorter(postj_order,list(jqp.input_signature) + [jqp.root])
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


#------------------------------------------------------------------------------
# Query is a abstract class that provides the interface to the Query API.  The
# implementation QueryImpl is in factbase.py but the interface is declared here
# so that we can deal with subqueries (imbedded within a membership clause (e.g,
# F.anum in fb.query(...)]).
# ------------------------------------------------------------------------------

class Query(abc.ABC):
    """An abstract class that defines the interface to the Clorm Query API v2.

    .. note::

       This new Query API replaces the old Select/Delete mechanism and offers
       many more features than the old API, especially allowing joins similar to
       an SQL join between tables.

       This interface is complete and unlikely to change - however it is being
       left open for the moment in case there is strong user feedback.

    ``Query`` objects cannot be constructed directly.

    Instead a ``Query`` object is returned by the :meth:`FactBase.query`
    function.  Queries can take a number of different forms but contain many of
    the components of a traditional SQL query. A predicate definition (as
    opposed to a predicate instance or fact) can be viewed as an SQL table and
    the parameters of a predicate can be viewed as the fields of the table.

    The simplest query must at least specify the predicate(s) to search
    for. This is specified as parameters to the :meth:`FactBase.query` function.
    Relating this to a traditional SQL query, the ``query`` clause can be viewed
    as an SQL ``FROM`` specification.

    The query is typicaly executed by iterating over the generator returned by
    the :meth:`Query.all` end-point.

    .. code-block:: python

       from clorm import FactBase, Predicate, IntegerField, StringField

       class Option(Predicate):
           oid = IntegerField
           name = StringField
           cost = IntegerField
           cat = StringField

       class Chosen(Predicate):
           oid = IntegerField

       fb=FactBase([Option(1,"Do A",200,"foo"),Option(2,"Do B",300,"bar"),
                    Option(3,"Do C",400,"foo"),Option(4,"Do D",300,"bar"),
                    Option(5,"Do E",200,"foo"),Option(6,"Do F",500,"bar"),
                    Chosen(1),Chosen(3),Chosen(4),Chosen(6)])

       q1 = fb.query(Chosen)     # Select all Chosen instances
       result = set(q1.all())
       assert result == set([Chosen(1),Chosen(3),Chosen(4),Chosen(6)])

    If there are multiple predicates involved in the search then the query must
    also contain a :meth:`Query.join` clause to specify the predicates
    parameters/fields to join.

    .. code-block:: python

       q2 = fb.query(Option,Chosen).join(Option.oid == Chosen.oid)

    .. note::

       As an aside, while a ``query`` clause typically consists of predicates,
       it can also contain predicate *aliases* created through the :func:`alias`
       function. This allows for queries with self joins to be specified.

    When a query contains multiple predicates the result will consist of tuples,
    where each tuple contains the facts matching the signature of predicates in
    the ``query`` clause. Mathematically the tuples are a subset of the
    cross-product over instances of the predicates; where the subset is
    determined by the ``join`` clause.

    .. code-block:: python

       result = set(q2.all())

       assert result == set([(Option(1,"Do A",200,"foo"),Chosen(1)),
                             (Option(3,"Do C",400,"foo"),Chosen(3)),
                             (Option(4,"Do D",300,"bar"),Chosen(4)),
                             (Option(6,"Do F",500,"bar"),Chosen(6))])

    A query can also contain a ``where`` clause as well as an ``order_by``
    clause. When the ``order_by`` clause contains a predicate path then by
    default it is ordered in ascending order. However, this can be changed to
    descending order with the :func:`desc` function modifier.

    .. code-block:: python

       from clorm import desc

       q3 = q2.where(Option.cost > 200).order_by(desc(Option.cost))

       result = list(q3.all())
       assert result == [(Option(6,"Do F",500,"bar"),Chosen(6)),
                         (Option(3,"Do C",400,"foo"),Chosen(3)),
                         (Option(4,"Do D",300,"bar"),Chosen(4))]

    The above code snippet highlights a feature of the query construction
    process. Namely, that these query construction functions can be chained and
    can also be used as the starting point for another query. Each construction
    function returns a modified copy of its parent. So in this example query
    ``q3`` is a modified version of query ``q2``.

    Returning tuples of facts is often not the most convenient output format and
    instead you may only be interested in specific predicates or parameters
    within each fact tuple. For example, in this running example it is
    unnecessary to return the ``Chosen`` facts. To provide the output in a more
    useful format a query can also contain a ``select`` clause that specifies
    the items to return. Essentially, this specifies a _projection_ over the
    elements of the result tuple.

    .. code-block:: python

       q4 = q3.select(Option)

       result = list(q4.all())
       assert result == [Option(6,"Do F",500,"bar"),
                         Option(3,"Do C",400,"foo"),
                         Option(4,"Do D",300,"bar")]

    A second mechanism for accessing the data in a more convenient format is to
    use a ``group_by`` clause. In this example, we may want to aggregate all the
    chosen options, for example to sum the costs, based on their membership of
    the ``"foo"`` and ``"bar"`` categories. The Clorm query API doesn't directly
    support aggregation functions, as you could do in SQL, so some additional
    Python code is required.

    .. code-block:: python

       q5 = q2.group_by(Option.cat).select(Option.cost)

       result = [(cat, sum(list(it))) for cat, it in q5.all()]
       assert result == [("bar",800), ("foo", 600)]

    The above are not the only options for a query. Some other query modifies
    include: :meth:`Query.distinct` to return distinct elements, and
    :meth:`Query.bind` to bind the value of any placeholders in the ``where``
    clause to specific values.

    A query is executed using a number of end-point functions. As already shown
    the main end-point is :meth:`Query.all` to return a generator for iterating
    over the results.

    Alternatively, if there is at least one element then to return the first
    result only (throwing an exception only if there are no elements) use the
    :meth:`Query.first` method.

    Or if there must be exactly one element (and to throw an exception
    otherwise) use :meth:`Query.singleton`.

    To count the elements of the result there is :meth:`Query.count`.

    Finally to delete all matching facts from the underlying FactBase use
    :meth:`Query.delete`.

    """

    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def join(self, *expressions):
        """Specifying how the predicate/tables in the query are to be joined.

        Joins are expressions that connect the predicates/tables of the
        query. They range from a pure SQL-like inner-join through to an
        unrestricted cross-product. The standard form is:

             ``<PredicatePath> <compop> <PredicatePath>``

        with the full cross-product expressed using a function:

             ``cross(<PredicatePath>,<PredicatePath>)``

        Every predicate/table in the query must be reachable to every other
        predicate/table through some form of join. For example, given predicate
        definitions ``F``, ``G``, ``H``, each with a field ``anum``:

              ``query = fb.query(F,G,H).join(F.anum == G.anum,cross(F,H))``

        generates an inner join between ``F`` and ``G``, but a full
        cross-product between ``F`` and ``H``.

        Finally, it is possible to perform self joins using the function
        ``alias`` that generates an alias for the predicate/table. For
        example:

              ``from clorm import alias``

              ``FA=alias(F)``
              ``query = fb.query(F,G,FA).join(F.anum == FA.anum,cross(F,G))``

        generates an inner join between ``F`` and itself, and a full
        cross-product between ``F`` and ``G``.

        Args:
          expressions: one or more join expressions.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def where(self, *expressions):
        """Sets a list of query conditions.

        The where clause consists of a single (or list) of simple/complex
        boolean and comparison expressions. This expression specifies a search
        criteria for matching facts within the corresponding ``FactBase``.

        Boolean expression are built from other boolean expression or a
        comparison expression. Comparison expressions are of the form:

               ``<PredicatePath> <compop>  <value>``

       where ``<compop>`` is a comparison operator such as ``==``, ``!=``, or
       ``<=`` and ``<value>`` is either a Python value or another predicate path
       object refering to a field of the same predicate or a placeholder.

        A placeholder is a special value that allows queries to be
        parameterised. A value can be bound to each placeholder. These
        placeholders are named ``ph1_``, ``ph2_``, ``ph3_``, and ``ph4_`` and
        correspond to the 1st to 4th arguments when the ``bind()`` function is
        called. Placeholders also allow for named arguments using the
        "ph_("<name>") function.

        Args:
          expressions: one or more comparison expressions.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Add an ordered expresison
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def ordered(self, *expressions):
        """Specify the natural/default ordering over results.

        Given a query over predicates 'P1...PN', the 'ordered()' flag provides a
        convenient way of specifying 'order_by(asc(P1),...,asc(PN))'.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def order_by(self, *expressions):
        """Specify an ordering over the results.

        Args:
          field_order: an ordering over fields

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Add a group_by expression
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def group_by(self, *expressions):
        """Specify a grouping over the results.

        The grouping specification is similar to an ordering specification but
        it modifies the behaviour of the query to return a pair of elements,
        where the first element of the pair is the group identifier (based on
        the specification) and the second element is an iterator over the
        matching elements.

        When both a ``group_by`` and ``order_by`` clause is provided the
        ``order_by`` clause is used the sort the elements within each matching
        group.

        Args:
          field_order: an ordering over fields to group by

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Specify a projection over the elements to output or delete
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def select(self,*outsig):
        """Provides a projection over the query result tuples.

        Mathematically the result tuples of a query are the cross-product over
        instances of the predicates. However, returning tuples of facts is often
        not the most convenient output format and instead you may only be
        interested in specific parameters/fields within each tuple of facts. The
        ``select`` clause specifies a _projection_ over each query result tuple.

        Each query result tuple is guaranteed to be distinct, since the query is
        a filtering over the cross-product of the predicate instances. However,
        the specification of a projection can result in information being
        discarded and can therefore cause the projected query results to no
        longer be distinct. To enforce uniqueness the :meth:`Query.distinct`
        flag can be specified. Essentially this is the same as an ``SQL SELECT
        DISTINCT ...`` statement.

        Note: when :meth:`Query.select` is used with the :meth:`Query.delete`
        end-point the `select` signature must specify predicates and not
        parameter/fields within the predicates.

        Finally, instead of a projection specification, a single Python
        `callable` object can be specified with input parameters matching the
        query signature. This callable object will then be called on each query
        tuple and the results will make up the modified query result. This
        provides the greatest flexibility in controlling the output of the
        query.

        Args:
           output_signature: the signature that defines the projection or a
                             callable object.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # The distinct flag
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def distinct(self):
        """Return only distinct elements in the query.

        This flag is only meaningful when combined with a :meth:`Query.select`
        clause that removes distinguishing elements from the tuples.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Ground - bind
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def bind(self,*args,**kwargs):
        """Bind placeholders to specific values.

        If the ``where`` clause has placeholders then these placeholders must be
        bound to actual values before the query can be executed.

        Args:
          *args: positional arguments corresponding to positional placeholders
          **kwargs: named arguments corresponding to named placeholders

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # The tuple flag
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def tuple(self):
        """Force returning a tuple even for singleton elements.

        In the general case the output signature of a query is a tuple;
        consisting either of a tuple of facts or a tuple of parameters/fields if
        a ``select`` projection has been specified.

        However, if the output signature is a singleton tuple then by default
        the API changes its behaviour and removes the tuple, returning only the
        element itself. This typically provides a much more useful and intutive
        interface. For example, if you want to perform a sum aggregation over
        the results of a query, aggregating over the value of a specific
        parameter/field, then specifying just that parameter in the ``select``
        clause allows you to simply pass the query generator to the standard
        Python ``sum()`` function without needing to perform a list
        comprehension to extract the value to be aggregated.

        If there is a case where this default behaviour is not wanted then
        specifying the ``tuple`` flag forces the query to always return a tuple
        of elements even if the output signature is a singleton tuple.

        Returns:
          Returns the modified copy of the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Overide the default heuristic
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def heuristic(self, join_order):
        """Allows the query engine's query plan to be modified.

        This is an advanced option that can be used if the query is not
        performing as expected. For multi-predicate queries the order in which
        the joins are performed can affect performance. By default the Query API
        will try to optimise this join order based on the ``join`` expressions;
        with predicates with more restricted joins being higher up in the join
        order.

        This join order can be controlled explicitly by the ``fixed_join_order``
        heuristic function. Assuming predicate definitions ``F`` and ``G`` the
        query:

            ``from clorm import fixed_join_order``

            ``query=fb.query(F,G).heuristic(fixed_join_order(G,F)).join(...)``

        forces the join order to first be the ``G`` predicate followed by the
        ``F`` predicate.

        Args:
          join_order: the join order heuristic

        Returns:
          Returns the modified copy of the query.
        """
        pass

    #--------------------------------------------------------------------------
    # End points that do something useful
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Select to display all the output of the query
    # --------------------------------------------------------------------------
    @abc.abstractmethod
    def all(self):
        """Returns a generator that iteratively executes the query.

        Note. This call doesn't execute the query itself. The query is executed
        when iterating over the elements from the generator.

        Returns:
          Returns a generator that executes the query.

        """
        pass

    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    @abc.abstractmethod
    def singleton(self):
        """Return the single matching element.

           An exception is thrown if there is not exactly one matching element
           or a ``group_by()`` clause has been specified.

        Returns:
           Returns the single matching element (or throws an exception)

        """
        pass

    #--------------------------------------------------------------------------
    # Return the count of elements - Note: the behaviour of what is counted
    # changes if group_by() has been specified.
    # --------------------------------------------------------------------------
    @abc.abstractmethod
    def count(self):
        """Return the number of matching element.

           Typically the number of elements consist of the number of tuples
           produced by the cross-product of the predicates that match the
           criteria of the ``join()`` and ``where()`` clauses.

           However, if a ``select()`` projection and ``unique()`` flag is
           specified then the ``count()`` will reflect the modified the number
           of unique elements based on the projection of the query.

           Furthermore, if a ``group_by()`` clause is specified then ``count()``
           returns a generator that iterates over pairs where the first element
           of the pair is the group identifier and the second element is the
           number of matching elements within that group.

        Returns:
           Returns the number of matching elements

        """
        pass

    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    @abc.abstractmethod
    def first(self):
        """Return the first matching element.

           An exception is thrown if there are no one matching element or a
           ``group_by()`` clause has been specified.

        Returns:
           Returns the first matching element (or throws an exception)

        """
        pass

    #--------------------------------------------------------------------------
    # Delete a selection of fact
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def delete(self):
        """Delete matching facts from the ``FactBase()``.

        In the simple case of a query with no joins then ``delete()`` simply
        deletes the matching facts. If there is a join then the matches consist
        of tuples of facts. In this case ``delete()`` will remove all facts from
        the tuple. This behaviour can be modified by using a ``select()``
        projection clause that selects only specific predicates. Note: when
        combined with ``select()`` the output signature must specify predicates
        and not parameter/fields within predicates.

           An exception is thrown if a ``group_by()`` clause has been specified.

        Returns:
           Returns the number of facts deleted.

        """
        pass

    #--------------------------------------------------------------------------
    # For the user to see what the query plan looks like
    #--------------------------------------------------------------------------
    @abc.abstractmethod
    def query_plan(self,*args,**kwargs):
        """Return a query plan object outlining the query execution.

        A query plan outlines the query will be executed; the order of table
        joins, the searches based on indexing, and how the sorting is
        performed. This is useful for debugging if the query is not behaving as
        expected.

        Currently, there is no fixed specification for the query plan
        object. All the user can do is display it for reading and debugging
        purposes.

        Returns:
           Returns a query plan object that can be stringified.

        """
        pass

    #--------------------------------------------------------------------------
    # Internal API property
    #--------------------------------------------------------------------------
    @property
    def qspec(self): pass


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
        where = self._qspec.where
        if where and not where.executable:
            placeholders = where.placeholders
            phstr=",".join("'{}'".format(ph) for ph in placeholders)
            raise ValueError(("Placeholders {} must be bound to values before "
                              "executing the query").format(phstr))
        qspec = self._qspec

        # FIXUP: This is hacky - if there is a group_by clause replace the
        # order_by list with the group_by list and later when sorting the for
        # each group the order_by list will be used.

        if where:
            qspec = qspec.modp(where=where.fixed())

        if qspec.group_by:
            qspec = qspec.modp(order_by=self._qspec.group_by)
            qspec = qspec.delp(["group_by"])
        elif qspec.ordered:
            qspec = qspec.modp(order_by=process_ordered(qspec.roots))

        (factsets,factindexes) = \
            QueryExecutor.get_factmap_data(self._factmaps, qspec)
        qplan = make_query_plan(factindexes.keys(), qspec)
#        qplan = qplan.ground()
        query = make_query(qplan,factsets,factindexes)
        return (qplan,query)


    # --------------------------------------------------------------------------
    # Internal function generator for returning all results
    # --------------------------------------------------------------------------
    def _all(self):
        cache = set()
        for input in self._query():
            output = self._outputter(input)
            if self._unwrap: output = output[0]
            if self._distinct:
                if output not in cache:
                    cache.add(output)
                    yield output
            else:
                yield output

    # --------------------------------------------------------------------------
    # Internal function generator for returning all grouped results
    # --------------------------------------------------------------------------
    def _group_by_all(self):
        iqs=None
        def groupiter(group):
            cache = set()
            if iqs: group=iqs.sorted(group)
            for input in group:
                output = self._outputter(input)
                if self._unwrap: output = output[0]
                if self._distinct:
                    if output not in cache:
                        cache.add(output)
                        yield output
                else:
                    yield output

        qspec = self._qspec
        if qspec.ordered:
            qspec = qspec.modp(order_by=process_ordered(qspec.roots))

        if qspec.order_by:
            iqs=InQuerySorter(OrderByBlock(qspec.order_by),
                              self._qplan.output_signature)
        unwrapkey = len(qspec.group_by) == 1 and not qspec.tuple

        group_by_keyfunc = make_input_alignment_functor(
            self._qplan.output_signature, qspec.group_by.paths)
        for k,g in itertools.groupby(self._query(), group_by_keyfunc):
            if unwrapkey: yield k[0], groupiter(g)
            else: yield k, groupiter(g)


    #--------------------------------------------------------------------------
    # Function to return a generator of the query output
    # --------------------------------------------------------------------------

    def all(self) -> Generator[Any, None, None]:
        if self._qspec.distinct and not self._qspec.select:
            raise ValueError("'distinct' flag requires a 'select' projection")

        (self._qplan,self._query) = self._make_plan_and_query()

        outsig = self._qspec.select
        if outsig is None or not outsig: outsig = self._qspec.roots

        self._outputter = make_outputter(self._qplan.output_signature, outsig)
        self._unwrap = not self._qspec.tuple and len(outsig) == 1
        self._distinct = self._qspec.distinct

        if len(self._qspec.group_by) > 0: return self._group_by_all()
        else: return self._all()

    # --------------------------------------------------------------------------
    # Delete a selection of facts. Maintains a set for each predicate type
    # and adds the selected fact to that set. The delete the facts in each set.
    # --------------------------------------------------------------------------

    def delete(self):
        if self._qspec.group_by:
            raise ValueError("'group_by' is incompatible with 'delete'")
        if self._qspec.distinct:
            raise ValueError("'distinct' is incompatible with 'delete'")
        if self._qspec.tuple:
            raise ValueError("'tuple' is incompatible with 'delete'")

        (self._qplan,self._query) = self._make_plan_and_query()

        selection = self._qspec.select
        roots = [hashable_path(p) for p in self._qspec.roots]
        if selection:
            subroots = set([hashable_path(p) for p in selection])
        else:
            subroots = set(roots)

        if not subroots.issubset(set(roots)):
            raise ValueError(("For a 'delete' query the selected items '{}' "
                              "must be a subset of the query roots "
                              "'{}'").format(selection, roots))

        # Special case for deleting all facts of a predicate
        if (len(roots) == 1 and len(subroots) == 1 and
            not self._qspec.where and not self._qspec.join):
            fm = self._factmaps[path(roots[0]).meta.predicate]
            count = len(fm)
            fm.clear()
            return count

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
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
