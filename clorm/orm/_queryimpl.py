#------------------------------------------------------------------------------
# Clorm Query implementation
#------------------------------------------------------------------------------


import functools
from typing import (Any, Callable, Dict, Generator, Generic, Iterator, Tuple,
                    Type, TypeVar, Union, overload)

from clorm.orm.factcontainers import FactMap

from ._typing import _T0, _T1, _T2, _T3, _T4
from .core import Predicate, and_
from .query import (Query, QueryExecutor, QuerySpec, make_query_plan,
                    process_join, process_orderby, process_where)

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
SelfQuery = TypeVar("SelfQuery", bound="BaseQueryImpl[Any]")
_T = TypeVar("_T", bound=Any)
_Fn = TypeVar("_Fn", bound=Callable[..., Any])

#------------------------------------------------------------------------------
# New Clorm Query API
#
# QueryImpl
# - factmaps             - dictionary mapping predicate types to FactMap objects
# - qspec                - a dictionary with query parameters
#------------------------------------------------------------------------------

def _generate(fn: _Fn) -> _Fn:
    """Copy decorator.

    This decorator copies the object and runs the copied object.
    """

    @functools.wraps(fn)
    def wrap(self: 'BaseQueryImpl', *args: Any, **kw: Any) -> Any:
        self = self.__class__(self._factmaps, self._qspec)
        x = fn(self, *args, **kw)
        assert x is self, "methods must return self"
        return self

    return wrap # type: ignore

@overload
def _check_join_called_first(*, endpoint: bool=False) -> Callable[[_Fn], _Fn]: ...

@overload
def _check_join_called_first(_fn: _Fn, *, endpoint: bool=False) -> _Fn: ...

def _check_join_called_first(_fn=None, *, endpoint=False):
    """test whether a precondition to call the decorated function is met"""
    def wrap(fn: _Fn) -> _Fn:
        @functools.wraps(fn)
        def check(self: 'BaseQueryImpl', *args: Any, **kwargs: Any) -> Any:
            if self._qspec.join is not None or len(self._qspec.roots) == 1:
                return fn(self, *args, **kwargs)
            if endpoint:
                raise ValueError(("A query over multiple predicates is incomplete without "
                                "'join' clauses connecting these predicates"))
            raise ValueError("A 'join' clause must be specified before '{}'".format(fn.__name__))
        return check # type: ignore
    
    if _fn is None:
        return wrap
    return wrap(_fn)


class BaseQueryImpl(Query, Generic[_T]):

    def __init__(self, factmaps: Dict[Type[Predicate], FactMap], qspec: QuerySpec) -> None:
        self._factmaps = factmaps
        self._qspec = qspec

    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    @_generate
    def join(self: SelfQuery, *expressions: Any) -> SelfQuery:
        join=process_join(expressions, self._qspec.roots)
        self._qspec = self._qspec.newp(join=join)
        return self

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def where(self: SelfQuery, *expressions: Any) -> SelfQuery:
        if not expressions:
            self._qspec.newp(where=None)    # Raise an error

        if len(expressions) == 1:
            where = process_where(expressions[0], self._qspec.roots)
        else:
            where = process_where(and_(*expressions), self._qspec.roots)

        self._qspec = self._qspec.newp(where=where)
        return self

    #--------------------------------------------------------------------------
    # Add an orderered() flag
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def ordered(self: SelfQuery, *expressions: Any) -> SelfQuery:
        if self._qspec.getp("order_by",None) is not None:
            raise ValueError(("Invalid query 'ordered' declaration conflicts "
                              "with previous 'order_by' declaration"))
        self._qspec = self._qspec.newp(ordered=True)
        return self

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def order_by(self: SelfQuery, *expressions: Any) -> SelfQuery:
        if not expressions:
            self._qspec = self._qspec.newp(order_by=None)   # raise exception
        elif self._qspec.getp("ordered",False):
            raise ValueError(("Invalid query 'order_by' declaration '{}' "
                              "conflicts with previous 'ordered' "
                              "declaration").format(expressions))
        else:
            self._qspec = self._qspec.newp(
                order_by=process_orderby(expressions,self._qspec.roots))
        return self

    @_generate
    @_check_join_called_first
    def select(self, *outsig: Any) -> Any:
        if not outsig:
            raise ValueError("An empty 'select' signature is invalid")
        self._qspec = self._qspec.newp(select=outsig)
        return self

    #--------------------------------------------------------------------------
    # The distinct flag
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def distinct(self: SelfQuery) -> SelfQuery:
        self._qspec = self._qspec.newp(distinct=True)
        return self

    #--------------------------------------------------------------------------
    # Ground - bind
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def bind(self: SelfQuery, *args: Any, **kwargs: Any) -> SelfQuery:
        self._qspec = self._qspec.bindp(*args, **kwargs)
        return self

    #--------------------------------------------------------------------------
    # The tuple flag
    #--------------------------------------------------------------------------
    @_generate
    @_check_join_called_first
    def tuple(self) -> 'BaseQueryImpl[Any]':
        self._qspec = self._qspec.newp(tuple=True)
        return self

    #--------------------------------------------------------------------------
    # Overide the default heuristic
    #--------------------------------------------------------------------------
    @_generate
    def heuristic(self: SelfQuery, join_order: Any) -> SelfQuery:
        self._qspec = self._qspec.newp(heuristic=True, joh=join_order)
        return self

    #--------------------------------------------------------------------------
    # End points that do something useful
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # For the user to see what the query plan looks like
    #--------------------------------------------------------------------------
    @_check_join_called_first
    def query_plan(self,*args,**kwargs):
        qspec = self._qspec.fill_defaults()

        (factsets,factindexes) = \
            QueryExecutor.get_factmap_data(self._factmaps, qspec)
        return make_query_plan(factindexes.keys(), qspec)

    #--------------------------------------------------------------------------
    # Return the placeholders
    #--------------------------------------------------------------------------
    @property
    def qspec(self):
        return self._qspec

    #--------------------------------------------------------------------------
    # Select to display all the output of the query
    # --------------------------------------------------------------------------
    @_check_join_called_first(endpoint=True)
    def all(self) -> Generator[_T, None, None]:
        qe = QueryExecutor(self._factmaps, self._qspec)
        return qe.all()

    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    @_check_join_called_first(endpoint=True)
    def singleton(self) -> _T:
        qe = QueryExecutor(self._factmaps, self._qspec)
        gen = qe.all()
        first = next(gen, None)
        if first is None:
            raise ValueError("Query has no matching elements")
        second = next(gen, None)
        if second is not None:
            raise ValueError("Query returned more than a single element")
        return first

    #--------------------------------------------------------------------------
    # Return the count of elements - Note: the behaviour of what is counted
    # changes if group_by() has been specified.
    # --------------------------------------------------------------------------
    @overload
    def count(self: 'GroupedQuery[_T0, Any]') -> Iterator[Tuple[_T0, int]]: ... # type: ignore
    
    @overload
    def count(self: 'BaseQueryImpl[Any]') -> int: ...

    @_check_join_called_first(endpoint=True)
    def count(self) -> Union[Iterator[Tuple[Any, int]], int]:
        qe = QueryExecutor(self._factmaps, self._qspec)

        def group_by_generator():
            for k, g in qe.all():
                yield k, sum(1 for _ in g)

        # If group_by is set then we want to count records associated with each
        # key and not just total records.
        if self._qspec.group_by:
            return group_by_generator()
        else:
            return sum(1 for _ in qe.all())


    #--------------------------------------------------------------------------
    # Return the first element of the query
    # --------------------------------------------------------------------------
    @_check_join_called_first(endpoint=True)
    def first(self) -> _T:
        qe = QueryExecutor(self._factmaps, self._qspec)

        for out in qe.all():
            return out
        raise ValueError("Query has no matching elements")

    #--------------------------------------------------------------------------
    # Delete a selection of fact
    #--------------------------------------------------------------------------
    @_check_join_called_first(endpoint=True)
    def delete(self) -> int:
        qe = QueryExecutor(self._factmaps, self._qspec)
        return qe.delete()


class UnGroupedQuery(BaseQueryImpl[_T], Generic[_T]):

    #--------------------------------------------------------------------------
    # Add a group_by expression
    #--------------------------------------------------------------------------
    # START OVERLOADED FUNCTIONS self.group_by;GroupedQuery[{0}, _T];1;5;Type;Y

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py

    @overload
    def group_by(
        self, __ent0: Type[_T0]
    ) -> 'GroupedQuery[_T0, _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0
    ) -> 'GroupedQuery[_T0, _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1]
    ) -> 'GroupedQuery[Tuple[_T0, _T1], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1
    ) -> 'GroupedQuery[Tuple[_T0, _T1], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1]
    ) -> 'GroupedQuery[Tuple[_T0, _T1], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1
    ) -> 'GroupedQuery[Tuple[_T0, _T1], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    @overload
    def group_by(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4], _T]':
        ...

    # END OVERLOADED FUNCTIONS self.group_by

    @overload
    def group_by(self, *expressions: Any) -> 'GroupedQuery[Any, _T]': ...
    
    def group_by(self, *expressions: Any) -> 'GroupedQuery[Any, _T]':
        if not expressions:
            nqspec = self._qspec.newp(group_by=None)   # raise exception
        else:
            nqspec = self._qspec.newp(
                group_by=process_orderby(expressions,self._qspec.roots))
        return GroupedQuery(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Explicitly select the elements to output or delete
    #--------------------------------------------------------------------------
    # START OVERLOADED FUNCTIONS self.select;UnGroupedQuery[{0}];1;5;Type;Y

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py

    @overload
    def select(
        self, __ent0: Type[_T0]
    ) -> 'UnGroupedQuery[_T0]':
        ...

    @overload
    def select(
        self, __ent0: _T0
    ) -> 'UnGroupedQuery[_T0]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'UnGroupedQuery[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    # END OVERLOADED FUNCTIONS self.select

    @overload
    def select(self, *outsig: Any) -> 'UnGroupedQuery[Any]': ...

    def select(self, *outsig: Any) -> Any:
        return super().select(*outsig)


_KT = TypeVar("_KT", bound=Any) # Key type of GroupedQuery
_GT = TypeVar("_GT", bound=Any) # Group type of GroupedQuery


class GroupedQuery(BaseQueryImpl[Tuple[_KT, Iterator[_GT]]], Generic[_KT, _GT]):

    def group_by(self, *expressions):
        # ABC 'Query' requires to implement group_by, but multiple group_by are not allowed
        # so we raise an error here
        # a better solution would be to somehow adjust 'Query' that GroupedQuery
        # doesn't need to implement group_by
        raise ValueError("Cannot specify 'group_by' multiple times")

    # START OVERLOADED FUNCTIONS self.select;GroupedQuery[_KT, {0}];1;5;Type;Y

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py

    @overload
    def select(
        self, __ent0: Type[_T0]
    ) -> 'GroupedQuery[_KT, _T0]':
        ...

    @overload
    def select(
        self, __ent0: _T0
    ) -> 'GroupedQuery[_KT, _T0]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: Type[_T0], __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: Type[_T1], __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: Type[_T2], __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: Type[_T3], __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: Type[_T4]
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    @overload
    def select(
        self, __ent0: _T0, __ent1: _T1, __ent2: _T2, __ent3: _T3, __ent4: _T4
    ) -> 'GroupedQuery[_KT, Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    # END OVERLOADED FUNCTIONS self.select

    @overload
    def select(self, *outsig: Any) -> 'GroupedQuery[_KT, Any]': ...

    def select(self, *outsig: Any) -> Any:
        return super().select(*outsig)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
