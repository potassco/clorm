# -----------------------------------------------------------------------------
# Clorm ORM FactBase query implementation. It provides the rich query API.
# ------------------------------------------------------------------------------

import io
import operator
import collections
import bisect
import abc
import functools
import itertools

from .core import *
from .core import get_field_definition, QueryCondition, PredicatePath, \
    kwargs_check_keys

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
    'not_',
    'and_',
    'or_',
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


def _hashable_paths(cond):
    if not isinstance(cond,QueryCondition): return set([])
    tmp=set([])
    for a in cond.args:
        if isinstance(a, PredicatePath): tmp.add(a.meta.hashable)
        elif isinstance(a, QueryCondition): tmp.update(_hashable_paths(a))
    return tmp

def _placeholders(cond):
    if not isinstance(cond,QueryCondition): return set([])
    tmp=set([])
    for a in cond.args:
        if isinstance(a, Placeholder): tmp.add(a.meta.hashable)
        elif isinstance(a, QueryCondition): tmp.update(_placeholders(a))
    return tmp


# ------------------------------------------------------------------------------
# User callable functions to build boolean conditions
# ------------------------------------------------------------------------------

def not_(*conditions):
    return QueryCondition(operator.not_,*conditions)
def and_(*conditions):
    return functools.reduce((lambda x,y: QueryCondition(operator.and_,x,y)),conditions)
def or_(*conditions):
    return functools.reduce((lambda x,y: QueryCondition(operator.or_,x,y)),conditions)



#------------------------------------------------------------------------------
# Functions to check, simplify, resolve placeholders, and execute queries
# ------------------------------------------------------------------------------

def _is_bool_condition(cond):
    bool_operators = {
        operator.and_ : True, operator.or_ : True, operator.not_ : True,
        operator.eq : False, operator.ne : False, operator.lt : False,
        operator.le : False, operator.gt : False, operator.ge : False }

    return bool_operators[cond.operator]

CompOpSpec = collections.namedtuple('CompOpSpec','negate')

g_compop_operators = {
    operator.eq : CompOpSpec(negate=operator.ne),
    operator.ne : CompOpSpec(negate=operator.eq),
    operator.lt : CompOpSpec(negate=operator.ge),
    operator.le : CompOpSpec(negate=operator.gt),
    operator.gt : CompOpSpec(negate=operator.le),
    operator.ge : CompOpSpec(negate=operator.lt) }



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
        if isinstance(cond,QueryCondition):
            if _is_bool_condition(cond):
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
        if isinstance(cond,QueryCondition): return True
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
            return QueryCondition(bcond.operator,newsubcond)
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
            return QueryCondition(bcond.operator,*newargs)

        if bcond.operator == operator.or_:
            if not isdynamiccond(newargs[0]):
                return True if newargs[0] else newargs[1]
            if not isdynamiccond(newargs[1]):
                return True if newargs[1] else newargs[0]
            if newargs[0] is bcond.args[0] and newargs[1] is bcond.args[1]:
                return bcond
            return QueryCondition(bcond.operator,*newargs)

    def simplify_condition(cond):
        if isinstance(cond,Placeholder):
            raise ValueError(("Invalid condition '{}' in query '{}': a Placeholder must be "
                              "part of a comparison condition").format(cond, qcond))
        if isinstance(cond,PredicatePath):
            raise ValueError(("Invalid condition '{}' in query '{}': a PredicatePath must be "
                              "part of a comparison condition").format(cond, qcond))
        if callable(cond): return cond
        if not isinstance(cond,QueryCondition): return bool(cond)
        if _is_bool_condition(cond):
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
        elif isinstance(cond,QueryCondition):
            newsubargs = []
            changed=False
            for subarg in cond.args:
                newsubarg = instantiate(subarg)
                if newsubarg is not subarg: changed=True
                newsubargs.append(newsubarg)
            if changed: return QueryCondition(cond.operator,*newsubargs)
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
        if isinstance(cond,QueryCondition):
            if _is_bool_condition(cond):
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

        if isinstance(cond, QueryCondition):
            if not _is_bool_condition(cond):
                return validate_indexable(get_indexable(cond))
        indexable = None
        if isinstance(cond, QueryCondition) and cond.operator == operator.and_:
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
