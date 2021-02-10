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

from ..util import OrderedSet as FactSet
from ..util.tools import all_equal
from .core import *
from .core import get_field_definition, QCondition, PredicatePath, \
    kwargs_check_keys, trueall, falseall

__all__ = [
    'Placeholder',
    'desc',
    'asc',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'func_',
    'fixed_join_order_heuristic',
    'basic_join_order_heuristic',
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
    def __ne__(self, other): pass

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
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result
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
def func_(paths, func):
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
# A comparator is either a standard comparator (with a known comparison
# operator) or made with an arbitrary function.
# ------------------------------------------------------------------------------


class Comparator(abc.ABC):

    @abc.abstractmethod
    def ground(self,*args,**kwargs): pass

    @abc.abstractmethod
    def negate(self): pass

    @abc.abstractmethod
    def dealias(self): pass

    @abc.abstractmethod
    def make_callable(self, root_signature): pass

    @property
    @abc.abstractmethod
    def form(self): pass

    @property
    @abc.abstractmethod
    def paths(self): pass

    @property
    @abc.abstractmethod
    def placeholders(self): pass

    @property
    @abc.abstractmethod
    def roots(self): pass

    @abc.abstractmethod
    def __eq__(self, other): pass

    @abc.abstractmethod
    def __ne__(self, other): pass

    @abc.abstractmethod
    def __hash__(self): pass


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
# Comparator for the standard operators
# ------------------------------------------------------------------------------

class StandardComparator(Comparator):
    class Preference(enum.IntEnum):
        LOW= 0
        MEDIUM= 1
        HIGH=2

    OpSpec = collections.namedtuple('OpSpec','pref join where negop swapop form')
    operators = {
        operator.eq : OpSpec(pref=Preference.HIGH, join=True, where=True,
                             negop=operator.ne, swapop=operator.eq,
                             form=QCondition.Form.INFIX),
        operator.ne : OpSpec(pref=Preference.LOW, join=True, where=True,
                             negop=operator.eq, swapop=operator.ne,
                             form=QCondition.Form.INFIX),
        operator.lt : OpSpec(pref=Preference.MEDIUM, join=True, where=True,
                             negop=operator.ge, swapop=operator.gt,
                             form=QCondition.Form.INFIX),
        operator.le : OpSpec(pref=Preference.MEDIUM, join=True, where=True,
                             negop=operator.gt, swapop=operator.ge,
                             form=QCondition.Form.INFIX),
        operator.gt : OpSpec(pref=Preference.MEDIUM, join=True, where=True,
                             negop=operator.le, swapop=operator.lt,
                             form=QCondition.Form.INFIX),
        operator.ge : OpSpec(pref=Preference.MEDIUM, join=True, where=True,
                             negop=operator.lt, swapop=operator.le,
                             form=QCondition.Form.INFIX),
        trueall     : OpSpec(pref=Preference.LOW, join=True, where=False,
                             negop=falseall, swapop=trueall,
                             form=QCondition.Form.FUNCTIONAL),
        falseall    : OpSpec(pref=Preference.HIGH, join=True, where=False,
                             negop=trueall, swapop=falseall,
                             form=QCondition.Form.FUNCTIONAL)}


    def __init__(self,operator,args):
        spec = StandardComparator.operators.get(operator,None)
        if spec is None:
            raise TypeError(("Internal bug: cannot create StandardComparator() with "
                             "non-comparison operator '{}' ").format(operator))
        self._operator = operator
        self._args = tuple(args)

        self._hashableargs = tuple([ hashable_path(a) if isinstance(a,PredicatePath) \
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
        def normalise_arg(arg):
            p=path(arg,exception=False)
            if p is None: return arg
            return p

        def is_static_arg(arg):
            return not isinstance(arg,PredicatePath)

        if not isinstance(qcond, QCondition):
            raise TypeError(("Internal bug: trying to make StandardComparator() "
                             "from non QCondition object: {}").format(qcond))
        newargs = [normalise_arg(a) for a in qcond.args]

        if all(map(is_static_arg, newargs)):
            raise ValueError(("Invalid comparison of only static inputs "
                              "(at least one argument must reference a "
                              "a component of a fact): {}").format(qcond))

        if qcond.operator == falseall:
            raise ValueError("Internal bug: cannot use falseall operator in QCondition")

        spec = StandardComparator.operators.get(qcond.operator,None)
        if spec is None:
            raise TypeError(("Internal bug: cannot create StandardComparator() with "
                             "non-comparison operator '{}' ").format(qcond.operator))
        if not spec.where and spec.join:
            raise ValueError(("Invalid 'where' comparison operator '{}' is only "
                              "valid for a join specification").format(qcond.operator))
        return cls(qcond.operator,newargs)

    @classmethod
    def from_join_qcondition(cls,qcond):
        if not isinstance(qcond, QCondition):
            raise TypeError(("Internal bug: trying to make Join() "
                             "from non QCondition object: {}").format(qcond))
        if qcond.operator == falseall:
            raise ValueError("Internal bug: cannot use falseall operator in QCondition")

        paths = list(filter(lambda x: isinstance(x,PredicatePath), qcond.args))
        paths = set(map(lambda x: hashable_path(x), paths))
        roots = set(map(lambda x: hashable_path(path(x).meta.root), paths))
        if len(roots) != 2:
            raise ValueError(("A join specification must have "
                              "exactly two root paths: '{}'").format(qcond))

        if qcond.operator == trueall:
            if paths != roots:
                raise ValueError(("Cross-product expression '{}' must contain only "
                                  "root paths").format(qcond))
        return cls(qcond.operator,qcond.args)

    # -------------------------------------------------------------------------
    # Implement ABC functions
    # -------------------------------------------------------------------------

    def ground(self,*args,**kwargs):
        def get(arg):
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
            else:
                return arg
        newargs = tuple([get(a) for a in self._args])
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

    @property
    def paths(self):
        return self._paths

    @property
    def placeholders(self):
        return set(filter(lambda x : isinstance(x,Placeholder), self._args))

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

    def __ne__(self,other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __hash__(self):
        return hash((self._operator,) + self._hashableargs)

    def __str__(self):
        # For convenience just return a QCondition string
        return str(QCondition(self._operator, *self._args))

    def __repr__(self):
        return self.__str__()

# ------------------------------------------------------------------------------
# Comparator for arbitrary functions. From the API generated with func_()
# The constructor takes a reference to the function and a path signature.
#
# FIXUP NOTE: a limitation of the current implementation of FunctionComparator
# means that ground() has to be called to make the assignment valid. Need to
# look at this.
#
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

    def negate(self):
        neg = not self._negative
        return FunctionComparator(self._func,self._pathsig,neg,
                                          assignment=self._assignment)

    def dealias(self):
        newpathsig = [path(hp).meta.dealiased for hp in self._pathsig]
        if _hashables(newpathsig) == _hashables(self._pathsig): return self
        return FunctionComparator(self._func, newpathsig, self._negative,
                                          assignment=self._assignment)

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
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __hash__(self):
        return hash((self._func,) + self._pathsig + self._assignment_tuple)

    def __str__(self):
        assignstr = ": {}".format(self._assignment) if self._assignment else ""
        funcstr = "func_({}{}, {})".format(self._pathsig,assignstr,self._func,)
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

    def dealias(self):
        newcomps = [ c.dealias() for c in self._comparators]
        if newcomps == self._comparators: return self
        return Clause(newcomps)

    def ground(self,*args, **kwargs):
        newcomps = [ comp.ground(*args,**kwargs) for comp in self._comparators]
        if newcomps == self._comparators: return self
        return Clause(newcomps)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._comparators == other._comparators

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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
    where = validate_where_expression(where_expression,roots)
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

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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
def desc(path):
    return OrderBy(path,asc=False)
def asc(path):
    return OrderBy(path,asc=True)

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

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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
        else: raise TypeError("Invalid 'order_by' expression: {}".format(exp))
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
# make_prejoin_pair(indexed_paths, clauses)
# - indexed_paths - a list of paths for which there is a factindex
# - clauses - a clause block that can only refer to a single root
#
# Tries to extract a clause that references a single path that can be used for
# indexing and returns a pair consisting of the (comparator, remainder) Note: we
# can't deal with disjunctive clauses (future work)
# ------------------------------------------------------------------------------
def make_prejoin_pair(indexed_paths, clauseblock):
    def preference(cl):
        c = min(cl, key=lambda c: c.preference)
        return c.preference

    def is_candidate(indexes, cl):
        for c in cl:
            if not isinstance(c, StandardComparator): return False
        hpaths = set([hashable_path(p.meta.dealiased) for p in cl.paths])
        if len(hpaths) != 1: return False
        return next(iter(hpaths)) in indexes

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
#
# Takes a list of joins and picks the best one for indexing (based on their
# operator preference). Returns a pair that is the chosen join and the rest of
# the joins added to the input clauseblock.
# ------------------------------------------------------------------------------
def make_join_pair(joins, clauseblock):
    if not joins: return (None,clauseblock)
    joins = sorted(joins, key=lambda x : x.preference, reverse=True)
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
# JoinQueryPlan is a part of the query plan that describes the plan to execute a
# single link in a join.
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

# For a clause consisting of standard comparators align each standard comparator
def _align_clause_path(root,clause):
    if not clause: return None
    return Clause([_align_sc_path(root,sc) for sc in clause])

# Extract the placeholders
def _extract_placeholders(elements):
    output = set()
    for f in elements:
        if not f: continue
        output.update(f.placeholders)
    return output

class JoinQueryPlan(object):
    '''Input:
       - input_signature tuple,
       - root,
       - indexes associated with the underlying fact type
       - a prejoin standard-comparator (or None),
       - a prejoin clauseblock (or None),
       - a prejoin orderbyblock (or None)
       - a join standard comparator (or None),
       - a join clauseblock (or None)
       - a join orderbyblock (or None)
    '''
    def __init__(self,input_signature, root, indexes,
                 prejoincl, prejoincb, prejoinobb,
                 joinsc, joincb, joinobb):
        if not indexes: indexes = []
        self._insig = tuple([path(r) for r in input_signature])
        self._root = path(root)
        self._predicate = self._root.meta.predicate
        self._indexes = tuple([p for p in indexes \
                               if path(p).meta.predicate == self._predicate])
        self._joinsc = _align_sc_path(self._root, joinsc)
        self._joincb = joincb
        self._joinobb = joinobb
        self._prejoincl = _align_clause_path(self._root.meta.dealiased, prejoincl)
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

        # The joinsc, joincb, and joinobb must refer only to the insig + root
        allroots = list(self._insig) + [self._root]
        if not _check_roots(allroots, joinsc):
            raise ValueError(("Join comparator '{}' refers to non '{}' "
                              "paths").format(joinsc,allroots))
        if not _check_roots(allroots, joincb):
            raise ValueError(("Join clause block '{}' refers to non '{}' "
                              "paths").format(joincb,allroots))

        if not _check_roots(allroots, joinobb):
            raise ValueError(("Join order by block '{}' refers to non '{}' "
                              "paths").format(joinobb,allroots))

        self._placeholders = _extract_placeholders(
            [self._joinsc, self._joincb, self._prejoincl, self._prejoincb])


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

        rootcbses, catchall = partition_clauses(clauses)
        if not rootcbses:
            (prejoincl,prejoincb) = (None,None)
        elif len(rootcbses) == 1:
            (prejoincl,prejoincb) = make_prejoin_pair(indexes, rootcbses[0])
            prejoincl = prejoincl.dealias() if prejoincl else None
            prejoincb = prejoincb.dealias() if prejoincb else None

        else:
            raise ValueError(("Internal bug: unexpected multiple single root "
                              "clauses '{}' when we expected only "
                              "clauses for root {}").format(rootcbses,root))

        (joinsc,joincb) = make_join_pair(joins, catchall)

        prejoinobb = None
        joinobb = None
        if orderbys:
            orderbys = OrderByBlock(orderbys)
            hroots = [ hashable_path(r) for r in orderbys.roots ]
            if len(hroots) > 1 or hroots[0] != hashable_path(root):
                joinobb = OrderByBlock(orderbys)
            else:
                prejoinobb = orderbys.dealias()

        return cls(input_signature,root, indexes,
                   prejoincl,prejoincb,prejoinobb,
                   joinsc,joincb,joinobb)


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
    def prejoin_key(self): return self._prejoincl

    @property
    def join_key(self): return self._joinsc

    @property
    def prejoin_clauses(self): return self._prejoincb

    @property
    def prejoin_orderbys(self): return self._prejoinobb

    @property
    def postjoin_clauses(self): return self._joincb

    @property
    def postjoin_orderbys(self): return self._joinobb

    @property
    def placeholders(self):
        return self._placeholders

    def ground(self,*args,**kwargs):
        gprejoincl  = self._prejoincl.ground(*args,**kwargs)  if self._prejoincl else None
        gprejoincb  = self._prejoincb.ground(*args,**kwargs)  if self._prejoincb else None
        gjoinsc = self._joinsc.ground(*args,**kwargs) if self._joinsc else None
        gjoincb = self._joincb.ground(*args,**kwargs) if self._joincb else None

        if gprejoincl == self._prejoincl and gprejoincb == self._prejoincb and \
           gjoinsc == self._joinsc and gjoincb == self._joincb: return self
        return JoinQueryPlan(self._insig,self._root, self._indexes,
                             gprejoincl,gprejoincb,self._prejoinobb,
                             gjoinsc,gjoincb,self._joinobb)

    def print(self,file=sys.stdout,pre=""):
        print("{}QuerySubPlan:".format(pre), file=file)
        print("{}\tInput Signature: {}".format(pre,self._insig), file=file)
        print("{}\tRoot path: {}".format(pre,self._root), file=file)
        print("{}\tIndexes: {}".format(pre,self._indexes), file=file)
        print("{}\tPrejoin key: {}".format(pre,self._prejoincl), file=file)
        print("{}\tPrejoin clauses: {}".format(pre,self._prejoincb), file=file)
        print("{}\tPrejoin order_by: {}".format(pre,self._prejoinobb), file=file)
        print("{}\tJoin key: {}".format(pre,self._joinsc), file=file)
        print("{}\tPost join clauses: {}".format(pre,self._joincb), file=file)
        print("{}\tPost join order_by: {}".format(pre,self._joinobb), file=file)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        if self._insig != other._insig: return False
        if self._root.meta.hashable != other._root.meta.hashable: return False
        if self._prejoincl != other._prejoincl: return False
        if self._prejoincb != other._prejoincb: return False
        if self._prejoinobb != other._prejoinobb: return False
        if self._joinsc != other._joinsc: return False
        if self._joincb != other._joincb: return False
        return True

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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

    def ground(self,*args,**kwargs):
        newqpjs = [qpj.ground(*args,**kwargs) for qpj in self._jqps]
        if tuple(newqpjs) == self._jqps: return self
        return QueryPlan(newqpjs)

    def __eq__(self, other):
        if not isinstance(other, self.__class__): return NotImplemented
        return self._jqps == other._jqps

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

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
# case is that the orderbys are in the same order as the root_join_order.
# ------------------------------------------------------------------------------

def partition_orderbys(root_join_order, orderbys=[]):
    partitions = make_orderby_partitions(root_join_order,orderbys)
    partitions = remove_orderby_gaps(partitions)
    partitions = merge_orderby_partitions(root_join_order,partitions)
    return partitions

#------------------------------------------------------------------------------
# QuerySpec stores all the information about a query in one data-structure
#------------------------------------------------------------------------------

QuerySpec = collections.namedtuple('QuerySpec', 'roots join where order_by')

def modify_query_spec(inspec,join=None,where=None,order_by=None):
    if join is None: join = inspec.join
    if where is None: where = inspec.where
    if order_by is None: order_by = inspec.order_by
    return QuerySpec(roots=inspec.roots, join=join,
                     where=where, order_by=order_by)

# Replace any None with a []
def fix_query_spec(inspec):
    join = inspec.join if inspec.join else []
    where = inspec.where if inspec.where else []
    order_by = inspec.order_by if inspec.order_by else []
    return QuerySpec(roots=inspec.roots, join=join,
                     where=where, order_by=order_by)

# ------------------------------------------------------------------------------
# Takes a list of paths that have an index, then based on a
# list of root paths and a list of joins, builds the queryplan.
# ------------------------------------------------------------------------------

def make_query_plan_preordered_roots(indexed_paths, root_join_order,
                                     query_spec):

    query_spec = fix_query_spec(query_spec)
    joins = query_spec.join
    whereclauses = query_spec.where
    orderbys = query_spec.order_by

    joinset=set(joins)
    clauseset=set(whereclauses)
    visited=set({})
    orderbys=list(orderbys)

    if not root_join_order:
        raise ValueError("Cannot make query plan with empty root join order")

    orderbygroups = partition_orderbys(root_join_order, orderbys)

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
        visited.add(hashable_path(root))
        rpjoins = visitedsubset(visited, joinset)
        rpclauses = visitedsubset(visited, clauseset)
        if rorderbys: rorderbys = OrderByBlock(rorderbys)

        output.append(JoinQueryPlan.from_specification(indexed_paths,
                                                       root_join_order[:idx],
                                                       root,rpjoins,rpclauses,
                                                       rorderbys))
    return QueryPlan(output)

# ------------------------------------------------------------------------------
# Order a list of join expressions heuristically. Returns a list of root paths
# where the first should be the outer loop query and the last should be the
# inner loop query.
#
# The idea is to assign a preference value to each join expression based on the
# number of join expressions connected with a root path and the operator
# preference. The higher the value the further it is to the inner loop. The
# intuition is that the inner loop will be repeated the most so should be the
# one that can the executed the quickes.
#
# ------------------------------------------------------------------------------

def fixed_join_order_heuristic(indexed_paths, query_spec):
    qspec = fix_query_spec(query_spec)
    return [path(r) for r in qspec.roots]


def basic_join_order_heuristic(indexed_paths, query_spec):
    qspec = fix_query_spec(query_spec)
    roots= qspec.roots
    joins= qspec.join

    root2val = { hashable_path(rp) : 0 for rp in roots }
    for join in joins:
        for rp in join.roots:
            hrp = hashable_path(rp)
            v = root2val.setdefault(hrp, 0)
            root2val[hrp] += join.preference
    return [path(hrp) for hrp in sorted(root2val.keys(), key = lambda k : root2val[k])]


# ------------------------------------------------------------------------------
# Take a join order heuristic, a list of joins, and a list of clause blocks and
# and generates a query.
# ------------------------------------------------------------------------------

def make_query_plan(join_order_heuristic, indexed_paths, query_spec):
    root_join_order=join_order_heuristic(indexed_paths, query_spec)
    return make_query_plan_preordered_roots(indexed_paths, root_join_order, query_spec)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
