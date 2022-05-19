#------------------------------------------------------------------------------
# Clorm Query implementation
#------------------------------------------------------------------------------


from typing import (Any, Dict, Generator, Generic, Iterator, Tuple, Type,
                    TypeVar, cast, overload)

from clorm.orm.factcontainers import FactMap

from .._typing import _T0, _T1, _T2, _T3, _T4
from .core import Predicate, and_
from .query import (Query, QueryExecutor, QuerySpec, make_query_plan,
                    process_join, process_orderby, process_where)

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
SelfQuery = TypeVar("SelfQuery", bound="QueryImpl[Any]")
_T = TypeVar("_T", bound=Any)

#------------------------------------------------------------------------------
# New Clorm Query API
#
# QueryImpl
# - factmaps             - dictionary mapping predicate types to FactMap objects
# - qspec                - a dictionary with query parameters
#------------------------------------------------------------------------------

class QueryImpl(Query, Generic[_T]):

    def __init__(self, factmaps: Dict[Type[Predicate], FactMap], qspec: QuerySpec) -> None:
        self._factmaps = factmaps
        self._qspec = qspec

    #--------------------------------------------------------------------------
    # Internal function to test whether a function has been called and add it
    #--------------------------------------------------------------------------
    def _check_join_called_first(self, name,endpoint=False):
        if self._qspec.join is not None or len(self._qspec.roots) == 1: return
        if endpoint:
            raise ValueError(("A query over multiple predicates is incomplete without "
                              "'join' clauses connecting these predicates"))
        raise ValueError("A 'join' clause must be specified before '{}'".format(name))

    #--------------------------------------------------------------------------
    # Add a join expression
    #--------------------------------------------------------------------------
    def join(self: SelfQuery, *expressions: Any) -> SelfQuery:
        join=process_join(expressions, self._qspec.roots)
        return cast(SelfQuery, QueryImpl(self._factmaps, self._qspec.newp(join=join)))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def where(self: SelfQuery, *expressions: Any) -> SelfQuery:
        self._check_join_called_first("where")

        if not expressions:
            self._qspec.newp(where=None)    # Raise an error

        if len(expressions) == 1:
            where = process_where(expressions[0], self._qspec.roots)
        else:
            where = process_where(and_(*expressions), self._qspec.roots)

        nqspec = self._qspec.newp(where=where)
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # Add an orderered() flag
    #--------------------------------------------------------------------------
    def ordered(self: SelfQuery, *expressions: Any) -> SelfQuery:
        self._check_join_called_first("ordered")
        if self._qspec.getp("order_by",None) is not None:
            raise ValueError(("Invalid query 'ordered' declaration conflicts "
                              "with previous 'order_by' declaration"))
        nqspec = self._qspec.newp(ordered=True)
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # Add an order_by expression
    #--------------------------------------------------------------------------
    def order_by(self: SelfQuery, *expressions: Any) -> SelfQuery:
        self._check_join_called_first("order_by")
        if not expressions:
            nqspec = self._qspec.newp(order_by=None)   # raise exception
        elif self._qspec.getp("ordered",False):
            raise ValueError(("Invalid query 'order_by' declaration '{}' "
                              "conflicts with previous 'ordered' "
                              "declaration").format(expressions))
        else:
            nqspec = self._qspec.newp(
                order_by=process_orderby(expressions,self._qspec.roots))
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # Add a group_by expression
    #--------------------------------------------------------------------------
    # START OVERLOADED FUNCTIONS self.group_by QueryImpl[Tuple[{0}, Iterator[_T]]] 1-3 Type P

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py


    @overload
    def group_by(
        self,
        __ent0: Type[_T0]
    ) -> 'QueryImpl[Tuple[_T0, Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0
    ) -> 'QueryImpl[Tuple[_T0, Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: _T1
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...


    @overload
    def group_by(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[Tuple[_T0, _T1, _T2], Iterator[_T]]]':
        ...

    # END OVERLOADED FUNCTIONS self.group_by

    @overload
    def group_by(self, *expressions: Any) -> 'QueryImpl[Tuple[Any, Iterator[_T]]]': ...
    
    def group_by(self, *expressions):
        if not expressions:
            nqspec = self._qspec.newp(group_by=None)   # raise exception
        else:
            nqspec = self._qspec.newp(
                group_by=process_orderby(expressions,self._qspec.roots))
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Explicitly select the elements to output or delete
    #--------------------------------------------------------------------------
    # START OVERLOADED FUNCTIONS self.select QueryImpl 1-5 Type P

    # code within this block is **programmatically, 
    # statically generated** by generate_overloads.py


    @overload
    def select(
        self,
        __ent0: Type[_T0]
    ) -> 'QueryImpl[_T0]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0
    ) -> 'QueryImpl[_T0]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1]
    ) -> 'QueryImpl[Tuple[_T0, _T1]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1
    ) -> 'QueryImpl[Tuple[_T0, _T1]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1]
    ) -> 'QueryImpl[Tuple[_T0, _T1]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1
    ) -> 'QueryImpl[Tuple[_T0, _T1]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: Type[_T0],
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: Type[_T1],
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: Type[_T2],
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: Type[_T3],
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: Type[_T4]
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...


    @overload
    def select(
        self,
        __ent0: _T0,
    	__ent1: _T1,
    	__ent2: _T2,
    	__ent3: _T3,
    	__ent4: _T4
    ) -> 'QueryImpl[Tuple[_T0, _T1, _T2, _T3, _T4]]':
        ...

    # END OVERLOADED FUNCTIONS self.select

    @overload
    def select(self, *outsig: Any) -> 'QueryImpl[Any]': ...

    def select(self, *outsig):
        self._check_join_called_first("select")
        if not outsig:
            raise ValueError("An empty 'select' signature is invalid")
        nqspec = self._qspec.newp(select=outsig)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # The distinct flag
    #--------------------------------------------------------------------------
    def distinct(self: SelfQuery) -> SelfQuery:
        self._check_join_called_first("distinct")
        nqspec = self._qspec.newp(distinct=True)
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # Ground - bind
    #--------------------------------------------------------------------------
    def bind(self: SelfQuery, *args: Any, **kwargs: Any) -> SelfQuery:
        self._check_join_called_first("bind")
        nqspec = self._qspec.bindp(*args, **kwargs)
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # The tuple flag
    #--------------------------------------------------------------------------
    def tuple(self) -> 'QueryImpl[Any]':
        self._check_join_called_first("tuple")
        nqspec = self._qspec.newp(tuple=True)
        return QueryImpl(self._factmaps, nqspec)

    #--------------------------------------------------------------------------
    # Overide the default heuristic
    #--------------------------------------------------------------------------
    def heuristic(self: SelfQuery, join_order: Any) -> SelfQuery:
        nqspec = self._qspec.newp(heuristic=True, joh=join_order)
        return cast(SelfQuery, QueryImpl(self._factmaps, nqspec))

    #--------------------------------------------------------------------------
    # End points that do something useful
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # For the user to see what the query plan looks like
    #--------------------------------------------------------------------------
    def query_plan(self,*args,**kwargs):
        self._check_join_called_first("query_plan")
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
    def all(self) -> Generator[_T, None, None]:
        self._check_join_called_first("all",endpoint=True)

        qe = QueryExecutor(self._factmaps, self._qspec)
        return qe.all()

    #--------------------------------------------------------------------------
    # Show the single element and throw an exception if there is more than one
    # --------------------------------------------------------------------------
    def singleton(self) -> _T:
        self._check_join_called_first("singleton",endpoint=True)

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
    def count(self: 'QueryImpl[Tuple[_T0, Iterator[_T1]]]') -> Iterator[Tuple[_T0, int]]: ... # type: ignore
    
    @overload
    def count(self: 'QueryImpl[_T1]') -> int: ...

    def count(self):
        self._check_join_called_first("count",endpoint=True)

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
    def first(self) -> _T:
        self._check_join_called_first("first",endpoint=True)

        qe = QueryExecutor(self._factmaps, self._qspec)

        for out in qe.all():
            return out
        raise ValueError("Query has no matching elements")

    #--------------------------------------------------------------------------
    # Delete a selection of fact
    #--------------------------------------------------------------------------
    def delete(self) -> int:
        self._check_join_called_first("delete",endpoint=True)

        qe = QueryExecutor(self._factmaps, self._qspec)
        return qe.delete()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
