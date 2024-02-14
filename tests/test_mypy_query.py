import sys
from typing import Tuple

if sys.version_info < (3, 11):
    from typing_extensions import reveal_type
else:
    from typing import reveal_type

from clorm import FactBase, Predicate
from clorm.orm._queryimpl import GroupedQuery, UnGroupedQuery
from clorm.orm.query import QuerySpec, basic_join_order

# this code is just to test type annotations with mypy and will not work when running with python


class Customer(Predicate):
    cid: int
    name: str


class Sale(Predicate):
    sid: int
    cid: int
    item: str


class Address(Predicate):
    aid: int
    customer: Customer


def test_query_ungrouped_endpoints() -> None:
    fb = FactBase()

    query1 = fb.query(Sale, Customer)

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[Sale, Customer]]
    reveal_type(query1)

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[Address, Sale, Customer]]
    reveal_type(fb.query(Address, Sale, Customer))

    # fallback to Any if query is called with more than 5 arguments
    # EXPECTED_TYPE: UnGroupedQuery[Any]
    reveal_type(fb.query(Address, Sale, Customer, Customer, Customer, Customer))

    # For correctness all predicates must be joined.
    query1 = fb.query(Sale, Customer).join(Sale.cid == Customer.cid)

    # EXPECTED_TYPE: Generator[Tuple[Sale, Customer], None, None]
    reveal_type(query1.all())

    # EXPECTED_TYPE: Generator[Sale, None, None]
    reveal_type(fb.query(Sale).all())

    # EXPECTED_TYPE: Tuple[Sale, Customer]
    reveal_type(query1.first())

    # EXPECTED_TYPE: Tuple[Sale, Customer]
    reveal_type(query1.singleton())

    # EXPECTED_TYPE: int
    reveal_type(query1.count())

    # EXPECTED_TYPE: int
    reveal_type(query1.delete())


def test_query_ungrouped_select() -> None:
    fb = FactBase()

    query1 = fb.query()

    # EXPECTED_TYPE: UnGroupedQuery[Any]
    reveal_type(query1)

    s1 = query1.select(Sale.item, Customer)
    # EXPECTED_TYPE: UnGroupedQuery[Tuple[str, Customer]]
    reveal_type(s1)

    s2 = query1.select(Sale.cid)
    # EXPECTED_TYPE: UnGroupedQuery[int]
    reveal_type(s2)

    s3 = query1.select(Sale.cid, Customer.name, Address, Address.customer)
    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, str, Address, Customer]]
    reveal_type(s3)

    # fallback to Any if select is called with more than 5 arguments
    s4 = query1.select(Sale.cid, Sale.cid, Sale.cid, Sale.cid, Sale.cid, Sale.cid)
    # EXPECTED_TYPE: UnGroupedQuery[Any]
    reveal_type(s4)


def test_query_grouped_select() -> None:
    fb = FactBase()

    #    query1 = fb.query(Sale, Customer).join(Sale.cid == Customer.cid)
    query1 = fb.query(Sale, Customer)

    # EXPECTED_TYPE: GroupedQuery[int, Tuple[Sale, Customer]]
    reveal_type(query1.group_by(Sale.sid))

    # EXPECTED_TYPE: GroupedQuery[Tuple[Customer, int], Tuple[Sale, Customer]]
    reveal_type(query1.group_by(Customer, Sale.sid))

    # fallback to Any if group_by is called with more than 5 arguments
    # EXPECTED_TYPE: GroupedQuery[Any, Tuple[Sale, Customer]]
    reveal_type(query1.group_by(Sale.sid, Sale.sid, Sale.sid, Sale.sid, Sale.sid, Sale.sid))

    # EXPECTED_TYPE: GroupedQuery[Tuple[Customer, int], int]
    reveal_type(query1.group_by(Customer, Sale.sid).select(Customer.cid))

    # EXPECTED_TYPE: GroupedQuery[Tuple[Customer, int], Tuple[int, str]]
    reveal_type(query1.group_by(Customer, Sale.sid).select(Customer.cid, Sale.item))

    # fallback to Any if select is called with more than 5 arguments
    s4 = query1.group_by(Sale).select(Sale.cid, Sale.cid, Sale.cid, Sale.cid, Sale.cid, Sale.cid)
    # EXPECTED_TYPE: GroupedQuery[Sale, Any]
    reveal_type(s4)


def test_query_grouped_endpoints() -> None:
    fb = FactBase()
    #    query1 = fb.query(Sale, Customer).join(Sale.cid == Customer.cid).group_by(Customer, Sale.sid)
    query1 = fb.query(Sale, Customer)

    # EXPECTED_TYPE: Generator[Tuple[Tuple[Customer, int], Iterator[Tuple[Sale, Customer]]], None, None]
    reveal_type(query1.all())

    # EXPECTED_TYPE: Generator[Tuple[Tuple[Customer, int], Iterator[Customer]], None, None]
    reveal_type(query1.select(Customer).all())

    # EXPECTED_TYPE: Tuple[Customer, int], Iterator[Tuple[Sale, Customer]]]
    reveal_type(query1.singleton())

    # EXPECTED_TYPE: Tuple[Customer, int], Iterator[Tuple[Sale, Customer]]]
    reveal_type(query1.first())

    # EXPECTED_TYPE: Iterator[Tuple[Tuple[Customer, int], int]]
    reveal_type(query1.count())

    # EXPECTED_TYPE: int
    reveal_type(query1.delete())


def test_query_method_without_type_modification() -> None:

    ungrouped = UnGroupedQuery[Tuple[int, int, str]]({}, QuerySpec())

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.where(Sale.cid == 3))

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.join(Sale.cid == Customer.cid))

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.heuristic(basic_join_order))

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.ordered())

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.distinct())

    # EXPECTED_TYPE: UnGroupedQuery[Tuple[int, int, str]]
    reveal_type(ungrouped.bind(ph_=42))

    grouped = GroupedQuery[Tuple[int, str], Sale]({}, QuerySpec())

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.where(Sale.cid == 3))

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.join(Sale.cid == Customer.cid))

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.heuristic(basic_join_order))

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.ordered())

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.distinct())

    # EXPECTED_TYPE: GroupedQuery[Tuple[int, str], Sale]
    reveal_type(grouped.bind(ph_=42))


def test_query_tuple() -> None:
    # can't find a proper type annotation to handle BaseQueryImpl.tuple
    # so for now we return BaseQueryImpl[Any] to get at least a type hint which is compatible to everything
    ungrouped = UnGroupedQuery[Tuple[int, int, str]]({}, QuerySpec())

    # EXPECTED_TYPE: BaseQueryImpl[Any]
    reveal_type(ungrouped.tuple())
