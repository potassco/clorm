# -----------------------------------------------------------------------------
# Clorm ORM FactBase query implementation. It provides the rich query API.
# ------------------------------------------------------------------------------

import io
import operator
import collections
import bisect
import abc
import functools
import inspect
import enum

from ..util.tools import all_equal
from .core import *
from .core import get_field_definition, QCondition, PredicatePath, \
    kwargs_check_keys, trueall

__all__ = [
    'Placeholder',
    'Select',
    'Delete',
    'desc',
    'asc',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'func_',
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

    @abc.abstractmethod
    def __eq__(self, other): pass

    @abc.abstractmethod
    def __ne__(self, other): pass

    @abc.abstractmethod
    def __hash__(self): pass


class NamedPlaceholder(Placeholder):
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
        if not isinstance(other, NamedPlaceholder): return NotImplemented
        if self.name != other.name: return False
        if self._default != other._default: return False
        return True
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result
    def __hash__(self):
        return hash(self._name)

class PositionalPlaceholder(Placeholder):
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
        if not isinstance(other, PositionalPlaceholder): return NotImplemented
        return self._posn == other._posn
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result
    def __hash__(self):
        return hash(self._posn)

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
        return NamedPlaceholder(**nkargs)

    # Its a positional placeholder
    if default[0]:
        raise TypeError("Positional placeholders don't support default values")
    idx -= 1
    if idx < 0:
        raise ValueError("Index {} is not a positional argument".format(idx+1))
    return PositionalPlaceholder(idx)

#------------------------------------------------------------------------------
# Some pre-defined positional placeholders
#------------------------------------------------------------------------------

ph1_ = PositionalPlaceholder(0)
ph2_ = PositionalPlaceholder(1)
ph3_ = PositionalPlaceholder(2)
ph4_ = PositionalPlaceholder(3)


# ------------------------------------------------------------------------------
# User callable function to build a functor wrapper object as part of a
# specifying a where clause.
# ------------------------------------------------------------------------------

def func_(paths, func):
    '''Wrap a boolean functor with predicate paths for use as a query condition'''
    def get_paths():
        try:
            return [path(paths)]
        except TypeError:
            return [ path(p) for p in paths]

    return FunctorComparisonCondition(func, get_paths())

# ------------------------------------------------------------------------------
# QConditions are generated by the 
# Query conditions (whether QCondition objects or functors or
# FunctorComparisonCondition wrapper objects) are treated as immutable. So when
# manipulating such objects the following functions make modified copies of the
# objects rather than modifying the objects themselves. So if a function doesn't
# need to modify an object at all it simply returns the object itself.
# ------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Functions to check, simplify, resolve placeholders, and execute queries
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# QCondition is used to support three different types of operators. A
# boolean condition (e.g., and,or,not), a comparison condition (e.g., equality,
# lessthan), and a join condition (eg., 
# ------------------------------------------------------------------------------

g_bool_operators = {
    operator.and_ : True, operator.or_ : True, operator.not_ : True }

def is_boolean_condition(cond):
    if isinstance(cond, FunctorComparisonCondition): return False
    elif not isinstance(cond, QCondition): return False
    v = g_bool_operators.get(cond.operator,False)
    return v


CompOpSpec = collections.namedtuple('CompOpSpec','negate')

g_compop_operators = {
    operator.eq : CompOpSpec(negate=operator.ne),
    operator.ne : CompOpSpec(negate=operator.eq),
    operator.lt : CompOpSpec(negate=operator.ge),
    operator.le : CompOpSpec(negate=operator.gt),
    operator.gt : CompOpSpec(negate=operator.le),
    operator.ge : CompOpSpec(negate=operator.lt) }


def is_comparison_condition(cond):
    if isinstance(cond, FunctorComparisonCondition): return True
    elif not isinstance(cond, QCondition): return False
    spec = g_compop_operators.get(cond.operator,None)
    if not spec: return False
    jspec = g_join_operators.get(cond.operator,None)
    if not jspec: return True
    p0 = path(cond.args[0],exception=False)
    if not p0: return True
    p1 = path(cond.args[1],exception=False)
    if not p1: return True
    return p0.meta.root == p1.meta.root


class JoinPref(enum.IntEnum):
    LOW= 0
    MEDIUM= 1
    HIGH=2

JoinOpSpec = collections.namedtuple('JoinOpSpec','porder swapop')

g_join_operators = {
    operator.eq : JoinOpSpec(porder=JoinPref.HIGH, swapop=operator.eq),
    operator.ne : JoinOpSpec(porder=JoinPref.LOW, swapop=operator.ne),
    operator.lt : JoinOpSpec(porder=JoinPref.MEDIUM, swapop=operator.ge),
    operator.le : JoinOpSpec(porder=JoinPref.MEDIUM, swapop=operator.gt),
    operator.gt : JoinOpSpec(porder=JoinPref.MEDIUM, swapop=operator.le),
    operator.ge : JoinOpSpec(porder=JoinPref.MEDIUM, swapop=operator.lt),
    trueall     : JoinOpSpec(porder=JoinPref.LOW, swapop=trueall) }


def is_join_condition(cond):
    if not isinstance(cond, QCondition): return False
    jspec = g_join_operators.get(cond.operator,None)
    if not jspec: return False
    cspec = g_compop_operators.get(cond.operator,None)
    if not cspec: return False
    p0 = path(cond.args[0],exception=False)
    if not p0: return True
    p1 = path(cond.args[1],exception=False)
    if not p1: return True
    return p0.meta.root == p1.meta.root




# ------------------------------------------------------------------------------
# To support database-like inner joins.  Join conditions are a subset of the
# comparison conditions which must have exactly two arguments that are both
# predicate field paths.
#
# Different types of joins have different properties.
# ------------------------------------------------------------------------------

# Each join operator has a preference ordering


# ------------------------------------------------------------------------------
# Every comparison condition (including a FunctorComparisonCondition) has an
# operator function and input of some form; eg "F.anum == 3" has operator.eq_
# and input (F.anum,3) where F.anum is a path and will be replaced by some fact
# sub-field value.
#
# Only the other hand a query needs to test a fact (or a tuple of facts) against
# this operator. If a search is on a single predicate type then input will be a
# singleton tuple; if there is a join in the query there will be multiple
# elements to the tuple. However, the order of facts will be determined by the
# query optimiser as it may be more efficient to join X with Y rather than Y
# with X. So we need a way to remap a search input fact-tuple into the expected
# form for each query condition component. This function returns a function that
# takes a tuple of facts as given by the input signature and returns a tuple of
# values as given by the output signature.
# ------------------------------------------------------------------------------
def make_query_alignment_functor(input_predicate_signature, output_signature):

    # Input signature are paths that must correspond to predicate types
    def validate_input_signature():
        if not input_predicate_signature:
            raise TypeError("Empty input predicate path signature")
        inputs=[]
        try:
            for p in input_predicate_signature:
                pp = path(p)
                if not pp.meta.is_root:
                    raise ValueError("path '{}' is not a predicate root".format(pp))
                inputs.append(pp)
        except Exception as e:
            raise TypeError(("Invalid input predicate path signature {}: "
                              "{}").format(input_predicate_signature,e)) from None
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

    # build list of lambdas one for each output item to return appropriate values
    pp2idx = { hashable_path(pp) : idx for idx,pp in enumerate(insig) }
    getters = []
    for out in outsig:
        if isinstance(out,PredicatePath):
            idx = pp2idx.get(hashable_path(out.meta.root),None)
            if idx is None:
                raise TypeError(("Invalid signature match between {} and {}: "
                                 "missing input predicate path for "
                                 "{}").format(input_predicate_signature,
                                              output_signature,out))
            getters.append(lambda facts, p=out, idx=idx: p(facts[idx]))
        else:
            getters.append(lambda facts : out)

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
    return func


# ------------------------------------------------------------------------------
# ComparisonCallable is a functional object that wraps a comparison operator and
# ensures the comparison operator gets the correct input. The input to a
# ComparisonCallable is a tulple of facts (the form of which is determined by a
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
# FunctorComparisonCondition is a wrapper around query boolean
# functions/callables that are not QCondition objects. The constructor takes
# a reference to the function and a path signature.
# ------------------------------------------------------------------------------

class FunctorComparisonCondition(object):
    def __init__(self,func,path_signature,negative=False,assignment=None):
        self._func = func
        self._funcsig = collections.OrderedDict()
        self._pathsig = tuple([ hashable_path(p) for p in path_signature])
        self._negative = negative
        self._assignment = None if assignment is None else dict(assignment)

        # The function signature must be compatible with the path signature
        funcsig = inspect.signature(func)
        if len(funcsig.parameters) < len(self._pathsig):
            raise TypeError(("More paths specified in the path signature '{}' "
                             "than there are in the function "
                             "signature '{}'").format(self._pathsig, funcsig))

        # Track the parameters that are not part of the path signature but are
        # part of the function signature. This determines if the
        # FunctorComparisonCondition is "ground".
        for i,(k,v) in enumerate(funcsig.parameters.items()):
            if i >= len(self._pathsig): self._funcsig[k]=v

        # Check the path signature
        if not self._pathsig:
            raise TypeError("Invalid empty path signature")

        for pp in self._pathsig:
            if not isinstance(pp,PredicatePath.Hashable):
                raise TypeError(("The boolean functor call signature must "
                                  "consist of predicate paths"))

        # if there is an assigned ordereddict then check the keys
        if self._assignment is not None:
            self._check_assignment()

    def _check_assignment(self):
        assignmentkeys=set(list(self._assignment.keys()))
        funcsigkeys=set(list(self._funcsig.keys()))
        tmp = assignmentkeys-funcsigkeys
        if tmp:
            raise TypeError(("FunctorComparisonCondition is being given "
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
            raise ValueError(("Even after the named placeholders have been "
                              "assigned there are missing functor parameters "
                              "for '{}'").format(tmp))

    @property
    def path_signature(self):
        return self._pathsig

    @property
    def predicates(self):
        return set([p.path.meta.predicate for p in self._pathsig])

    @property
    def is_ground(self):
        '''Is ground if all the non-path function parameters are assigned or have a
           default value
        '''
        return self._assignment is not None

    def negate(self):
        neg = not self._negative
        return FunctorComparisonCondition(self._func,self._pathsig,neg,
                                          assignment=self._assignment)

    def ground(self, assignment={}):
        if self._assignment is not None:
            raise RuntimeError(("Internal bug: cannot ground "
                                "FunctorComparisonCondition multiple times"))
        return FunctorComparisonCondition(self._func,self._pathsig,
                                          self._negative,assignment)

    def make_callable(self, predicate_signature):
        if not self.is_ground:
            raise RuntimeError(("Internal bug: make_callable called on a "
                                "ungrounded object: {}").format(self))

        # from the function signature generate and the assignment
        # generate the fixed values for the non-path items
        funcsigparam = [ self._assignment[k] for k,_ in self._funcsig.items() ]
        outputsig = tuple(list(self._pathsig) + funcsigparam)
        alignfunc = make_query_alignment_functor(predicate_signature,
                                                 outputsig)
        op = self._func if not self._negative else lambda *args : not self._func(*args)
        return ComparisonCallable(op,alignfunc)

    def __eq__(self, other):
        if not isinstance(other, FunctorComparisonCondition): return NotImplemented
        if self._func != other._func: return False
        if self._pathsig != other._pathsig: return False
        if self._negative != other._negative: return False
        if self._assignment != other._assignment: return False
        return True
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __str__(self):
        assignstr = ": {}".format(self._assignment) if self._assignment else ""
        funcstr = "func_({}{}, {})".format(self._pathsig,assignstr,self._func,)
        if not self._negative: return funcstr
        return "not_({})".format(funcstr)

# ------------------------------------------------------------------------------
# Take a predicate path signature and a ground comparison condition (either an
# appropriate QCondition or a FunctorComparisonCondition) and return a
# ComparisonCallable object that can be used to test whether an input fact tuple
# satisfies the condition.
# ------------------------------------------------------------------------------

def make_comparison_callable(predicate_signature, ccond):
    if isinstance(ccond,FunctorComparisonCondition):
        return ccond.make_callable(predicate_signature)
    if not is_comparison_condition(ccond):
        raise TypeError(("Internal bug: object is not a comparison "
                         "condition: {}").format(ccond))
    if not _is_ground(ccond):
        raise TypeError(("Internal bug: comparison condition is not"
                         "ground: {}").format(ccond))

    # It must be a ground comparison QCondition object
    sig = make_query_alignment_functor(predicate_signature, ccond.args)
    return ComparisonCallable(ccond.operator,sig)

# ------------------------------------------------------------------------------
# Validates and simplifies a query condition with respect to a set of predicate
# types. Returns a simplified version of the query condition where: 1) any
# static conditions (conditions that can be evaluated without a fact) are
# replaced with their a boolean evaluation, 2) boolean functors are wrapped in a
# FunctorComparisonCondition object.
# ------------------------------------------------------------------------------
def validate_query_condition(qcond, ppaths):
    try:
        ppaths = [ hashable_path(pp) for pp in ppaths ]
    except Exception as e:
        raise ValueError(("Invalid predicate paths signature {}: "
                          "{}").format(ppaths,e)) from None
    for pp in ppaths:
        if not pp.path.meta.is_root:
            raise ValueError(("Invalid ppaths element {} does not refer to "
                              "the root of a predicate path ").format(pp))
    ppaths = set(ppaths)

    def getcomparable(arg):
        if isinstance(arg,PredicatePath): return hashable_path(arg)
        return arg

    # Check if a condition is static - based on recursive call
    def is_static_condition(cond):
        if isinstance(cond,QCondition): return False
        if isinstance(cond,FunctorComparisonCondition): return False
        if callable(cond): return False
        return True

    # Check callable - construct a FunctorComparisonCondition if not already one
    def validate_callable(func):
        if len(ppaths) != 1:
            raise ValueError(("Incompatible usage between raw functor {} and "
                              "non-singleton predicates {}").format(func,ppaths))
        return FunctorComparisonCondition(func,ppaths)

    # Check boolean condition - simplifying if it is a static condition
    def validate_bool_condition(bcond):
        if bcond.operator == operator.not_:
            newsubcond = validate_condition(bcond.args[0])
            if is_static_condition(newsubcond): return bcond.operator(newsubcond)
            if newsubcond == bcond.args[0]: return bcond
            return QCondition(bcond.operator,newsubcond)
        if bcond.operator != operator.and_ and bcond.operator != operator.or_:
            raise TypeError(("Internal bug: unknown boolean operator '{}' in query "
                             "condition '{}'").format(bcond.operator, qcond))
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
        if isinstance(ccond,QCondition):
            if all(map(is_static_condition, ccond.args)):
                raise ValueError(("Invalid comparison condition {} in query {}: "
                                  "at least one argument must reference a "
                                  "predicate path").format(ccond,qcond))
            if all_equal(ccond.args): return ccond
            return QCondition(ccond.operator,*ccond.args)

        # must be a FunctorComparisonCondition
        for pp in ccond.path_signature:
            if hashable_path(path(pp).meta.predicate) not in ppaths:
                raise ValueError(("Boolean functor {} references {} which "
                                  "is not connected to {}").format(fcc,pp,ppaths))
        return ccond

    # Validate a condition
    def validate_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid condition '{}' in query '{}': a Placeholder must be "
                              "part of a comparison condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid condition '{}' in query '{}': a PredicatePath must be "
                              "part of a comparison condition").format(cond, qcond))
        if callable(cond): return validate_callable(cond)
        elif is_boolean_condition(cond): return validate_bool_condition(cond)
        elif is_comparison_condition(cond): return validate_comp_condition(cond)
        else: return bool(cond)

    return validate_condition(qcond)

# ------------------------------------------------------------------------------
# negate a query condition and push the negation into the leaf nodes - note:
# input must have already been validated. Because we can negate all comparison
# conditions we therefore end up with no explicitly negated boolean conditions.
# ------------------------------------------------------------------------------
def negate_query_condition(qcond):

    # Note: for not operator negate twice to force negation inward
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

    def negate_comp_condition(ccond):
        spec = g_compop_operators.get(ccond.operator,None)
        if spec is None:
            raise TypeError(("Internal bug: unknown comparison operator '{}' in "
                             "query condition '{}'").format(bcond.operator, qcond))
        return QCondition(spec.negate, *ccond.args)

    # Negate the condition
    def negate_condition(cond):
        if isinstance(cond, FunctorComparisonCondition): return cond.negate()
        if is_boolean_condition(cond):
            return negate_bool_condition(cond)
        else:
            return negate_comp_condition(cond)

    return negate_condition(qcond)

# ------------------------------------------------------------------------------
# Convert the query condition to negation normal form by pushing any negations
# inwards. Because we can negate all comparison conditions we therefore end up
# with no explicit negated boolean conditions. Note: input must have been
# validated
# ------------------------------------------------------------------------------
def normalise_to_nnf_query_condition(qcond):
    return negate_query_condition(negate_query_condition(qcond))

# ------------------------------------------------------------------------------
# Convert the query condition to conjunctive normal form. Because we can negate
# all comparison conditions we therefore end up with no explicit negated boolean
# conditions.  Note: input must have been validated
# ------------------------------------------------------------------------------
def normalise_to_cnf_query_condition(qcond):

    def dist_if_or_over_and(bcond):
        if bcond.operator != operator.or_: return bcond
        if bcond.args[0].operator == operator.and_:
            x = bcond.args[0].args[0]
            y = bcond.args[0].args[1]
            return and_(or_(x,bcond.args[1]),or_(y,bcond.args[1]))
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
        if isinstance(cond, FunctorComparisonCondition): return cond
        if not is_boolean_condition(cond): return cond
        return bool_condition_to_cnf(cond)

    return condition_to_cnf(normalise_to_nnf_query_condition(qcond))


# ------------------------------------------------------------------------------
# Some support functions
# ------------------------------------------------------------------------------

def _hashable_paths(arg):
    if isinstance(arg, FunctorComparisonCondition): return set(arg.path_signature)
    elif isinstance(arg, PredicatePath): return set([hashable_path(arg)])
    if not isinstance(arg,QCondition): return set([])
    tmp=set([])
    for a in arg.args: tmp.update(_hashable_paths(a))
    return tmp

def _is_ground(arg):
    if isinstance(arg, Placeholder): return False
    elif isinstance(arg, FunctorComparisonCondition) and not arg.is_ground: return False
    if not isinstance(arg,QCondition): return True
    for a in arg.args:
        if not _is_ground(a): return False
    return True

# ------------------------------------------------------------------------------
# A Clause is a list of comparison conditions that should be interpreted as a
# disjunction.
# ------------------------------------------------------------------------------

class Clause(object):

    def __init__(self, cconds):
        if not cconds:
            raise ValueError("Empty list of comparison conditions")
        for ccond in cconds:
            if not isinstance(ccond,FunctorComparisonCondition) and \
               is_boolean_condition(ccond):
                raise ValueError(("Only comparison conditions allowed: "
                                  "{} ").format(ccond))
        self._cconds = tuple(cconds)

    @property
    def is_ground(self):
        tmp = []
        for ccond in self._cconds:
            if not _is_ground(ccond): return False
        return True

    @property
    def hashable_paths(self):
        tmp = []
        for ccond in self._cconds:
            tmp.extend(_hashable_paths(ccond))
        return set(tmp)

    @property
    def predicates(self):
        return set([path(hp).meta.predicate for hp in self.hashable_paths])

    def ground(self,args,kwargs):
        if self.is_ground: return self

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._cconds == other._cconds

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __iter__(self):
        return iter(self._cconds)

    def __str__(self):
       return "[ {} ]".format(" | ".join([str(c) for c in self._cconds]))

    def __repr__(self):
       return self.__str__()

# ------------------------------------------------------------------------------
# Normalise takes a formula and turns it into a clausal CNF (a list of lists
# being a conjuctive list of disjunctive elements. Note: input must have been
# validated.
# ------------------------------------------------------------------------------
def normalise_query_condition(qcond):
    NEWCL = "new_clause"
    stack=[NEWCL]

    def is_leaf(arg):
        if isinstance(arg, FunctorComparisonCondition): return True
        return not is_boolean_condition(arg)

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
    stack_add(normalise_to_cnf_query_condition(qcond))
#    print("STACK: {}".format(stack))
    return build_clauses()





def is_join_operator(op):
    return op in g_join_operators


def validate_join_condition(jcond):
    if isinstance(cond, FunctorComparisonCondition): return False
    elif not isinstance(cond, QCondition): return False
    spec = g_join_operators.get(cond.operator,None)
    if not spec: return False
        






# ------------------------------------------------------------------------------
# Our normal form is a clausal CNF - a conjunctive list of disjunctive lists
# ------------------------------------------------------------------------------

class NormalForm(object):
    pass















# ------------------------------------------------------------------------------
# BELOW HERE IS THE OLD QUERY IMPLEMENTATION
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
        if isinstance(cond,QCondition):
            if is_boolean_condition(cond):
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
        if isinstance(cond,QCondition): return True
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
            return QCondition(bcond.operator,newsubcond)
        if bcond.operator != operator.and_ and bcond.operator != operator.or_:
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
            return QCondition(bcond.operator,*newargs)

        if bcond.operator == operator.or_:
            if not isdynamiccond(newargs[0]):
                return True if newargs[0] else newargs[1]
            if not isdynamiccond(newargs[1]):
                return True if newargs[1] else newargs[0]
            if newargs[0] is bcond.args[0] and newargs[1] is bcond.args[1]:
                return bcond
            return QCondition(bcond.operator,*newargs)

    def simplify_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid condition '{}' in query '{}': a Placeholder must be "
                              "part of a comparison condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid condition '{}' in query '{}': a PredicatePath must be "
                              "part of a comparison condition").format(cond, qcond))
        if callable(cond): return cond
        if not isinstance(cond,QCondition): return bool(cond)
        if is_boolean_condition(cond):
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

# NOTE: I possibly only need to use functools.partial here
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
        elif isinstance(cond,PositionalPlaceholder):
            if cond.posn < len(args): return args[cond.posn]
            raise ValueError(("Missing positional placeholder argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(cond,qcond,args,kwargs))
        elif isinstance(cond,NamedPlaceholder):
            v = kwargs.get(cond.name,None)
            if v: return v
            if cond.has_default: return cond.default
            raise ValueError(("Missing named placeholder argument '{}' when instantiating "
                              "'{}' with arguments: {} {}").format(cond,qcond,args,kwargs))
        elif isinstance(cond,QCondition):
            newsubargs = []
            changed=False
            for subarg in cond.args:
                newsubarg = instantiate(subarg)
                if newsubarg is not subarg: changed=True
                newsubargs.append(newsubarg)
            if changed: return QCondition(cond.operator,*newsubargs)
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
        if isinstance(cond,QCondition):
            if is_boolean_condition(cond):
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

class SelectImpl(Select):

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

        if isinstance(cond, QCondition):
            if not is_boolean_condition(cond):
                return validate_indexable(get_indexable(cond))
        indexable = None
        if isinstance(cond, QCondition) and cond.operator == operator.and_:
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
        """Return the number of matching entries."""
        return len(self.get(*args, **kwargs))

#------------------------------------------------------------------------------
# A deletion over a _FactMap
# - a stupid implementation that iterates over all facts and indexes
#------------------------------------------------------------------------------

class DeleteImpl(object):

    def __init__(self, factmap):
        self._factmap = factmap
        self._select = SelectImpl(factmap)

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
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
