# ------------------------------------------------------------------------------
# Unit tests for Clorm ORM Query API and associated classes and functions. This
# includes the query API.
#
# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import operator
import unittest

from clingo import Control, Function, Number, String, SymbolType

# Official Clorm API imports for the core complements
from clorm.orm import (
    ComplexTerm,
    ConstantField,
    IntegerField,
    Predicate,
    StringField,
    alias,
    and_,
    asc,
    cross,
    desc,
    func,
    hashable_path,
    in_,
    not_,
    notin_,
    or_,
    path,
    ph1_,
    ph2_,
    ph_,
)

# Implementation imports
from clorm.orm.core import QCondition, notcontains, trueall
from clorm.orm.factcontainers import FactIndex, FactMap, FactSet
from clorm.orm.query import (
    Clause,
    ClauseBlock,
    FunctionComparator,
    InQuerySorter,
    JoinQueryPlan,
    MembershipSeq,
    NamedPlaceholder,
    OrderBy,
    OrderByBlock,
    PositionalPlaceholder,
    QueryExecutor,
    QueryPlan,
    QuerySpec,
    StandardComparator,
    basic_join_order,
    fixed_join_order,
    is_boolean_qcondition,
    is_comparison_qcondition,
    make_chained_join_query,
    make_first_join_query,
    make_first_prejoin_query,
    make_input_alignment_functor,
    make_join_pair,
    make_prejoin_pair,
    make_prejoin_query_source,
    make_query,
    make_query_plan,
    make_query_plan_preordered_roots,
    negate_where_expression,
    normalise_where_expression,
    oppref_join_order,
    partition_clauses,
    partition_orderbys,
    process_join,
    process_orderby,
    process_where,
    validate_join_expression,
    validate_orderby_expression,
    validate_where_expression,
    where_expression_to_cnf,
    where_expression_to_nnf,
)

from .support import check_errmsg, check_errmsg_contains, to_tuple

###### NOTE: The QueryOutput tests need to be turned into QueryExecutor
###### tests. We can then delete QueryOutput which is not being used for
###### anything.


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "PlaceholderTestCase",
    "QQConditionTestCase",
    "ComparatorTestCase",
    "WhereExpressionTestCase",
    "JoinExpressionTestCase",
    "OrderByTestCase",
    "QueryPlanTestCase",
    "InQuerySorterTestCase",
    "QueryTestCase",
    "QueryExecutorTestCase",
]

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


def hpaths(paths):
    return [hashable_path(path) for path in paths]


# ------------------------------------------------------------------------------
# Test functions for Placeholder sub-classes
# ------------------------------------------------------------------------------


class PlaceholderTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_NamedPlaceholder(self):
        ph1 = NamedPlaceholder(name="foo")
        ph1alt = NamedPlaceholder(name="foo")
        ph2 = NamedPlaceholder(name="foo", default="bar")
        ph3 = NamedPlaceholder(name="foo", default=None)
        self.assertEqual(ph1, ph1alt)
        self.assertNotEqual(ph1, ph2)

        self.assertEqual(ph1.name, "foo")
        self.assertFalse(ph1.has_default)
        self.assertTrue(ph2.has_default)
        self.assertTrue(ph3.has_default)
        self.assertEqual(ph2.default, "bar")
        self.assertEqual(ph3.default, None)

        with self.assertRaises(TypeError) as ctx:
            ph = NamedPlaceholder("foo")
        check_errmsg_contains("__init__() takes 1 positional", ctx)

        with self.assertRaises(TypeError) as ctx:
            ph = NamedPlaceholder("foo", "bar")
        check_errmsg_contains("__init__() takes 1 positional", ctx)

        self.assertFalse(ph1 == 1)
        self.assertFalse(ph1 == "a")

    def test_PositionalPlaceholder(self):
        ph2 = PositionalPlaceholder(posn=1)
        ph2alt = PositionalPlaceholder(posn=1)
        ph3 = PositionalPlaceholder(posn=2)

        self.assertEqual(ph2, ph2alt)
        self.assertNotEqual(ph2, ph3)

        self.assertEqual(ph2, ph2_)

        with self.assertRaises(TypeError) as ctx:
            ph = PositionalPlaceholder(0)
        check_errmsg_contains("__init__() takes 1 positional", ctx)

        self.assertFalse(1 == ph2)
        self.assertTrue(1 != ph2)
        self.assertFalse(ph2 == 1)
        self.assertTrue(ph2 != 1)
        self.assertFalse(ph2 == "a")

    # --------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    # --------------------------------------------------------------------------
    def test_placeholder_instantiation(self):

        # Named placeholder with and without default
        p = ph_("test")
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertFalse(p.has_default)
        self.assertEqual(p.default, None)
        self.assertEqual(str(p), 'ph_("test")')

        p = ph_("test", default=0)
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default, 0)
        self.assertEqual(str(p), 'ph_("test",0)')

        p = ph_("test", default=None)
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default, None)

        # Positional placeholder
        p = ph_(1)
        self.assertEqual(type(p), PositionalPlaceholder)
        self.assertEqual(p.posn, 0)
        self.assertEqual(str(p), "ph1_")

        # Some bad initialisation
        with self.assertRaises(TypeError) as ctx:
            ph_(1, 2)
        with self.assertRaises(TypeError) as ctx:
            ph_("a", 2, 3)
        with self.assertRaises(TypeError) as ctx:
            ph_("a", default=2, arg=3)


# ------------------------------------------------------------------------------
# Test functions that manipulate query conditional and evaluate the conditional
# w.r.t a fact.
# ------------------------------------------------------------------------------


class QQConditionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField
            atuple = (IntegerField, StringField)

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

    # --------------------------------------------------------------------------
    #  Test that the fact comparators work
    # --------------------------------------------------------------------------

    def test_simple_comparison_conditional(self):
        F = self.F

        # Indentical queries with named arguments and positional arguments
        cn1 = F.anum == 2
        cn2 = F.anum == F.atuple[0]
        cn3 = F.astr == F.atuple[1]
        cn4 = F.anum == ph1_
        cn5 = F.anum == ph_("anum")

        cp1 = F[0] == 2
        cp2 = F[0] == F.atuple[0]
        cp3 = F[1] == F.atuple[1]
        cp4 = F[0] == ph1_
        cp5 = F[0] == ph_("anum")

        # NOTE: the positional and named queries generate identical strings
        # because we use a canonical form for the predicate path. Look at
        # changing this in the future.
        self.assertEqual(str(cn1), str(cp1))
        self.assertEqual(str(cn2), str(cp2))
        self.assertEqual(str(cn3), str(cp3))
        self.assertEqual(str(cn4), str(cp4))
        self.assertEqual(str(cn5), str(cp5))

        self.assertEqual(cn1, cp1)
        self.assertEqual(cn2, cp2)
        self.assertEqual(cn3, cp3)
        self.assertEqual(cn4, cp4)
        self.assertEqual(cn5, cp5)

        self.assertNotEqual(cn1, cn2)

        # Evaluating condition against some facts
        af1 = F(2, "bbb", (2, "bbb"))
        af2 = F(1, "aaa", (3, "bbb"))

        # Some other query conditions that can't be defined with the nice syntax
        # - these are forbidden
        #        c1 = QCondition(operator.eq, 2, F.anum)
        #        self.assertEqual(str(c1), "2 == F.anum")

        #        c1 = QCondition(operator.eq,2,2)
        #        self.assertEqual(str(c1), "2 == 2")

        # c1 = QCondition(operator.eq,2,1)
        # self.assertEqual(str(c1), "2 == 1")

        c1 = F.anum == F.anum
        self.assertEqual(str(c1), "F.anum == F.anum")

        f = lambda x: x.anum == 2

        # Test evaluating against a tuple
        c3 = F.atuple == ph1_

    def test_complex_comparison_conditional(self):
        F = self.F

        # Test that simplifying a complex works as expected
        c1 = and_(F.anum == 1, F.astr == ph1_)
        c3 = and_(F.anum == 1, F.anum == F.anum, F.astr == ph1_)

        c1 = ((F.anum == 1) & (F.astr == ph1_)) | ~(F.atuple == ph2_)

        # TEst simplifying works for a complex disjunction
        c1 = or_(F.anum == 1, F.anum == F.anum, F.astr == ph1_)

        c1 = or_(F.anum == 1, F.anum != F.anum, F.astr == ph1_)
        c2 = or_(F.anum == 1, F.astr == ph1_)

        # We can now detect this as problematic
        with self.assertRaises(TypeError) as ctx:
            c2 = and_(F.anum == 1, F.astr == ph1_, True)
        check_errmsg("'True' is not a valid query sub-expression", ctx)

    # -------------------------------------------------------------------------
    # Since we want to use the condition to model joins (such as using __mult__
    # to model a cross-product) so we now have non-bool and non-comparison
    # conditions. Make sure we can handle this
    # -------------------------------------------------------------------------
    def test_nonapi_not_bool_not_comparison_condition(self):
        F = self.F
        G = self.G

        self.assertTrue(is_boolean_qcondition((F.anum == 1) & (G.anum == 1)))
        self.assertFalse(is_boolean_qcondition(F.anum == 1))
        self.assertFalse(is_boolean_qcondition(cross(F, G)))


# ------------------------------------------------------------------------------
# Testing of Comparator and related items - make_
# ------------------------------------------------------------------------------


class ComparatorTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField
            atuple = (IntegerField, StringField)

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

    # ------------------------------------------------------------------------------
    #
    # ------------------------------------------------------------------------------
    def test_nonapi_make_input_alignment_functor(self):
        F = self.F
        G = self.G
        f1 = F(1, "a", (2, "b"))
        f2 = F(3, "c", (4, "d"))
        g1 = G(4, "df")

        getter = make_input_alignment_functor([F], [F.anum, F.atuple[0]])
        self.assertEqual(getter((f1,)), (1, 2))

        getter = make_input_alignment_functor([F], [10])
        self.assertEqual(getter((f1,)), (10,))

        getter = make_input_alignment_functor([F, G], [F.atuple[0], G.anum])
        self.assertEqual(getter((f1, g1)), (2, 4))

        getter = make_input_alignment_functor([F, G], [F.atuple[0]])
        self.assertEqual(getter((f1, g1)), (2,))

        getter = make_input_alignment_functor([F, G], [F.atuple[0], [1, 2]])
        self.assertEqual(getter((f1, g1)), (2, [1, 2]))

        # Test static values are passed through correctly
        getter = make_input_alignment_functor([F], [1, 2, 3])
        self.assertEqual(getter((f1,)), (1, 2, 3))

        # Make sure it can also deal with predicate aliases
        X = alias(F)
        getter = make_input_alignment_functor([X, F], [F.atuple[1], X.atuple[0], X.anum])
        self.assertEqual(getter((f1, f2)), ("d", 2, 1))

        # Testing bad creation of the getter

        # Empty input or output
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([], [F.atuple[0], G.anum])
        check_errmsg("Empty input predicate", ctx)
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([F], [])
        check_errmsg("Empty output path", ctx)

        # Missing input predicate path
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([F], [F.atuple[0], G.anum])
        check_errmsg("Invalid signature match", ctx)

        # Bad input is not a path
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([2], [F.atuple[0]])
        check_errmsg("Invalid input predicate path signature", ctx)

        # Bad input is not a predicate
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([F.anum], [F.atuple[0]])
        check_errmsg("Invalid input predicate path", ctx)

        # Bad output is a placeholder
        with self.assertRaises(TypeError) as ctx:
            make_input_alignment_functor([F], [F.atuple[0], ph1_])
        check_errmsg("Output signature '[F.atuple.arg1", ctx)

        # Test bad inputs to the getter
        with self.assertRaises(TypeError) as ctx:
            getter((f1,))
        check_errmsg("Invalid input to getter function: expecting", ctx)

        with self.assertRaises(TypeError) as ctx:
            getter((f1, 2))
        check_errmsg("Invalid input to getter function:", ctx)

    # ------------------------------------------------------------------------------
    #
    # ------------------------------------------------------------------------------
    def test_nonapi_make_input_alignment_functor_complex(self):
        class F(Predicate):
            anum = IntegerField
            acomplex = (IntegerField, IntegerField)

        f1 = F(1, (1, 2))
        f2 = F(2, (3, 4))

        # FIXUP
        getter = make_input_alignment_functor([F], [F.acomplex])
        result = getter((f1,))
        tmp = ((1, 2),)
        self.assertEqual(to_tuple(result), tmp)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_StandardComparator(self):
        F = self.F
        G = self.G
        X = alias(F)

        def hps(paths):
            return set([hashable_path(p) for p in paths])

        SC = StandardComparator

        # Test __str__
        self.assertEqual(str(SC(operator.eq, [F.anum, 4])), "F.anum == 4")

        # Test __eq__ and __ne__
        self.assertEqual(SC(operator.eq, [F.anum, 4]), SC(operator.eq, [F.anum, 4]))
        self.assertNotEqual(SC(operator.eq, [F.anum, 4]), SC(operator.eq, [F.anum, 3]))
        self.assertNotEqual(SC(operator.eq, [F.anum, 4]), SC(operator.eq, [F.anum, ph1_]))

        # Test __hash__
        self.assertEqual(hash(SC(operator.eq, [F.anum, 4])), hash(SC(operator.eq, [F.anum, 4])))

        # Test negating
        self.assertEqual(SC(operator.eq, [F.anum, 4]).negate(), SC(operator.ne, [F.anum, 4]))
        self.assertEqual(SC(operator.ne, [F.anum, 4]).negate(), SC(operator.eq, [F.anum, 4]))
        self.assertEqual(SC(operator.lt, [F.anum, 4]).negate(), SC(operator.ge, [F.anum, 4]))
        self.assertEqual(SC(operator.le, [F.anum, 4]).negate(), SC(operator.gt, [F.anum, 4]))
        self.assertEqual(SC(operator.gt, [F.anum, 4]).negate(), SC(operator.le, [F.anum, 4]))
        self.assertEqual(SC(operator.ge, [F.anum, 4]).negate(), SC(operator.lt, [F.anum, 4]))

        self.assertNotEqual(SC(operator.eq, [F.anum, 4]).negate(), SC(operator.eq, [F.anum, 4]))

        # Test dealiasing
        self.assertEqual(SC(operator.eq, [F.anum, 4]).dealias(), SC(operator.eq, [F.anum, 4]))
        self.assertEqual(SC(operator.eq, [X.anum, 4]).dealias(), SC(operator.eq, [F.anum, 4]))
        self.assertEqual(
            SC(operator.eq, [X.anum, X.astr]).dealias(), SC(operator.eq, [F.anum, F.astr])
        )

        # Test swap operation
        self.assertEqual(SC(operator.eq, [F.anum, 4]).swap(), SC(operator.eq, [4, F.anum]))
        self.assertEqual(SC(operator.ne, [F.anum, 4]).swap(), SC(operator.ne, [4, F.anum]))
        self.assertEqual(SC(operator.lt, [F.anum, 4]).swap(), SC(operator.gt, [4, F.anum]))
        self.assertEqual(SC(operator.le, [F.anum, 4]).swap(), SC(operator.ge, [4, F.anum]))
        self.assertEqual(SC(operator.gt, [F.anum, 4]).swap(), SC(operator.lt, [4, F.anum]))
        self.assertEqual(SC(operator.ge, [F.anum, 4]).swap(), SC(operator.le, [4, F.anum]))

        # Test paths
        self.assertEqual(hps(SC(operator.eq, [F.anum, 4]).paths), hps([F.anum]))
        self.assertEqual(hps(SC(operator.eq, [F.anum, F.anum]).paths), hps([F.anum]))
        self.assertEqual(hps(SC(operator.eq, [F.anum, F.astr]).paths), hps([F.anum, F.astr]))

        # Test placeholders
        self.assertEqual(SC(operator.eq, [F.anum, 4]).placeholders, set())
        self.assertEqual(SC(operator.eq, [F.anum, ph1_]).placeholders, set([ph1_]))
        self.assertEqual(SC(operator.eq, [F.anum, ph_("b")]).placeholders, set([ph_("b")]))

        # Test roots
        self.assertEqual(hps(SC(operator.eq, [F.anum, 4]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq, [F.anum, F.anum]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq, [F.anum, F.astr]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq, [F.anum, G.anum]).roots), hps([F, G]))
        X = alias(F)
        self.assertEqual(hps(SC(operator.eq, [X.anum, F.anum]).roots), hps([X, F]))

        # Test grounding
        self.assertEqual(SC(operator.eq, [F.anum, 4]), SC(operator.eq, [F.anum, 4]).ground())

        self.assertEqual(
            SC(operator.eq, [F.anum, ph2_]).ground(1, 4), SC(operator.eq, [F.anum, 4])
        )
        self.assertEqual(
            SC(operator.eq, [F.anum, ph_("val")]).ground(1, 4, val=4),
            SC(operator.eq, [F.anum, 4]),
        )

        # Bad grounding
        with self.assertRaises(ValueError) as ctx:
            SC(operator.eq, [F.anum, ph_("val")]).ground(1, 4)
        check_errmsg("Missing named", ctx)
        with self.assertRaises(ValueError) as ctx:
            SC(operator.eq, [F.anum, ph2_]).ground(1)
        check_errmsg("Missing positional", ctx)

        # Test make_callable
        self.assertTrue(SC(operator.eq, [1, 1]).make_callable([G])(5))
        self.assertTrue(SC(operator.eq, [G.anum, 1]).make_callable([G])((G(1, "b"),)))
        self.assertFalse(SC(operator.eq, [G.anum, 1]).make_callable([G])((G(2, "b"),)))
        sc = SC(operator.eq, [G.anum, 1]).make_callable([F, G])
        self.assertFalse(sc((F(1, "b", (1, "b")), G(2, "b"))))
        self.assertTrue(sc((F(1, "b", (1, "b")), G(1, "b"))))

        # Cannot make_callable on ungrounded
        with self.assertRaises(TypeError) as ctx:
            SC(operator.eq, [G.anum, ph1_]).make_callable([F, G])

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_StandardComparator_make_callable_with_tuples(self):
        SC = StandardComparator

        class F(Predicate):
            anum = IntegerField
            acomplex = (IntegerField, IntegerField)

        f1 = F(1, (1, 2))
        f2 = F(1, (1, 3))

        getter = make_input_alignment_functor([F], [F.acomplex])
        result = getter((f1,))
        self.assertEqual(to_tuple(result), ((1, 2),))

        sc = SC(operator.eq, [F.acomplex, F.meta[1].defn.complex(1, 2)])
        cmp = sc.make_callable([F])
        self.assertTrue(cmp((f1,)))
        self.assertFalse(cmp((f2,)))

    # ------------------------------------------------------------------------------
    # Test the standard comparator keyable function
    # ------------------------------------------------------------------------------
    def test_nonapi_StandardComparator_keyable(self):
        SC = StandardComparator

        class F(Predicate):
            anum = IntegerField

        sc = SC(operator.eq, [F.anum, 2])
        result = sc.keyable([])
        self.assertEqual(result, None)

        # F.anum == 2
        sc = SC(operator.eq, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.eq, 2))

        # F.anum != 2
        sc = SC(operator.ne, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.ne, 2))

        # F.anum < 2
        sc = SC(operator.lt, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.lt, 2))

        # F.anum <= 2
        sc = SC(operator.le, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.le, 2))

        # F.anum > 2
        sc = SC(operator.gt, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.gt, 2))

        # F.anum >= 2
        sc = SC(operator.ge, [F.anum, 2])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.ge, 2))

        # 2 == F.anum
        sc = SC(operator.eq, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.eq, 2))

        # 2 != F.anum
        sc = SC(operator.ne, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.ne, 2))

        # 2 < F.anum
        sc = SC(operator.lt, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.gt, 2))

        # 2 <= F.anum
        sc = SC(operator.le, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.ge, 2))

        # 2 > F.anum
        sc = SC(operator.gt, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.lt, 2))

        # 2 >= F.anum
        sc = SC(operator.ge, [2, F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.le, 2))

        # Membership operators
        # No keyable
        sc = SC(operator.contains, [[1, 2], F.anum])
        self.assertEqual(sc.keyable([]), None)

        # F.anum in [1,2]
        sc = SC(operator.contains, [[1, 2], F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), operator.contains, [1, 2]))

        # F.anum not in [1,2]
        sc = SC(notcontains, [[1, 2], F.anum])
        self.assertEqual(sc.keyable([F.anum]), (hashable_path(F.anum), notcontains, [1, 2]))

    # ------------------------------------------------------------------------------
    # Test the wrapping of comparison functors in FunctionComparator
    # ------------------------------------------------------------------------------
    def test_nonapi_FunctionComparator(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        F = self.F
        G = self.G

        func1 = lambda x: x.anum >= 0
        func2 = lambda x, y: x == y

        bf1 = FunctionComparator(func1, [path(F)])
        bf2 = FunctionComparator(func2, [F.anum, F.atuple[0]])

        self.assertEqual(hps(bf1.paths), hps([F]))
        self.assertEqual(hps(bf2.paths), hps([F.anum, F.atuple[0]]))

        nbf1 = FunctionComparator(func1, [path(F)], negative=True)
        self.assertEqual(bf1.negate(), nbf1)

        sat1 = bf1.ground().make_callable([F])
        nsat1 = bf1.negate().ground().make_callable([F])
        nsat2 = bf1.ground().negate().make_callable([F])
        fact1 = F(1, "ab", (-2, "abc"))
        fact2 = F(-1, "ab", (2, "abc"))

        self.assertTrue(sat1((fact1,)))
        self.assertFalse(sat1((fact2,)))

        self.assertFalse(nsat1((fact1,)))
        self.assertFalse(nsat2((fact1,)))
        self.assertTrue(nsat1((fact2,)))
        self.assertTrue(nsat2((fact2,)))

        self.assertEqual(bf1.ground(), bf1.ground().ground())

        # Test the paths and roots properties
        func3 = lambda x, y, z: x == y + z
        X = alias(F)
        bf = func([F.anum, X.anum, G.anum], func3)
        bf = FunctionComparator.from_specification(bf.paths, bf.functor)
        self.assertEqual(hps(bf.paths), hps([F.anum, X.anum, G.anum]))
        self.assertEqual(hps(bf.roots), hps([F, X, G]))

        func4 = lambda x: x > 5
        bf1 = FunctionComparator.from_specification([F.anum], func4)
        bf2 = FunctionComparator.from_specification([X.anum], func4)
        self.assertNotEqual(bf1, bf2)
        self.assertNotEqual(hps(bf1.roots), hps(bf2.roots))
        self.assertEqual(bf1, bf2.dealias())
        self.assertEqual(hps(bf1.roots), hps(bf2.dealias().roots))

        with self.assertRaises(RuntimeError) as ctx:
            bf1.make_callable([F])
        check_errmsg("Internal bug: make_callable", ctx)

        with self.assertRaises(ValueError) as ctx:
            bf = FunctionComparator(func1, [])
        check_errmsg("Invalid empty path signature", ctx)

    # ------------------------------------------------------------------------------
    # Test more complex case of wrapping of comparison functors in
    # FunctionComparator
    # ------------------------------------------------------------------------------
    def test_nonapi_FunctionComparator_with_args(self):
        def hps(paths):
            return [hashable_path(p) for p in paths]

        F = self.F
        func1 = lambda x, y: x.anum >= y
        func2 = lambda x, y=10: x.anum >= y

        # grounding with named placeholders
        bf1 = FunctionComparator(func1, [F.anum, F.astr])
        self.assertEqual(bf1.ground().placeholders, set())
        bf1 = FunctionComparator(func1, [F.anum])
        self.assertEqual(bf1.placeholders, set([ph_("y")]))
        bf1 = FunctionComparator(func1, [F.anum], assignment={"y": 5})
        self.assertEqual(bf1.placeholders, set())

        bf1 = FunctionComparator(func2, [F.anum])
        self.assertEqual(bf1.ground(), bf1.ground(y=10))
        self.assertNotEqual(bf1.ground(), bf1.ground(y=11))

        bf1 = FunctionComparator(func1, [path(F)])
        assignment = {"y": 1}
        gbf1 = FunctionComparator(func1, [path(F)], False, assignment)
        self.assertEqual(gbf1, bf1.ground(**assignment))

        # grounding with positional placeholders
        fc = FunctionComparator(func1, [path(F)])
        gfc_args = fc.ground(1)
        gfc_kwargs = fc.ground(y=1)
        self.assertEqual(len(fc.placeholders), 1)
        self.assertEqual(len(gfc_args.placeholders), 0)
        self.assertEqual(gfc_args, gfc_kwargs)

        # Partial grounding will fail
        with self.assertRaises(ValueError) as ctx:
            bf1.ground()
        check_errmsg("Missing named placeholder", ctx)

        # Too many paths
        with self.assertRaises(ValueError) as ctx:
            bf1 = FunctionComparator(func1, [F.anum, F.astr, F.atuple])
        check_errmsg("More paths specified", ctx)

        # Bad assignment parameter value
        with self.assertRaises(ValueError) as ctx:
            bf1 = FunctionComparator(func1, [F.anum], assignment={"k": 5})
        check_errmsg("FunctionComparator is being given an assignment", ctx)

        # Conflicting grounding with positional and keyword arguments
        with self.assertRaises(ValueError) as ctx:
            fc = FunctionComparator(func1, [F.anum])
            gfc = fc.ground(1, y=1)
        check_errmsg("Both positional and keyword", ctx)

        bf1 = FunctionComparator(lambda x, y: x < y, [F.anum, F.atuple[0]])
        sat1 = bf1.ground().make_callable([F])
        nsat1 = bf1.negate().ground().make_callable([F])
        fact1 = F(1, "ab", (-2, "abc"))
        fact2 = F(-1, "ab", (2, "abc"))

        self.assertFalse(sat1((fact1,)))
        self.assertTrue(nsat1((fact1,)))
        self.assertTrue(sat1((fact2,)))
        self.assertFalse(nsat1((fact2,)))

    # ------------------------------------------------------------------------------
    # Test the func API functor for creating FunctionComparator
    # ------------------------------------------------------------------------------
    def test_api_func(self):

        F = self.F
        G = self.G
        func1 = lambda x, y: x.anum == y.anum

        wrap1 = FunctionComparator(func1, [F, G])
        wrap2 = func([F, G], func1)
        wrap2 = FunctionComparator.from_specification(wrap2.paths, wrap2.functor)
        self.assertEqual(wrap1, wrap2)
        sat1 = wrap1.ground().make_callable([F, G])
        sat2 = wrap2.ground().make_callable([F, G])

        f1 = F(1, "ab", (-2, "abc"))
        f2 = F(-1, "ab", (2, "abc"))
        g1 = G(1, "2")
        g2 = G(-1, "4")
        self.assertTrue(sat1((f1, g1)))
        self.assertEqual(sat1((f1, g1)), sat2((f1, g1)))

        self.assertFalse(sat1((f2, g1)))
        self.assertEqual(sat1((f2, g1)), sat2((f2, g1)))

    # ------------------------------------------------------------------------------
    # Make ComparisonCallable objects from either any ground comparison condition.
    # ------------------------------------------------------------------------------
    def test_nonapi_comparison_callables(self):
        F = self.F
        G = self.G
        func1 = lambda x, y: x == y

        wrap2 = FunctionComparator.from_specification([F.anum, G.anum], func1)
        sat1 = wrap2.ground().make_callable([G, F])
        sat2 = StandardComparator.from_where_qcondition(F.anum == G.anum).make_callable([G, F])

        f1 = F(1, "ab", (-2, "abc"))
        f2 = F(-1, "ab", (2, "abc"))
        g1 = G(1, "4")
        g2 = G(-1, "4")

        self.assertTrue(sat1((g1, f1)))
        self.assertTrue(sat2((g1, f1)))
        self.assertTrue(sat1((g2, f2)))
        self.assertTrue(sat2((g2, f2)))

        self.assertFalse(sat1((g1, f2)))
        self.assertFalse(sat2((g1, f2)))
        self.assertFalse(sat1((g2, f1)))
        self.assertFalse(sat2((g2, f1)))

        # Bad calls to the callable
        with self.assertRaises(TypeError) as ctx:
            sat1(g1, f1)
        check_errmsg_contains("__call__() takes 2", ctx)

        # NOTE: Now using the attrgetter which is more liberal and doesn't check
        # for the correct predicate type. So this error is no longer raised.
        #        with self.assertRaises(TypeError) as ctx:
        #            sat1((f1,g1))
        #        check_errmsg("Invalid input", ctx)

        # Bad calls to make_comparison_callable
        with self.assertRaises(TypeError) as ctx:
            sc = StandardComparator.from_where_qcondition(F.anum == G.anum)
            sc.make_callable([G])
        check_errmsg("Invalid signature match", ctx)


# ------------------------------------------------------------------------------
# Test query "where" expressions. Turning nested QConditions into a set of
# clauses.
# ------------------------------------------------------------------------------


class WhereExpressionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField
            atuple = (IntegerField, StringField)

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_where_expression(self):
        F = self.F
        G = self.G

        vwe = validate_where_expression
        wsc = StandardComparator.from_where_qcondition
        mfc = FunctionComparator.from_specification

        # Comparison QConditions and raw functions are turned into Comparators
        self.assertEqual(vwe((F.anum == 4), [F]), wsc(F.anum == 4))
        self.assertEqual(vwe(~(F.anum == 4), [F]), not_(wsc(F.anum == 4)))
        self.assertEqual(
            vwe((F.anum == 4) & (F.astr == "df"), [F]),
            and_(wsc(F.anum == 4), wsc(F.astr == "df")),
        )
        self.assertEqual(
            vwe((F.anum == 4) | (F.astr == "df"), [F]), or_(wsc(F.anum == 4), wsc(F.astr == "df"))
        )
        self.assertEqual(
            vwe((F.anum == 4) | ((F.astr == "df") & ~(F.atuple[0] < 2)), [F]),
            or_(wsc(F.anum == 4), and_(wsc(F.astr == "df"), not_(wsc(F.atuple[0] < 2)))),
        )

        f = lambda x: x + F.anum
        self.assertEqual(vwe(f, [F]), mfc([F], f))

        cond1 = (F.anum == 4) & f
        cond2 = and_(wsc(F.anum == 4), mfc([F], f))
        self.assertEqual(vwe(cond1, [F]), cond2)
        self.assertEqual(vwe(cond2, [F]), cond2)

        # Where expression with a membership operator
        # Comparison QConditions and raw functions are turned into Comparators
        seq = [1, 4]
        self.assertEqual(vwe(in_(F.anum, seq), [F]), wsc(in_(F.anum, seq)))

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_negate_where_expression(self):
        F = self.F
        G = self.G
        vwe = validate_where_expression
        nwe = negate_where_expression

        bf = vwe(func([F.anum], lambda x: x < 2), [F])
        nbf = bf.negate()

        self.assertEqual(nwe(nbf), bf)
        self.assertEqual(nwe(vwe(F.anum == 3, [F])), vwe(F.anum != 3, [F]))

        self.assertEqual(nwe(vwe(F.anum != 3, [F])), vwe(F.anum == 3, [F]))
        self.assertEqual(nwe(vwe(F.anum < 3, [F])), vwe(F.anum >= 3, [F]))
        self.assertEqual(nwe(vwe(F.anum <= 3, [F])), vwe(F.anum > 3, [F]))
        self.assertEqual(nwe(vwe(F.anum > 3, [F])), vwe(F.anum <= 3, [F]))
        self.assertEqual(nwe(vwe(F.anum >= 3, [F])), vwe(F.anum < 3, [F]))

        c = vwe((F.anum == 3) | (bf), [F])
        nc = vwe((F.anum != 3) & (nbf), [F])
        self.assertEqual(nwe(c), nc)
        self.assertEqual(nwe(nc), c)

        c = vwe(~(~(F.anum == 3) | ~(F.anum != 4)), [F])
        nc = vwe((F.anum != 3) | (F.anum == 4), [F])
        self.assertEqual(nwe(c), nc)

        # Negate contains/notcontains
        seq = [1, 2]
        c = vwe(in_(F.anum, seq), [F])
        nc = vwe(notin_(F.anum, seq), [F])
        self.assertEqual(nwe(c), nc)

    # ------------------------------------------------------------------------------
    # Test turning the where expression into NNF
    # ------------------------------------------------------------------------------
    def test_nonapi_where_expression_to_nnf(self):
        F = self.F
        vwe = validate_where_expression
        tonnf = where_expression_to_nnf

        c = vwe(~(~(F.anum == 3) | ~(F.anum == 4)), [F])
        nnfc = vwe((F.anum == 3) & (F.anum == 4), [F])
        self.assertEqual(tonnf(c), nnfc)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_where_expression_to_cnf(self):
        F = self.F
        vwe = validate_where_expression
        tocnf = where_expression_to_cnf

        # NOTE: Equality test relies on the order - to make this better would
        # need to introduce ordering over comparison conditions.

        f = vwe(((F.anum == 4) & (F.anum == 3)) | (F.anum == 6), [F])
        cnf = vwe(((F.anum == 4) | (F.anum == 6)) & ((F.anum == 3) | (F.anum == 6)), [F])
        self.assertEqual(tocnf(f), cnf)

        f = vwe((F.anum == 6) | ((F.anum == 4) & (F.anum == 3)), [F])
        cnf = vwe(((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3)), [F])
        self.assertEqual(tocnf(f), cnf)

        f = vwe(((F.anum == 6) & (F.anum == 5)) | ((F.anum == 4) & (F.anum == 3)), [F])
        cnf = vwe(
            (((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3)))
            & (((F.anum == 5) | (F.anum == 4)) & ((F.anum == 5) | (F.anum == 3))),
            [F],
        )
        self.assertEqual(tocnf(f), cnf)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_Clause(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        vwe = validate_where_expression
        wsc = StandardComparator.from_where_qcondition

        F = self.F
        G = self.G

        cx1 = Clause([wsc(F.anum == 4)])
        cx2 = Clause([wsc(F.anum == 4)])
        cx3 = Clause([wsc(F.anum == ph1_)])

        # Test __eq__ and __ne__
        self.assertEqual(cx1, cx2)
        self.assertNotEqual(cx1, cx3)

        c1 = Clause([wsc(F.anum == 4), wsc(F.astr == "b"), wsc(F.atuple[0] == 6)])

        # Test paths and ground
        self.assertEqual(hps([F.anum, F.astr, F.atuple[0]]), hps(c1.paths))
        self.assertEqual(hps(c1.roots), hps([F]))
        self.assertEqual(c1, c1.ground())

        c2 = Clause([wsc(F.anum == ph1_), wsc(F.astr == "b"), wsc(F.atuple[0] == 6)])
        self.assertEqual(hps([F.anum, F.astr, F.atuple[0]]), hps(c2.paths))
        self.assertEqual(c2.ground(4), c1)
        self.assertEqual(hps(c1.roots), hps([F]))

        f = FunctionComparator.from_specification([F.anum], lambda x: x == 2)
        c1 = Clause([f])

        self.assertEqual(hps(c1.paths), hps([F.anum]))
        self.assertEqual(hps(c1.roots), hps([F]))

        # Test dealiasing
        X = alias(F)
        c3 = Clause([wsc(F.anum == 4)])
        c4 = Clause([wsc(X.anum == 4)])
        self.assertNotEqual(c3, c4)
        self.assertEqual(c3, c4.dealias())

        # Test __len__, __getitem__ and __iter__
        cmp10 = wsc(F.anum == 4)
        cmp11 = wsc(X.anum == 4)
        c10 = Clause([cmp10, cmp11])
        self.assertEqual(len(c10), 2)
        self.assertEqual(list(c10), [cmp10, cmp11])
        self.assertEqual(c10[1], cmp11)

        # Test placeholders
        self.assertEqual(cx3.placeholders, set([ph1_]))
        fy = FunctionComparator.from_specification([F.anum], lambda x, y: x == y)
        self.assertEqual(Clause([fy]).placeholders, set([ph_("y")]))
        fy = FunctionComparator.from_specification([F.anum], lambda x, y=10: x == y)
        self.assertEqual(Clause([fy]).placeholders, set([ph_("y", 10)]))

        # Iterate over the conditions within a clause
        c1 = Clause([wsc(G.anum == ph1_), wsc(F.astr == "b"), wsc(F.atuple[0] == 6)])
        self.assertEqual(
            list(c1), [wsc(G.anum == ph1_), wsc(F.astr == "b"), wsc(F.atuple[0] == 6)]
        )

        # Test make_callable
        c1 = Clause([wsc(G.anum == ph1_), wsc(F.astr == "b")])
        cc = c1.ground(5).make_callable([F, G])

        f1 = F(1, "b", (2, "b"))
        f2 = F(3, "c", (4, "d"))
        g1 = G(4, "df")
        g2 = G(5, "df")
        self.assertTrue(cc((f1, g1)))
        self.assertTrue(cc((f2, g2)))
        self.assertTrue(cc((f1, g2)))
        self.assertFalse(cc((f2, g1)))

        # Test cannot make callable an ungrounded clause
        with self.assertRaises(TypeError) as ctx:
            cc = c1.make_callable([F, G])
        check_errmsg("Internal bug", ctx)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_ClauseBlock(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        vwe = validate_where_expression
        wsc = StandardComparator.from_where_qcondition

        F = self.F
        G = self.G
        X = alias(F)
        Y = alias(G)

        c1 = Clause([wsc(F.anum == 4), wsc(F.astr == "b")])
        c2 = Clause([wsc(X.anum == 5), wsc(X.astr == "c")])
        c3 = Clause([wsc(G.anum == 6)])
        c4 = Clause([wsc(G.anum == ph1_)])
        cb1 = ClauseBlock([c1, c2, c3])
        cb2 = ClauseBlock([c1, c2, c3])
        cb3 = ClauseBlock([c1, c2, c4])

        # Equality and inequlity
        self.assertEqual(cb1, cb2)
        self.assertNotEqual(cb2, cb3)

        # Test placeholders
        self.assertEqual(cb1.placeholders, set())

        #        cbt = ClauseBlock()
        self.assertEqual(hps([F.anum, F.astr, X.anum, X.astr, G.anum]), hps(cb1.paths))
        self.assertEqual(hps([F, X, G]), hps(cb1.roots))
        self.assertEqual(cb1.clauses, (c1, c2, c3))

        # Test dealiasing
        c10 = Clause([wsc(F.anum == 4)])
        c11 = Clause([wsc(X.anum == 4)])
        cb10 = ClauseBlock([c10])
        cb11 = ClauseBlock([c11])
        self.assertNotEqual(cb10, cb11)
        self.assertEqual(cb10, cb11.dealias())

        # Test __len__, __getitem__ and __iter__
        c10 = Clause([wsc(F.anum == 4)])
        c11 = Clause([wsc(X.anum == 4)])
        cb10 = ClauseBlock([c10, c11])
        self.assertEqual(len(cb10), 2)
        self.assertEqual(list(cb10), [c10, c11])
        self.assertEqual(cb10[1], c11)

        # Test the concatenation of clause blocks
        x1 = ClauseBlock([c1])
        x2 = ClauseBlock([c2])
        x3 = ClauseBlock([c1, c2])
        self.assertEqual(x1 + x2, x3)

        self.assertEqual(cb1.ground(), cb2)
        self.assertEqual(list(cb1), [c1, c2, c3])

        c1 = Clause([wsc(F.anum == ph1_)])
        c2 = Clause([wsc(G.anum == ph2_)])
        c1a = Clause([wsc(F.anum == 1)])
        c2b = Clause([wsc(G.anum == 2)])
        cb1 = ClauseBlock([c1, c2])
        cb2 = ClauseBlock([c1a, c2b])
        self.assertEqual(cb1.ground(1, 2), cb2)

        # Test placeholders
        self.assertEqual(cb1.placeholders, set([ph1_, ph2_]))

        testfunc = cb2.make_callable([F, G])
        #        trivialtrue = cbt.make_callable([F,G])
        f1 = F(1, "a", (2, "b"))
        f2 = F(2, "a", (2, "b"))
        g1 = G(2, "a")
        g2 = G(3, "a")

        self.assertFalse(testfunc((f1, g2)))
        self.assertFalse(testfunc((f2, g1)))
        self.assertFalse(testfunc((f2, g2)))
        self.assertTrue(testfunc((f1, g1)))

    #        self.assertTrue(trivialtrue((f1,g2)))
    #        self.assertTrue(trivialtrue((f2,g1)))
    #        self.assertTrue(trivialtrue((f2,g2)))
    #        self.assertTrue(trivialtrue((f1,g1)))

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_normalise_where_expression(self):
        F = alias(self.F)
        vwe = validate_where_expression
        tonorm = normalise_where_expression
        wsc = StandardComparator.from_where_qcondition

        # Simple cases containing a single clause block
        f = vwe(F.anum == 4, [F])
        #        self.assertEqual(tonorm(f), [ClauseBlock([Clause([f])])])
        self.assertEqual(tonorm(f), ClauseBlock([Clause([f])]))

        f = FunctionComparator.from_specification([F.anum], lambda x: x == 2)
        #        self.assertEqual(tonorm(f), [ClauseBlock([Clause([f])])])
        self.assertEqual(tonorm(f), ClauseBlock([Clause([f])]))

        f = vwe(((F.anum == 4) & (F.anum == 3)) | (F.anum == 6), [F])
        clauses = [
            Clause([wsc(F.anum == 4), wsc(F.anum == 6)]),
            Clause([wsc(F.anum == 3), wsc(F.anum == 6)]),
        ]
        norm = tonorm(f)
        self.assertEqual(tonorm(f), ClauseBlock(clauses))

        # More complex cases with multiple blocks
        G = alias(self.G)
        X = alias(F)
        Y = alias(G)

        f = vwe(
            and_(
                or_(F.anum == 4, F.astr == "b"),
                X.anum == 5,
                or_(X.anum == 6, Y.astr == "d"),
                X.astr == "a",
            ),
            [F, X, Y],
        )
        norm = tonorm(f)
        clauses = [
            Clause([wsc(F.anum == 4), wsc(F.astr == "b")]),
            Clause([wsc(X.anum == 5)]),
            Clause([wsc(X.anum == 6), wsc(Y.astr == "d")]),
            Clause([wsc(X.astr == "a")]),
        ]
        self.assertEqual(norm, ClauseBlock(clauses))

        # Normalise a negated expression where the negation is next to comparator
        f = vwe(~(F.anum == 4), [F])
        norm = tonorm(f)
        self.assertEqual(norm, ClauseBlock([Clause([wsc(F.anum != 4)])]))

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_partition_clauses(self):
        F = path(self.F)
        G = path(self.G)
        X = alias(F)
        Y = alias(G)
        wsc = StandardComparator.from_where_qcondition

        cf1 = Clause([wsc(F.anum == 4)])
        cx1 = Clause([wsc(X.anum == 5)])
        cbs, catchall = partition_clauses([cf1, cx1])
        self.assertEqual(cbs, [ClauseBlock([cf1]), ClauseBlock([cx1])])
        self.assertEqual(catchall, None)

        cf1 = Clause([wsc(F.anum == 4), wsc(F.astr == "b")])
        cx1 = Clause([wsc(X.anum == 5)])
        cx2 = Clause([wsc(X.astr == "a")])
        cxy1 = Clause([wsc(X.anum == 6), wsc(Y.astr == "d")])
        cbs, catchall = partition_clauses([cf1, cx1, cx2, cxy1])
        self.assertEqual(cbs, [ClauseBlock([cf1]), ClauseBlock([cx1, cx2])])
        self.assertEqual(catchall, ClauseBlock([cxy1]))


# ------------------------------------------------------------------------------
# Tests of manipulating/cleaning the query conditions
# ------------------------------------------------------------------------------


class JoinExpressionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

    # ------------------------------------------------------------------------------
    # Test validating a join expression (a list of join clauses)
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_join_expression(self):
        F = path(self.F)
        G = path(self.G)
        SC = StandardComparator
        vje = validate_join_expression
        joins = vje([F.anum == G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.eq, [F.anum, G.anum])])
        self.assertEqual(
            set(hpaths(SC(operator.eq, [F.anum, G.anum]).paths)), set(hpaths([F.anum, G.anum]))
        )
        self.assertEqual(
            set(hpaths(SC(operator.eq, [F.anum, G.anum]).roots)), set(hpaths([path(F), path(G)]))
        )
        self.assertEqual(
            hash(SC(operator.eq, [F.anum, G.anum])), hash(SC(operator.eq, [F.anum, G.anum]))
        )

        joins = vje([F.anum != G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.ne, [F.anum, G.anum])])

        joins = vje([F.anum < G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.lt, [F.anum, G.anum])])

        joins = vje([F.anum <= G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.le, [F.anum, G.anum])])

        joins = vje([F.anum > G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.gt, [F.anum, G.anum])])

        joins = vje([F.anum >= G.anum], [F, G])
        self.assertEqual(joins, [SC(operator.ge, [F.anum, G.anum])])

        joins = vje([cross(F, G)], [F, G])
        self.assertEqual(joins, [])

        # Bad specification that is not an operator
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum], [F])
        check_errmsg("Invalid join element", ctx)

        # Missing root path
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum <= G.anum], [F])
        check_errmsg("Join specification", ctx)

        # Only a single path
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum <= 1], [F, G])
        check_errmsg("Invalid join expression 'F.anum <= 1'", ctx)

        # Indentical argument
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == F.anum], [F, G])
        check_errmsg("Invalid join expression 'F.anum == F.anum'", ctx)

        # Bad cross-product specification
        with self.assertRaises(ValueError) as ctx:
            vje([cross(F.anum, G.anum)], [F, G])
        check_errmsg("Cross-product expression", ctx)

        X = alias(F)
        Y = alias(G)

        # A disconnected graph
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == G.anum, X.anum == Y.anum], [F, G, X, Y])
        check_errmsg("Invalid join specification: contains un-joined", ctx)

        Z = alias(G)
        # Missing base root
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == G.anum, X.anum == Y.anum], [F, G, X, Y, Z])
        check_errmsg("Invalid join specification: missing joins", ctx)

    # ------------------------------------------------------------------------------
    # Test validating a join expression connected by &
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_join_expression_with_ampersand(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        SC = StandardComparator
        vje = validate_join_expression
        tmp1 = SC(operator.eq, [F.anum, G.anum])
        tmp2 = SC(operator.eq, [F.anum, GA.anum])
        tmp3 = SC(operator.eq, [G.anum, FA.anum])

        joins = vje([(F.anum == G.anum) & (F.anum == GA.anum)], [F, G, GA])
        self.assertEqual([tmp1, tmp2], joins)

        joins = vje(
            [(F.anum == G.anum) & (F.anum == GA.anum) & (G.anum == FA.anum)], [F, G, GA, FA]
        )
        self.assertEqual([tmp1, tmp2, tmp3], joins)

        joins = vje(
            [(F.anum == G.anum) & ((F.anum == GA.anum) & (G.anum == FA.anum))], [F, G, GA, FA]
        )
        self.assertEqual([tmp1, tmp2, tmp3], joins)

        # Joining with a non-ampersand operator
        with self.assertRaises(ValueError) as ctx:
            vje([(F.anum == F.anum) | (F.anum == GA.anum)], [F, G, GA])
        check_errmsg("Invalid join ", ctx)


# ------------------------------------------------------------------------------
# Tests OrderBy, OrderByBlock, and related functions
# ------------------------------------------------------------------------------


class OrderByTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

    # ------------------------------------------------------------------------------
    # test the asc() and desc() functions produce valid specifications
    # ------------------------------------------------------------------------------
    def test_api_asc_desc(self):
        F = self.F

        self.assertEqual(asc(F.anum), OrderBy(path(F.anum), True))
        self.assertEqual(desc(F.anum), OrderBy(path(F.anum), False))
        self.assertEqual(asc(path(F)), OrderBy(path(F), True))
        self.assertEqual(desc(path(F)), OrderBy(path(F), False))
        self.assertEqual(asc(F), OrderBy(path(F), True))

    # ------------------------------------------------------------------------------
    # Test OrderBy
    # ------------------------------------------------------------------------------
    def test_nonapi_OrderBy_1d(self):
        F = self.F
        hp = hashable_path

        f1 = F(1, "a")
        f1cp = F(1, "a")
        f2 = F(2, "a")
        ob1 = OrderBy(F.anum, True)
        ob1cp = OrderBy(F.anum, True)
        ob2 = OrderBy(F.anum, False)
        ob3 = OrderBy(F.astr, True)

        self.assertEqual(hp(ob1.path), hp(F.anum))
        self.assertEqual(ob1.asc, True)
        self.assertEqual(ob2.asc, False)
        self.assertEqual(ob1, ob1cp)
        self.assertNotEqual(ob1, ob2)
        self.assertNotEqual(ob1, ob3)
        self.assertEqual(hash(ob1), hash(ob1cp))

    # ------------------------------------------------------------------------------
    # Test OrderByBlock
    # ------------------------------------------------------------------------------
    def test_nonapi_OrderByBlock(self):
        F = self.F
        G = self.G
        hp = hashable_path

        f1a = F(1, "a")
        f1b = F(1, "b")
        f2a = F(2, "a")
        f2b = F(2, "b")
        g1a = G(1, "a")
        g1b = G(1, "b")
        g2a = G(2, "a")
        g2b = G(2, "b")

        ob1 = OrderBy(F.anum, True)
        ob2 = OrderBy(F.astr, True)
        obb = OrderByBlock([ob1, ob2])
        obbcp = OrderByBlock([ob1, ob2])
        obb2 = OrderByBlock([ob2, ob1])

        self.assertEqual([hp(p) for p in obb.paths], [hp(F.anum), hp(F.astr)])
        self.assertEqual(set([hp(F)]), obb.roots)
        self.assertEqual([ob1, ob2], list(obb))
        self.assertEqual(len(obb), 2)
        self.assertEqual(obb[0], ob1)
        self.assertEqual(obb[1], ob2)
        self.assertEqual(obb, obbcp)
        self.assertNotEqual(obb, obb2)

    # ------------------------------------------------------------------------------
    # Test validating a join expression (a list of join clauses)
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_orderby_expression(self):
        F = self.F
        G = self.G
        FA = alias(F)
        vobe = validate_orderby_expression

        obb1 = vobe([F.anum, G.anum, desc(FA.anum)], [F, G, FA])
        obb2 = OrderByBlock(
            [OrderBy(F.anum, True), OrderBy(G.anum, True), OrderBy(FA.anum, False)]
        )
        self.assertEqual(obb1, obb2)

        # An order_by expression can also be a simple Predicate class
        Fpc = path(F).meta.predicate
        obb3 = vobe([Fpc], [Fpc])
        obb4 = OrderByBlock([OrderBy(path(F), True)])
        self.assertEqual(obb3, obb4)

        # Missing some roots
        with self.assertRaises(ValueError) as ctx:
            vobe([F.anum, G.anum, desc(FA.anum)], [F, G])
        check_errmsg("Invalid 'order_by'", ctx)


# ------------------------------------------------------------------------------
# Tests of manipulating/cleaning the query conditions
# ------------------------------------------------------------------------------


class QueryPlanTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = IntegerField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = IntegerField

        self.G = G

    # ------------------------------------------------------------------------------
    # Test generating the prejoin part of a JoinQueryPlan
    # ------------------------------------------------------------------------------

    def test_nonapi_make_prejoin_pair_simple(self):
        F = path(self.F)
        pw = process_where
        wsc = StandardComparator.from_where_qcondition

        clauses = pw((F.anum < 4) & (F.astr == "foo"), [F])
        (prejoinsc, prejoincb) = make_prejoin_pair([F.anum, F.astr], clauses)
        self.assertEqual(type(prejoincb), ClauseBlock)
        self.assertEqual(len(prejoincb), 1)
        self.assertEqual(type(prejoincb[0]), Clause)
        self.assertEqual(prejoinsc, Clause([wsc(F.astr == "foo")]))
        self.assertEqual(prejoincb, pw(F.anum < 4, [F]))

    def test_nonapi_make_prejoin_pair(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        pw = process_where
        pj = process_join
        wsc = StandardComparator.from_where_qcondition

        where = pw(
            (FA.anum < 4)
            & (FA.astr == "foo")
            & (FA.anum == FA.astr)
            & ((FA.anum > 10) | (FA.astr == "bar")),
            [FA],
        )

        where2 = pw(
            (FA.anum < 4) & (FA.anum == F.astr) & ((FA.anum > 10) | (FA.astr == "bar")), [FA, F]
        )
        (prejoinsc, prejoincb) = make_prejoin_pair([F.anum, F.astr], where)
        self.assertEqual(prejoinsc, Clause([wsc(FA.astr == "foo")]))
        self.assertEqual(len(prejoincb), len(where2))

        (prejoinsc, prejoincb) = make_prejoin_pair([F.anum], where)
        self.assertEqual(prejoinsc, Clause([wsc(FA.anum < 4)]))

        (prejoinsc, prejoincb) = make_prejoin_pair([], where)
        self.assertEqual(prejoinsc, None)
        self.assertEqual(prejoincb, where)

    # ------------------------------------------------------------------------------
    # Test generating the join components of a JoinQueryPlan
    # ------------------------------------------------------------------------------

    def test_nonapi_make_join_pair(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        wsc = StandardComparator.from_where_qcondition

        where = pw((FA.anum < G.anum) | ((FA.astr == "foo") & (FA.anum == FA.astr)), [FA, G])
        joins = pj([FA.anum == G.anum, G.anum > FA.anum], [FA, G])

        (joinsc, joincb) = make_join_pair(joins, where)
        self.assertEqual(joinsc, pj([FA.anum == G.anum], [FA, G])[0])
        self.assertEqual(len(joincb), len(where) + 1)

        (joinsc, joincb) = make_join_pair([], where)
        self.assertEqual(joinsc, None)
        self.assertEqual(len(joincb), len(where))

        (joinsc, joincb) = make_join_pair([], None)
        self.assertEqual(joinsc, None)
        self.assertEqual(joincb, None)

    # ------------------------------------------------------------------------------
    # Test the JoinQueryPlan class
    # ------------------------------------------------------------------------------

    def test_nonapi_JoinQueryPlan(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification

        joins = pj(
            [G.anum == FA.anum, FA.anum < GA.anum, cross(F, G), cross(G, FA)], [F, G, FA, GA]
        )
        joinsc = jsc(G.anum == F.anum)
        cl1 = Clause([wsc(F.anum == GA.anum)])
        cl2 = Clause([wsc(F.anum == 5)])
        cl3 = Clause([wsc(F.anum == ph1_)])

        clauses = pw((FA.anum < G.anum) | ((FA.astr == "foo") & (GA.anum == 4)), [FA, G, GA])
        qp1 = jqp([], (F, G, GA), FA, joins, clauses)

        self.assertEqual(hps(qp1.input_signature), hps((F, G, GA)))
        self.assertEqual(hps([qp1.root]), hps([FA]))
        self.assertEqual(qp1.prejoin_key_clause, None)
        self.assertEqual(qp1.join_key, jsc(FA.anum == G.anum))
        self.assertEqual(qp1.prejoin_clauses, None)

        clauses = pw((FA.anum < G.anum) & (FA.astr == "foo") & (FA.anum > 4), [FA, G])
        qp2 = jqp([F.astr], (F, G, GA), FA, joins, clauses)

        self.assertEqual(qp2.prejoin_key_clause, Clause([wsc(F.astr == "foo")]))
        self.assertEqual(qp2.prejoin_clauses, ClauseBlock([Clause([wsc(F.anum > 4)])]))
        self.assertEqual(qp2.join_key, jsc(FA.anum == G.anum))
        self.assertEqual(len(qp2.postjoin_clauses), 2)
        self.assertEqual(qp2.placeholders, set())

        clauses = pw((FA.anum < G.anum) & (FA.astr == ph1_) & (FA.anum > 4), [FA, G])
        qp3 = jqp([F.astr], (F, G, GA), FA, joins, clauses)
        self.assertEqual(qp3.prejoin_key_clause, Clause([wsc(F.astr == ph1_)]))
        self.assertEqual(qp3.placeholders, set([ph1_]))
        self.assertEqual(qp3.ground("foo"), qp2)

    # ------------------------------------------------------------------------------
    # Test the JoinQueryPlan class with a prejoin_key_clause that contains more
    # than one literal.
    # ------------------------------------------------------------------------------

    def test_nonapi_JoinQueryPlan_with_complex_prejoin_key_clause(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification

        joins = pj(
            [G.anum == FA.anum, FA.anum < GA.anum, cross(F, G), cross(G, FA)], [F, G, FA, GA]
        )
        joinsc = jsc(G.anum == F.anum)
        cl1 = Clause([wsc(F.anum == GA.anum)])
        cl2 = Clause([wsc(F.anum == 5)])
        cl3 = Clause([wsc(F.anum == ph1_)])

        clauses = pw((FA.anum < G.anum) & ((FA.astr == "foo") | (FA.anum == 4)), [FA, G])
        qp2 = jqp([F.astr, F.anum], (F, G, GA), FA, joins, clauses)

        self.assertEqual(qp2.prejoin_key_clause, Clause([wsc(F.astr == "foo"), wsc(F.anum == 4)]))
        self.assertEqual(qp2.prejoin_clauses, None)
        self.assertEqual(qp2.join_key, jsc(FA.anum == G.anum))
        self.assertEqual(len(qp2.postjoin_clauses), 2)
        self.assertEqual(qp2.placeholders, set())

    # ------------------------------------------------------------------------------
    # Test an example from with orderby -- SPECIAL CASE
    # ------------------------------------------------------------------------------

    def _test_nonapi_QueryPlan_with_orderby(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths])

        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        pob = process_orderby
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification
        mkq = make_query_plan
        indexes = [F.anum, G.astr]
        order_by = pob([asc(F.astr), desc(G.astr), desc(G.anum)], [F, G])
        qspec = QuerySpec(
            roots=[F, G], join=[], where=[], order_by=order_by, joh=basic_join_order
        )

        qplan = make_query_plan(indexes, qspec)
        self.assertEqual(qplan[0].prejoin_orderbys, [asc(F.astr)])
        self.assertEqual(qplan[1].prejoin_orderbys, [desc(G.astr), desc(G.anum)])

    # ------------------------------------------------------------------------------
    # Test the JoinQueryPlan class
    # ------------------------------------------------------------------------------

    def test_nonapi_QueryPlan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification

        joins1 = []
        joins2 = pj([G.anum == F.anum], [F, G])
        joins3 = pj([G.anum == F.anum, F.anum < FA.anum], [F, G, FA])

        c1 = pw(F.anum == 5, [F])
        c1ph = pw(F.anum == ph1_, [F])
        c2 = pw(F.astr == G.astr, [F, G])

        qpj1 = JoinQueryPlan((), F, [], None, c1, None, None, None, None)
        qpj1ph = JoinQueryPlan((), F, [], None, c1ph, None, None, None, None)

        qp1 = QueryPlan([qpj1])
        qp1ph = QueryPlan([qpj1ph])
        self.assertEqual(len(qp1), 1)
        self.assertEqual(qp1[0], qpj1)
        self.assertNotEqual(qp1, qp1ph)
        self.assertEqual(qp1, qp1ph.ground(5))

        qpj2 = JoinQueryPlan((F,), G, [], None, None, None, jsc(G.anum == F.anum), c2, None)
        qpj3 = JoinQueryPlan((F, G), FA, [], None, None, None, jsc(G.anum == FA.anum), None, None)

        qp2 = QueryPlan([qpj1, qpj2])
        self.assertEqual(len(qp2), 2)
        self.assertEqual(qp2[0], qpj1)
        self.assertEqual(qp2[1], qpj2)

        qp3 = QueryPlan([qpj1, qpj2, qpj3])
        qp3ph = QueryPlan([qpj1ph, qpj2, qpj3])
        self.assertEqual(list(qp3), [qpj1, qpj2, qpj3])
        self.assertEqual(len(qp3), 3)
        self.assertNotEqual(qp3, qp3ph)
        self.assertEqual(qp3, qp3ph.ground(5))

        self.assertEqual(qp3.output_signature, tuple(qpj3.input_signature + (qpj3.root,)))

        # Test placeholders
        self.assertEqual(qp3.placeholders, set())
        self.assertEqual(qp3ph.placeholders, set([ph1_]))
        self.assertEqual(qp3ph.ground(4).placeholders, set())

        # Bad query plans
        with self.assertRaises(ValueError) as ctx:
            qp = QueryPlan([qpj2])
        check_errmsg("Invalid 'input_signature'", ctx)
        with self.assertRaises(ValueError) as ctx:
            qp = QueryPlan([qpj2, qpj1, qpj3])
        check_errmsg("Invalid 'input_signature'", ctx)

    # ------------------------------------------------------------------------------
    # Test associating orderby statements with root_join_order blocks
    # ------------------------------------------------------------------------------

    def test_nonapi_partition_orderbys(self):
        class P(Predicate):
            anum = IntegerField
            astr = StringField

        class F(Predicate):
            anum = IntegerField
            astr = StringField

        PA = alias(P)
        pob = process_orderby
        OBB = OrderByBlock
        orderbys = [asc(P.anum), asc(PA.anum)]

        self.assertEqual(
            partition_orderbys([P, PA, F], orderbys), [[asc(P.anum)], [asc(PA.anum)], []]
        )

        self.assertEqual(
            partition_orderbys([P, F, PA], orderbys), [[], [asc(P.anum)], [asc(PA.anum)]]
        )

        self.assertEqual(
            partition_orderbys([F, P, PA], orderbys), [[], [asc(P.anum)], [asc(PA.anum)]]
        )

        self.assertEqual(
            partition_orderbys([F, PA, P], orderbys), [[], [], [asc(P.anum), asc(PA.anum)]]
        )

        self.assertEqual(
            partition_orderbys([PA, P, F], orderbys), [[], [asc(P.anum), asc(PA.anum)], []]
        )

        self.assertEqual(
            partition_orderbys([PA, F, P], orderbys), [[], [], [asc(P.anum), asc(PA.anum)]]
        )

        orderbys = [asc(P.anum)]

        self.assertEqual(partition_orderbys([P, PA, F], orderbys), [[asc(P.anum)], [], []])

        self.assertEqual(partition_orderbys([P, F, PA], orderbys), [[asc(P.anum)], [], []])

        self.assertEqual(partition_orderbys([F, P, PA], orderbys), [[], [asc(P.anum)], []])

        self.assertEqual(partition_orderbys([F, PA, P], orderbys), [[], [], [asc(P.anum)]])

        self.assertEqual(
            partition_orderbys([PA, P, F], orderbys),
            [
                [],
                [
                    asc(P.anum),
                ],
                [],
            ],
        )

        self.assertEqual(partition_orderbys([PA, F, P], orderbys), [[], [], [asc(P.anum)]])

        orderbys = [asc(P.anum), asc(F.anum)]
        self.assertEqual(partition_orderbys([P, F], orderbys), [[asc(P.anum)], [asc(F.anum)]])

        self.assertEqual(partition_orderbys([F, P], orderbys), [[], [asc(P.anum), asc(F.anum)]])

        orderbys = [asc(P.anum), asc(P.astr)]
        self.assertEqual(partition_orderbys([P, F], orderbys), [[asc(P.anum), asc(P.astr)], []])

        orderbys = [asc(P.anum), asc(P.astr)]
        self.assertEqual(partition_orderbys([F, P], orderbys), [[], [asc(P.anum), asc(P.astr)]])

        orderbys = [asc(F.astr), desc(P.astr), asc(P.anum)]
        self.assertEqual(
            partition_orderbys([F, P], orderbys), [[asc(F.astr)], [desc(P.astr), asc(P.anum)]]
        )

        self.assertEqual(
            partition_orderbys([P, F], orderbys), [[], [asc(F.astr), desc(P.astr), asc(P.anum)]]
        )

    # ------------------------------------------------------------------------------
    # Test geneating the query plan when give the root join order, the joins,
    # and the where clauses.
    # ------------------------------------------------------------------------------

    def test_nonapi_make_query_plan_preordered_roots(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        pob = process_orderby
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification
        hp = hashable_path

        joins = pj([G.anum == F.anum, F.anum < GA.anum, cross(G, FA)], [F, G, FA, GA])
        where = pw((F.anum == 4) & (FA.anum < 2), [F, FA])
        orderbys = pob([GA.anum, FA.anum, F.anum, G.anum], [F, G, FA, GA])

        qspec = QuerySpec(roots=[FA, GA, G, F], join=joins, where=where, order_by=orderbys)
        qp1 = make_query_plan_preordered_roots([F.anum], [FA, GA, G, F], qspec)

        self.assertEqual(len(qp1), 4)
        self.assertEqual(hp(qp1[0].root), hp(FA))
        self.assertEqual(hp(qp1[1].root), hp(GA))
        self.assertEqual(hp(qp1[2].root), hp(G))
        self.assertEqual(hp(qp1[3].root), hp(F))

        self.assertEqual(qp1[0].prejoin_key_clause, Clause([wsc(F.anum < 2)]))
        self.assertEqual(qp1[1].prejoin_key_clause, None)
        self.assertEqual(qp1[2].prejoin_key_clause, None)
        self.assertEqual(qp1[3].prejoin_key_clause, Clause([wsc(F.anum == 4)]))

        self.assertEqual(qp1[0].prejoin_clauses, None)
        self.assertEqual(qp1[1].prejoin_clauses, None)
        self.assertEqual(qp1[2].prejoin_clauses, None)
        self.assertEqual(qp1[3].prejoin_clauses, None)

        self.assertEqual(qp1[0].join_key, None)
        self.assertEqual(qp1[1].join_key, None)
        self.assertEqual(qp1[2].join_key, None)
        self.assertEqual(qp1[3].join_key, jsc(F.anum == G.anum))

        self.assertEqual(qp1[0].postjoin_clauses, None)
        self.assertEqual(qp1[1].postjoin_clauses, None)
        self.assertEqual(qp1[2].postjoin_clauses, None)
        self.assertEqual(list(qp1[3].postjoin_clauses), [Clause([wsc(F.anum < GA.anum)])])

        self.assertEqual(qp1[0].postjoin_orderbys, None)
        self.assertEqual(qp1[1].postjoin_orderbys, None)
        self.assertEqual(qp1[2].postjoin_orderbys, None)
        self.assertEqual(
            qp1[3].postjoin_orderbys,
            OrderByBlock([asc(GA.anum), asc(FA.anum), asc(F.anum), asc(G.anum)]),
        )

        # Same as qp1 but with placeholder - so equal after grounding
        where2 = pw((F.anum == ph1_) & (FA.anum < ph2_), [F, FA])
        qspec = QuerySpec(roots=[FA, GA, G, F], join=joins, where=where2, order_by=orderbys)
        qp2 = make_query_plan_preordered_roots([F.anum], [FA, GA, G, F], qspec)
        self.assertEqual(qp2.placeholders, set([ph1_, ph2_]))

        self.assertEqual(qp2[0].prejoin_key_clause, Clause([wsc(F.anum < ph2_)]))
        self.assertEqual(qp2[1].prejoin_key_clause, None)
        self.assertEqual(qp2[2].prejoin_key_clause, None)
        self.assertEqual(qp2[3].prejoin_key_clause, Clause([wsc(F.anum == ph1_)]))
        self.assertNotEqual(qp1, qp2)
        self.assertEqual(qp1.ground(4, 2), qp1)
        self.assertEqual(qp2.ground(4, 2), qp1)

        # Same as qp1 but different root ordering
        qspec = QuerySpec(roots=[FA, GA, G, F], join=joins, where=where, order_by=orderbys)
        qp3 = make_query_plan_preordered_roots([F.anum], [FA, GA, F, G], qspec)
        self.assertEqual(len(qp3), 4)
        self.assertEqual(hp(qp3[0].root), hp(FA))
        self.assertEqual(hp(qp3[1].root), hp(GA))
        self.assertEqual(hp(qp3[2].root), hp(F))
        self.assertEqual(hp(qp3[3].root), hp(G))

        self.assertEqual(qp3[0].prejoin_key_clause, Clause([wsc(F.anum < 2)]))
        self.assertEqual(qp3[1].prejoin_key_clause, None)
        self.assertEqual(qp3[2].prejoin_key_clause, Clause([wsc(F.anum == 4)]))
        self.assertEqual(qp3[3].prejoin_key_clause, None)

        self.assertEqual(qp3[0].join_key, None)
        self.assertEqual(qp3[1].join_key, None)
        self.assertEqual(qp3[2].join_key, jsc(F.anum < GA.anum))
        self.assertEqual(qp3[3].join_key, jsc(G.anum == F.anum))

        self.assertEqual(qp3[0].postjoin_clauses, None)
        self.assertEqual(qp3[1].postjoin_clauses, None)
        self.assertEqual(qp3[2].postjoin_clauses, None)
        self.assertEqual(qp3[3].postjoin_clauses, None)

    # ------------------------------------------------------------------------------
    # Test the operator preference heuristic for generating the join order
    # ------------------------------------------------------------------------------
    def test_nonapi_oppref_join_order(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        pj = process_join

        joins = pj([F.anum == G.anum, F.anum < GA.anum, cross(G, FA)], [F, G, FA, GA])
        qspec = QuerySpec(roots=[F, G, FA, GA], join=joins, where=[], order_by=[])
        qorder = oppref_join_order([], qspec)
        self.assertEqual(qorder, [F, G, GA, FA])

    # ------------------------------------------------------------------------------
    # Test the basic heuristic for generating the join order
    # ------------------------------------------------------------------------------
    def test_nonapi_basic_join_order(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        qspec = QuerySpec(roots=[F, G, FA, GA], join=[], where=[], order_by=[])
        qorder = basic_join_order([], qspec)
        self.assertEqual(qorder, [F, G, FA, GA])

    # ------------------------------------------------------------------------------
    # Test the fixed join order heuristic generator
    # ------------------------------------------------------------------------------
    def test_nonapi_fixed_join_order(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        qspec = QuerySpec(roots=[F, G, FA, GA], join=[], where=[], order_by=[])

        qorder = fixed_join_order(F, G, FA, GA)([], qspec)
        self.assertEqual(qorder, [F, G, FA, GA])

        qorder = fixed_join_order(G, F, FA, GA)([], qspec)
        self.assertEqual(qorder, [G, F, FA, GA])

        qorder = fixed_join_order(GA, FA, F, G)([], qspec)
        self.assertEqual(qorder, [GA, FA, F, G])

        # Detect creation of bad heuristics
        with self.assertRaises(ValueError) as ctx:
            qorder = fixed_join_order(F, G)([], qspec)
        check_errmsg("Mis-matched query roots: fixed join", ctx)

        with self.assertRaises(ValueError) as ctx:
            qorder = fixed_join_order(F.anum, G)([], qspec)
        check_errmsg("Bad query roots specification", ctx)

        with self.assertRaises(ValueError) as ctx:
            qorder = fixed_join_order()
        check_errmsg("Missing query roots", ctx)

    # ------------------------------------------------------------------------------
    # Test making a plan from joins and whereclauses
    # ------------------------------------------------------------------------------
    def test_make_query_plan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)

        pw = process_where
        pj = process_join
        pob = process_orderby
        wsc = StandardComparator.from_where_qcondition
        jsc = StandardComparator.from_join_qcondition
        jqp = JoinQueryPlan.from_specification
        hp = hashable_path

        joins = pj([G.anum == F.anum, F.anum < GA.anum, cross(G, FA)], [F, G, FA, GA])
        where = pw((F.anum == 4) & (FA.anum < 2), [F, FA])
        orderbys = pob([FA.anum, G.anum], [FA, G])
        qspec = QuerySpec(roots=[F, G, FA, GA], join=joins, where=where, order_by=orderbys)
        qp1 = make_query_plan([F.anum], qspec)
        self.assertEqual(len(qp1), 4)

    # ------------------------------------------------------------------------------
    # Test the plan with a membership operator in the key
    # ------------------------------------------------------------------------------
    def test_make_query_plan_membership(self):
        F = path(self.F)

        pw = process_where
        pob = process_orderby
        wsc = StandardComparator.from_where_qcondition
        jqp = JoinQueryPlan.from_specification
        hp = hashable_path

        seq = [3, 4]
        wherein = pw(in_(F.anum, seq), [F])
        wherenotin1 = pw(~in_(F.anum, seq), [F])
        wherenotin2 = pw(notin_(F.anum, seq), [F])

        qspec = QuerySpec(roots=[F], where=wherein)
        qp = make_query_plan([F.anum], qspec)
        self.assertEqual(len(qp), 1)
        self.assertEqual(qp[0].prejoin_key_clause, wherein[0])

        qspec = QuerySpec(roots=[F], where=wherenotin1)
        qp = make_query_plan([F.anum], qspec)
        self.assertEqual(len(qp), 1)
        self.assertEqual(qp[0].prejoin_key_clause, wherenotin1[0])
        self.assertEqual(qp[0].prejoin_key_clause, wherenotin2[0])

    # ------------------------------------------------------------------------------
    #
    # ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# InQuerySorterTest. Test functions for the underlying query mechanism
# ------------------------------------------------------------------------------


class InQuerySorterTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

        self.factsets = {}
        self.indexes = {}

        factset = FactSet()
        factindex = FactIndex(G.astr)
        for f in [G(1, "a"), G(1, "foo"), G(5, "a"), G(5, "foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(G.astr)] = factindex
        self.factsets[G] = factset

        factset = FactSet()
        factindex = FactIndex(F.anum)
        for f in [F(1, "a"), F(1, "foo"), F(5, "a"), F(5, "foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(F.anum)] = factindex
        self.factsets[F] = factset

    def test_InQuerySorter_bad(self):
        F = self.F
        G = self.G
        factsetF = self.factsets[F]
        roots = [F]
        pob = process_orderby

        with self.assertRaises(ValueError) as ctx:
            orderby = pob([desc(F.astr), G.anum], [F, G])
            iqs = InQuerySorter(orderby)
        check_errmsg("Cannot create an InQuerySorter", ctx)

        with self.assertRaises(AttributeError) as ctx:
            iqs = InQuerySorter([])
        check_errmsg("'list' object has no attribute", ctx)

    def test_InQuerySorter_singlefacts(self):
        F = self.F
        factsetF = self.factsets[F]
        roots = [F]
        pob = process_orderby

        # Ascending order sorting in-place as well as generating a new list
        orderby = pob([F.astr], roots)
        iqs = InQuerySorter(orderby)
        inlistF = list(factsetF)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)

        self.assertEqual(len(inlistF), 4)
        self.assertEqual(len(outlistF), 4)
        self.assertEqual(inlistF[0].astr, "a")
        self.assertEqual(outlistF[0].astr, "a")
        self.assertEqual(inlistF[1].astr, "a")
        self.assertEqual(outlistF[1].astr, "a")
        self.assertEqual(inlistF[2].astr, "foo")
        self.assertEqual(outlistF[2].astr, "foo")
        self.assertEqual(inlistF[3].astr, "foo")
        self.assertEqual(outlistF[3].astr, "foo")

        # Descending order sorting
        orderby = pob([desc(F.astr)], roots)
        iqs = InQuerySorter(orderby)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)

        self.assertEqual(len(outlistF), 4)
        self.assertEqual(outlistF[0].astr, "foo")
        self.assertEqual(outlistF[1].astr, "foo")
        self.assertEqual(outlistF[2].astr, "a")
        self.assertEqual(outlistF[3].astr, "a")

        # Multiple criteria sort
        orderby = pob([desc(F.astr), F.anum], roots)
        iqs = InQuerySorter(orderby)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)
        self.assertEqual(
            outlistF,
            [
                F(1, "foo"),
                F(5, "foo"),
                F(1, "a"),
                F(5, "a"),
            ],
        )

    def test_InQuerySorter_facttuples(self):
        F = self.F
        G = self.G
        factsetF = self.factsets[F]
        factsetG = self.factsets[G]
        roots = [F, G]
        pob = process_orderby
        cp = []
        for f in factsetF:
            for g in factsetG:
                cp.append((f, g))

        orderby = pob([desc(F.anum), G.anum, desc(F.astr), desc(G.astr)], roots)
        iqs = InQuerySorter(orderby, roots)
        outlistF = iqs.sorted(cp)

        expected = [
            (F(5, "foo"), G(1, "foo")),
            (F(5, "foo"), G(1, "a")),
            (F(5, "a"), G(1, "foo")),
            (F(5, "a"), G(1, "a")),
            (F(5, "foo"), G(5, "foo")),
            (F(5, "foo"), G(5, "a")),
            (F(5, "a"), G(5, "foo")),
            (F(5, "a"), G(5, "a")),
            (F(1, "foo"), G(1, "foo")),
            (F(1, "foo"), G(1, "a")),
            (F(1, "a"), G(1, "foo")),
            (F(1, "a"), G(1, "a")),
            (F(1, "foo"), G(5, "foo")),
            (F(1, "foo"), G(5, "a")),
            (F(1, "a"), G(5, "foo")),
            (F(1, "a"), G(5, "a")),
        ]
        self.assertEqual(outlistF, expected)


# ------------------------------------------------------------------------------
# QueryTest. Test functions for the underlying query mechanism
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# support function to take a list of fact tuples transforms the order of facts
# based on the signature transform
# ------------------------------------------------------------------------------


def align_facts(insig, outsig, it):
    insig = tuple([path(a) for a in insig])
    outsig = tuple([path(a) for a in outsig])
    f = make_input_alignment_functor(insig, outsig)
    return [f(t) for t in it]


class QueryTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

        self.factsets = {}
        self.indexes = {}

        factset = FactSet()
        factindex = FactIndex(G.astr)
        for f in [G(1, "a"), G(1, "foo"), G(5, "a"), G(5, "foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(G.astr)] = factindex
        self.factsets[G] = factset

        factset = FactSet()
        factindex = FactIndex(F.anum)
        for f in [F(1, "a"), F(1, "foo"), F(5, "a"), F(5, "foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(F.anum)] = factindex
        self.factsets[F] = factset

    # ------------------------------------------------------------------------------
    # Test generating the prejoin query source function
    # ------------------------------------------------------------------------------

    def test_nonapi_make_prejoin_query_source(self):
        F = self.F
        G = self.G
        indexes = self.indexes
        factsets = self.factsets
        pw = process_where
        pj = process_join
        pob = process_orderby
        roots = [F, G]
        bjoh = basic_join_order
        bjoh = oppref_join_order

        # Simplest case. Nothing specified so pass through the factset
        qspec = QuerySpec(roots=roots, join=[], where=[], order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(out is factsets[G])

        # A prejoin key but nothing else
        where = pw(G.astr == "foo", roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(set(out), set([G(1, "foo"), G(5, "foo")]))

        # A prejoin clause but nothing else
        where = pw(G.anum == 1, roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(set(out), set([G(1, "a"), G(1, "foo")]))

        # Both a prejoin key and a prejoin clause
        where = pw((G.anum == 1) & (G.astr == "foo"), roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(set(out), set([G(1, "foo")]))

        # A prejoin key with no join and a single ascending order matching an index
        where = pw(G.astr == "foo", roots)
        orderby = pob([F.astr, asc(G.astr)], roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(out[0].astr, "foo")
        self.assertEqual(out[1].astr, "foo")
        self.assertEqual(len(out), 2)

        # A prejoin key with no join and a single desc order matching an index
        where = pw(G.astr == "foo", roots)
        orderby = pob([F.astr, desc(G.astr)], roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(out[0].astr, "foo")
        self.assertEqual(out[1].astr, "foo")
        self.assertEqual(len(out), 2)

        # A prejoin key with no join and a complex order
        where = pw(G.astr == "foo", roots)
        orderby = pob([F.astr, desc(G.astr), G.anum], roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)

        out0 = make_prejoin_query_source(qp[0], factsets, indexes)()
        out1 = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertEqual(set([F(1, "a"), F(1, "foo"), F(5, "a"), F(5, "foo")]), set(out0))
        self.assertEqual(set(out1), set([G(1, "foo"), G(5, "foo")]))

        # A prejoin key with no join and non index matching sort
        where = pw(G.astr == "foo", roots)
        orderby = pob([F.astr, desc(G.anum)], roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, list))
        self.assertEqual(set(out), set([G(5, "foo"), G(1, "foo")]))

        # A join key that matches an existing index but nothing else
        join = pj([F.astr == G.astr], roots)
        qspec = QuerySpec(roots=roots, join=join, where=[], order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(out is indexes[hashable_path(G.astr)])

        # A join key that doesn't match an existing index - and nothing else
        join = pj([F.anum == G.anum], roots)
        qspec = QuerySpec(roots=roots, join=join, where=[], order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.anum))
        self.assertEqual(set(out), set(factsets[G]))

        # A join key and a prejoin key
        join = pj([F.astr == G.astr], roots)
        where = pw(G.astr == "foo", roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.astr))
        self.assertEqual(set(out), set([G(1, "foo"), G(5, "foo")]))

        # A join key and a prejoin clause
        join = pj([F.astr == G.astr], roots)
        where = pw(G.anum == 1, roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out, FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.astr))
        self.assertEqual(set(out), set([G(1, "a"), G(1, "foo")]))

    # ------------------------------------------------------------------------------
    # Test generating the prejoin query source function
    # ------------------------------------------------------------------------------

    def test_nonapi_make_chained_join_query(self):
        F = self.F
        G = self.G
        indexes = self.indexes
        factsets = self.factsets
        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        roots = [F, G]

        #        orderby = pob([F.astr,desc(G.anum)],roots)

        # Simplest case. No join or no G-where clauses.
        # (Note: the where clause for F is to simplify to only one join).
        where = pw((F.anum == 1) & (F.astr == "foo"), roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(
            set(query),
            set(
                [
                    (F(1, "foo"), G(1, "a")),
                    (F(1, "foo"), G(1, "foo")),
                    (F(1, "foo"), G(5, "a")),
                    (F(1, "foo"), G(5, "foo")),
                ]
            ),
        )

        # No join but a prejoin where clause
        where = pw(((F.anum == 1) & (F.astr == "foo")) & (G.anum == 1), roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query), set([(F(1, "foo"), G(1, "a")), (F(1, "foo"), G(1, "foo"))]))

        # No join but a post-join where clause - by adding useless extra F
        where = pw(((F.anum == 1) & (F.astr == "foo")) & ((G.anum == 1) | (F.anum == 5)), roots)
        qspec = QuerySpec(roots=roots, join=[], where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query), set([(F(1, "foo"), G(1, "a")), (F(1, "foo"), G(1, "foo"))]))

        # A join key but nothing else
        join = pj([F.astr == G.astr], roots)
        where = pw((F.anum == 1) & (F.astr == "foo"), roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=[], joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(
            set(query), set([(F(1, "foo"), G(1, "foo")), (F(1, "foo"), G(5, "foo"))])
        )

        # A join key and a prejoin-sort
        join = pj([F.astr == G.astr], roots)
        where = pw((F.anum == 1) & (F.astr == "foo"), roots)
        orderby = pob([F.astr, desc(G.anum)], roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(
            set(query), set([(F(1, "foo"), G(5, "foo")), (F(1, "foo"), G(1, "foo"))])
        )

        # FIXUP
        # A join key and a prejoin-sort where they are different keys and the
        # sort is on the second predicate. Ignoring the indexes
        join = pj([F.anum == G.anum], roots)
        #        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        orderby = pob([G.astr, G.anum], roots)
        qspec = QuerySpec(roots=roots, join=join, order_by=orderby, joh=bjoh)
        qp = make_query_plan([], qspec)
        inquery = make_first_join_query(qp[0], factsets, {})
        query = make_chained_join_query(qp[1], inquery, factsets, {})()
        result = list(query)
        expected = [
            (F(1, "a"), G(1, "a")),
            (F(1, "foo"), G(1, "a")),
            (F(5, "a"), G(5, "a")),
            (F(5, "foo"), G(5, "a")),
            (F(1, "a"), G(1, "foo")),
            (F(1, "foo"), G(1, "foo")),
            (F(5, "a"), G(5, "foo")),
            (F(5, "foo"), G(5, "foo")),
        ]
        self.assertEqual(result, expected)

        # A join key and a post join-sort
        join = pj([F.astr == G.astr], roots)
        where = pw((F.anum == 1) & (F.astr == "foo"), roots)
        orderby = pob([desc(G.anum)], roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(
            set(query), set([(F(1, "foo"), G(5, "foo")), (F(1, "foo"), G(1, "foo"))])
        )

        # A join key and a complex post join sort
        join = pj([F.astr == G.astr], roots)
        where = pw((F.anum == 1) & (F.astr == "foo"), roots)
        orderby = pob([desc(G.anum), F.anum, G.astr], roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=orderby, joh=bjoh)
        qp = make_query_plan(indexes.keys(), qspec)

        inquery = make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(
            set(query), set([(F(1, "foo"), G(5, "foo")), (F(1, "foo"), G(1, "foo"))])
        )

    # --------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    # --------------------------------------------------------------------------
    def test_make_first_prejoin_query(self):
        def strip(it):
            return [f for f, in it]

        G = self.G
        pw = process_where
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.astr == "foo"), [G])
        qspec1 = QuerySpec(roots=[G], join=[], where=which1, order_by=[], joh=bjoh)
        qp1 = make_query_plan([G.astr], qspec1)
        q1 = make_first_prejoin_query(qp1[0], factsets, indexes)
        self.assertEqual(set([f for (f,) in q1()]), set([G(1, "foo"), G(5, "foo")]))

        which2 = pw((G.astr == "foo") | (G.astr == "a"), [G])
        qspec2 = QuerySpec(roots=[G], join=[], where=which2, order_by=[], joh=bjoh)
        qp2 = make_query_plan([G.astr], qspec2)
        q2 = make_first_prejoin_query(qp2[0], factsets, indexes)
        self.assertEqual(
            set([f for (f,) in q2()]), set([G(1, "foo"), G(5, "foo"), G(1, "a"), G(5, "a")])
        )

    # --------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    # --------------------------------------------------------------------------
    def test_make_first_join_query(self):
        def strip(it):
            return [f for f, in it]

        G = self.G
        pw = process_where
        pob = process_orderby
        bjoh = oppref_join_order
        bjoh = basic_join_order

        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.anum > 4) & (G.astr == "foo"), [G])
        orderbys = pob([G.anum, desc(G.astr)], [G])
        qspec = QuerySpec(roots=[G], join=[], where=which1, order_by=orderbys, joh=bjoh)
        qp1 = make_query_plan([G.astr], qspec)

        query1 = make_first_join_query(qp1[0], factsets, indexes)
        self.assertEqual(set(strip(query1())), set([G(5, "foo")]))

        which2 = pw((G.anum > 4) | (G.astr == "foo"), [G])
        qspec = QuerySpec(roots=[G], join=[], where=which2, order_by=orderbys, joh=bjoh)
        qp2 = make_query_plan([G.astr], qspec)

        query2 = make_first_join_query(qp2[0], factsets, indexes)
        self.assertEqual(list(strip(query2())), [G(1, "foo"), G(5, "foo"), G(5, "a")])

    # --------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    # --------------------------------------------------------------------------
    def test_make_query(self):
        F = self.F
        G = self.G
        indexes = self.indexes
        factsets = self.factsets
        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = oppref_join_order
        bjoh = basic_join_order
        roots = [F, G]

        joins1 = pj([F.anum == G.anum], roots)
        which1 = pw((G.anum > 4) | (F.astr == "foo"), roots)
        orderbys = pob([desc(G.anum), F.astr, desc(G.astr)], roots)
        qspec = QuerySpec(roots=roots, join=joins1, where=which1, order_by=orderbys, joh=bjoh)
        qp1 = make_query_plan(indexes.keys(), qspec)
        q1 = make_query(qp1, factsets, indexes)
        result = list(q1())
        expected = [
            (F(5, "a"), G(5, "foo")),
            (F(5, "a"), G(5, "a")),
            (F(5, "foo"), G(5, "foo")),
            (F(5, "foo"), G(5, "a")),
            (F(1, "foo"), G(1, "foo")),
            (F(1, "foo"), G(1, "a")),
        ]
        self.assertEqual(expected, result)

        # Ungrounded query
        joins2 = pj([F.anum == G.anum], roots)
        which2 = pw((G.anum > 4) | (F.astr == ph1_), roots)
        orderbys2 = pob([desc(G.anum), F.astr, desc(G.astr)], roots)
        qspec = QuerySpec(roots=roots, join=joins2, where=which2, order_by=orderbys2, joh=bjoh)
        qp2 = make_query_plan(indexes.keys(), qspec)
        with self.assertRaises(ValueError) as ctx:
            q1 = make_query(qp2, factsets, indexes)
        check_errmsg("Cannot execute an ungrounded query", ctx)

    # --------------------------------------------------------------------------
    # Test making a query containing a sorting based on an attribute of the
    # second root predicate (where the join between the two predicates is
    # through a different attribute).
    # --------------------------------------------------------------------------
    def test_nonapi_make_query_sort_order(self):
        class F(Predicate):
            anum = IntegerField

        class G(Predicate):
            anum = IntegerField
            astr = StringField
            aval = IntegerField

        factsets = {}
        factsets[G] = FactSet(
            [G(1, "a", 5), G(1, "b", 4), G(2, "a", 6), G(2, "b", 7), G(3, "a", 1), G(3, "b", 8)]
        )
        factsets[F] = FactSet([F(1), F(2)])

        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        roots = [F, G]

        joins1 = pj([F.anum == G.anum], roots)
        orderbys = pob([G.astr, G.anum], roots)
        qspec = QuerySpec(roots=roots, join=joins1, order_by=orderbys, joh=bjoh)
        qp = make_query_plan([], qspec)
        query = make_query(qp, factsets, {})
        result = list(query())
        expected = [
            (F(1), G(1, "a", 5)),
            (F(2), G(2, "a", 6)),
            (F(1), G(1, "b", 4)),
            (F(2), G(2, "b", 7)),
        ]
        self.assertEqual(expected, result)


# ------------------------------------------------------------------------------
# Helper function for QueryExecutor testing
# ------------------------------------------------------------------------------
def factmaps_to_factsets(factmaps):
    return {ptype: fm.factset for ptype, fm in factmaps.items()}


def f_in_factmaps(f, factmaps):
    fm = factmaps.get(type(f), factmaps)
    if not fm:
        return False
    return f in fm.factset


def factmaps_dict(facts, indexes=None):
    from itertools import groupby

    if indexes is None:
        indexes = []
    indexes = sorted([hashable_path(p) for p in indexes])
    predicate2indexes = {}
    for k, g in groupby(indexes, lambda p: path(p).meta.predicate):
        predicate2indexes[k] = list(g)

    factmaps = {}
    keyfunc = lambda fact: hashable_path(type(fact))
    facts = sorted(facts, key=keyfunc)
    for pp, g in groupby(facts, keyfunc):
        predicate = path(pp).meta.predicate
        indexes = [path(p) for p in predicate2indexes.get(predicate, [])]
        fm = FactMap(predicate, indexes)
        fm.add_facts(list(g))
        factmaps[predicate] = fm
    return factmaps


# ------------------------------------------------------------------------------
# The QueryExecutor actually executes the queries
# ------------------------------------------------------------------------------


class QueryExecutorTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum = IntegerField
            astr = StringField

        self.F = F

        class G(Predicate):
            anum = IntegerField
            astr = StringField

        self.G = G

        factmaps = factmaps_dict(
            [
                G(1, "a"),
                G(1, "foo"),
                G(5, "a"),
                G(5, "foo"),
                F(1, "a"),
                F(1, "foo"),
                F(5, "a"),
                F(5, "foo"),
            ]
        )
        self.factmaps = factmaps

    # --------------------------------------------------------------------------
    # Test some basic configurations
    # --------------------------------------------------------------------------
    def test_nonapi_QueryExecutor(self):
        F = self.F
        G = self.G
        factmaps = self.factmaps
        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order

        roots = (F, G)
        join = pj([F.anum == G.anum], roots)
        where = pw((F.astr == "foo"), roots)
        order_by = pob([G.anum, G.astr], roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=order_by, joh=bjoh)
        qe = QueryExecutor(factmaps, qspec)

        # Test output with no options
        result = list(qe.all())
        expected = set(
            [
                (F(1, "foo"), G(1, "a")),
                (F(1, "foo"), G(1, "foo")),
                (F(5, "foo"), G(5, "a")),
                (F(5, "foo"), G(5, "foo")),
            ]
        )
        self.assertEqual(expected, set(result))

    # --------------------------------------------------------------------------
    # Test some basic configurations
    # --------------------------------------------------------------------------
    def test_nonapi_basic_tests(self):
        F = self.F
        G = self.G
        factmaps = self.factmaps

        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        roots = [F, G]

        joins1 = pj([F.anum == G.anum], roots)
        where1 = pw((G.anum > 4) | (F.astr == "foo"), roots)
        orderbys = pob([F.anum, G.anum], roots)
        qspec = QuerySpec(roots=roots, join=joins1, where=where1, order_by=orderbys, joh=bjoh)

        # Test output with no options
        qe = QueryExecutor(factmaps, qspec)
        result = list(qe.all())
        expected = set(
            [
                (F(1, "foo"), G(1, "a")),
                (F(1, "foo"), G(1, "foo")),
                (F(5, "a"), G(5, "a")),
                (F(5, "a"), G(5, "foo")),
                (F(5, "foo"), G(5, "a")),
                (F(5, "foo"), G(5, "foo")),
            ]
        )
        self.assertEqual(expected, set(result))

        # Test output with a simple swapped signature
        nqspec = qspec.newp(select=(G, F))
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set(
            [
                (G(1, "a"), F(1, "foo")),
                (G(1, "foo"), F(1, "foo")),
                (G(5, "a"), F(5, "a")),
                (G(5, "foo"), F(5, "a")),
                (G(5, "a"), F(5, "foo")),
                (G(5, "foo"), F(5, "foo")),
            ]
        )
        self.assertEqual(expected, set(result))

        # Test output with filtered signature
        nqspec = qspec.newp(select=[G.anum])
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set([1, 5])
        self.assertEqual(expected, set(result))

        # Test output with an complex implicit function signature
        nqspec = qspec.newp(select=(G.anum, lambda f, g: "X{}".format(f.astr)))
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set([(1, "Xfoo"), (5, "Xa"), (5, "Xfoo")])
        self.assertEqual(expected, set(result))

        # Test output with an complex explicit function signature
        nqspec = qspec.newp(select=(G.anum, func([F.astr], lambda v: "X{}".format(v))))
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set([(1, "Xfoo"), (5, "Xa"), (5, "Xfoo")])
        self.assertEqual(expected, set(result))

        # Test output with filtered signature and distinctness
        nqspec = qspec.newp(select=(G.anum,), distinct=True)
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set([1, 5])
        self.assertTrue(result == [1, 5] or result == [5, 1])

        # Test output with filtered signature and forced tuple
        nqspec = qspec.newp(select=(G.anum,), tuple=True)
        qe = QueryExecutor(factmaps, nqspec)
        result = list(qe.all())
        expected = set([(1,), (5,)])
        self.assertEqual(expected, set(result))

    # --------------------------------------------------------------------------
    # Test query executor with a group_by query
    # --------------------------------------------------------------------------
    def test_nonapi_group_by(self):
        class F(Predicate):
            anum = IntegerField

        class G(Predicate):
            anum = IntegerField
            astr = StringField
            aval = IntegerField

        factmaps = factmaps_dict(
            [
                G(1, "a", 5),
                G(1, "b", 4),
                G(2, "a", 6),
                G(2, "b", 7),
                G(3, "a", 1),
                G(3, "b", 8),
                F(1),
                F(2),
            ]
        )

        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        roots = [F, G]

        joins1 = pj([F.anum == G.anum], roots)
        orderbys = pob([G.astr, F.anum], roots)
        #        groupbys = pob([G.astr,F.anum],roots)
        groupbys = pob([G.astr], roots)

        qspec = QuerySpec(
            roots=roots, join=joins1, order_by=orderbys, group_by=groupbys, joh=bjoh
        )

        qe = QueryExecutor(factmaps, qspec)
        result = [(fn, set(fg)) for fn, fg in qe.all()]
        expected = [
            ("a", set([(F(1), G(1, "a", 5)), (F(2), G(2, "a", 6))])),
            ("b", set([(F(1), G(1, "b", 4)), (F(2), G(2, "b", 7))])),
        ]
        self.assertEqual(expected, result)

        nqspec = qspec.newp(select=(G.aval,))
        qe = QueryExecutor(factmaps, nqspec)

        result = [(fn, set(fg)) for fn, fg in qe.all()]
        expected = [("a", set([5, 6])), ("b", set([4, 7]))]
        self.assertEqual(expected, result)

        # Test a group_by with a 'where' with a placeholder and bind
        where = pw(F.anum == ph1_, roots)
        qspec = QuerySpec(
            roots=roots, join=joins1, where=where, order_by=orderbys, group_by=groupbys, joh=bjoh
        )
        bqspec = qspec.bindp(1)
        qe = QueryExecutor(factmaps, bqspec)
        result = [(fn, set(fg)) for fn, fg in qe.all()]
        expected = [("a", set([(F(1), G(1, "a", 5))])), ("b", set([(F(1), G(1, "b", 4))]))]
        self.assertEqual(expected, result)

        # Test a group_by with a 'where' that has an 'in_()'
        where = pw(in_(F.anum, [1, 3]), roots)
        qspec = QuerySpec(
            roots=roots, join=joins1, where=where, order_by=orderbys, group_by=groupbys, joh=bjoh
        )

        qe = QueryExecutor(factmaps, qspec)
        result = [(fn, set(fg)) for fn, fg in qe.all()]
        expected = [("a", set([(F(1), G(1, "a", 5))])), ("b", set([(F(1), G(1, "b", 4))]))]
        self.assertEqual(expected, result)

        # Test a group_by where the is also an 'ordered'
        qspec = QuerySpec(roots=roots, join=joins1, ordered=True, group_by=groupbys, joh=bjoh)

        factmaps = factmaps_dict(
            [
                G(1, "a", 5),
                G(1, "b", 4),
                G(1, "b", 3),
                G(2, "a", 8),
                G(2, "b", 7),
                G(2, "b", 5),
                F(1),
                F(2),
            ]
        )

        qe = QueryExecutor(factmaps, qspec)
        result = [(fn, list(fg)) for fn, fg in qe.all()]
        expected = [
            ("a", [(F(1), G(1, "a", 5)), (F(2), G(2, "a", 8))]),
            (
                "b",
                [
                    (F(1), G(1, "b", 3)),
                    (F(1), G(1, "b", 4)),
                    (F(2), G(2, "b", 5)),
                    (F(2), G(2, "b", 7)),
                ],
            ),
        ]
        self.assertEqual(expected, result)

    # --------------------------------------------------------------------------
    # Test query executor with sorting based on an attribute of the second root
    # predicate (where the join between the two predicates is through a
    # different attribute).
    # --------------------------------------------------------------------------
    def test_nonapi_QueryExecutor_sort_order(self):
        class F(Predicate):
            anum = IntegerField

        class G(Predicate):
            anum = IntegerField
            astr = StringField
            aval = IntegerField

        factmaps = factmaps_dict(
            [
                G(1, "a", 5),
                G(1, "b", 4),
                G(2, "a", 6),
                G(2, "b", 7),
                G(3, "a", 1),
                G(3, "b", 8),
                F(1),
                F(2),
            ]
        )

        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order
        bjoh = oppref_join_order
        roots = [F, G]

        joins1 = pj([F.anum == G.anum], roots)
        orderbys = pob([G.astr, G.anum], roots)
        qspec = QuerySpec(roots=roots, join=joins1, order_by=orderbys, joh=bjoh)

        qe = QueryExecutor(factmaps, qspec)

        (qplan, query) = qe._make_plan_and_query()
        result = list(qe.all())

        expected = [
            (F(1), G(1, "a", 5)),
            (F(2), G(2, "a", 6)),
            (F(1), G(1, "b", 4)),
            (F(2), G(2, "b", 7)),
        ]
        self.assertEqual(expected, result)

        # Alternative using the natural sort order specified by ordered()
        qspec = QuerySpec(roots=roots, join=joins1, ordered=True, joh=bjoh)
        qe = QueryExecutor(factmaps, qspec)
        (qplan, query) = qe._make_plan_and_query()
        result = list(qe.all())
        expected = [
            (F(1), G(1, "a", 5)),
            (F(1), G(1, "b", 4)),
            (F(2), G(2, "a", 6)),
            (F(2), G(2, "b", 7)),
        ]
        self.assertEqual(expected, result)

    # --------------------------------------------------------------------------
    # Test where clause with member operator
    # --------------------------------------------------------------------------
    def test_nonapi_QueryExecutor_contains(self):
        F = self.F
        G = self.G
        factmaps = self.factmaps
        pw = process_where
        pj = process_join
        pob = process_orderby
        fjoh = fixed_join_order

        def runtests():
            roots = (F, G)
            join = pj([F.anum == G.anum], roots)
            order_by = pob([G.anum, G.astr], roots)

            # F.astr in ["foo"] - force F to be the first join
            where = pw(in_(F.astr, ("foo",)), roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=order_by, joh=fjoh(F, G)
            )
            qe = QueryExecutor(factmaps, qspec)

            result = list(qe.all())
            expected = set(
                [
                    (F(1, "foo"), G(1, "a")),
                    (F(1, "foo"), G(1, "foo")),
                    (F(5, "foo"), G(5, "a")),
                    (F(5, "foo"), G(5, "foo")),
                ]
            )
            self.assertEqual(expected, set(result))

            # F.astr in ["foo"] - force F to be the second join - expect same result
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=order_by, joh=fjoh(G, F)
            )
            qe = QueryExecutor(factmaps, qspec)
            result = list(qe.all())
            expected = set(
                [
                    (F(1, "foo"), G(1, "a")),
                    (F(1, "foo"), G(1, "foo")),
                    (F(5, "foo"), G(5, "a")),
                    (F(5, "foo"), G(5, "foo")),
                ]
            )
            self.assertEqual(expected, set(result))

            # F.astr not in ["foo"] - force F to be the first join
            where = pw(notin_(F.astr, ["foo"]), roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=order_by, joh=fjoh(F, G)
            )
            qe = QueryExecutor(factmaps, qspec)
            result = list(qe.all())
            expected = set(
                [
                    (F(1, "a"), G(1, "a")),
                    (F(1, "a"), G(1, "foo")),
                    (F(5, "a"), G(5, "a")),
                    (F(5, "a"), G(5, "foo")),
                ]
            )
            self.assertEqual(expected, set(result))

            # F.astr not in ["foo"] - force F to be the second join
            where = pw(notin_(F.astr, ["foo"]), roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=order_by, joh=fjoh(G, F)
            )
            qe = QueryExecutor(factmaps, qspec)
            result = list(qe.all())
            expected = set(
                [
                    (F(1, "a"), G(1, "a")),
                    (F(1, "a"), G(1, "foo")),
                    (F(5, "a"), G(5, "a")),
                    (F(5, "a"), G(5, "foo")),
                ]
            )
            self.assertEqual(expected, set(result))

        # Run tests with factmap containing no indexes
        runtests()

        # Repeat tests with factmap contain index for F.astr
        factmaps = factmaps_dict(
            [
                G(1, "a"),
                G(1, "foo"),
                G(5, "a"),
                G(5, "foo"),
                F(1, "a"),
                F(1, "foo"),
                F(5, "a"),
                F(5, "foo"),
            ],
            [F.astr],
        )
        runtests()

    # --------------------------------------------------------------------------
    # Test where clause with member operator
    # --------------------------------------------------------------------------
    def test_nonapi_QueryExecutor_contains_indexed(self):

        pw = process_where
        pob = process_orderby
        fjoh = fixed_join_order
        F = self.F
        f1 = F(1, "a")
        f3 = F(3, "a")
        f5 = F(5, "a")
        f7 = F(7, "a")
        f9 = F(9, "a")
        factmaps = factmaps_dict([f1, f3, f5, f7, f9], [F.anum])
        self.assertEqual(len(factmaps), 1)
        self.assertEqual(list(factmaps[F].path2factindex.keys()), hpaths([F.anum]))

        roots = (F,)
        order_by = pob([F.anum], roots)
        where = pw(in_(F.anum, [1, 2]), roots)
        qspec = QuerySpec(roots=roots, where=where, order_by=order_by)
        qe = QueryExecutor(factmaps, qspec)

        # Test output with no options
        result = list(qe.all())
        self.assertEqual(result, [f1])

    # --------------------------------------------------------------------------
    # Some tests when we have non-equality joins. Example taken from:
    # https://en.wikipedia.org/wiki/Relational_algebra
    # --------------------------------------------------------------------------
    def test_nonapi_inequality_join_tests(self):
        class Employee(Predicate):
            name = StringField
            eid = IntegerField
            deptname = StringField

        class Dept(Predicate):
            deptname = StringField
            manager = StringField

        E = Employee
        D = Dept

        e1 = E("Harry", 3415, "Finance")
        e2 = E("Sally", 2241, "Sales")
        e3 = E("George", 3401, "Finance")
        e4 = E("Harriet", 2202, "Sales")
        e5 = E("Tim", 1123, "Executive")

        d1 = D("Sales", "Harriet")
        d2 = D("Production", "Charles")

        factmaps = factmaps_dict([e1, e2, e3, e4, e5, d1, d2])

        pw = process_where
        pj = process_join
        pob = process_orderby
        fjoh = fixed_join_order
        roots = [E, D]
        join = pj([E.deptname != D.deptname], roots)
        expected = set(
            [(e1, d1), (e1, d2), (e2, d2), (e3, d1), (e3, d2), (e4, d2), (e5, d1), (e5, d2)]
        )

        qspec = QuerySpec(roots=roots, join=join, where=[], order_by=[], joh=fjoh(E, D))
        qe = QueryExecutor(factmaps, qspec)
        result = list(qe.all())
        self.assertEqual(expected, set(result))

        qspec = QuerySpec(roots=roots, join=join, where=[], order_by=[], joh=fjoh(D, E))
        qe = QueryExecutor(factmaps, qspec)
        result = list(qe.all())
        self.assertEqual(expected, set(result))

    # --------------------------------------------------------------------------
    # Test sort ordering - to fix bug
    # --------------------------------------------------------------------------
    def test_nonapi_QueryExecutor_order(self):
        class Visit(Predicate):
            tid = ConstantField
            nid = ConstantField

        class ArrivalTime(Predicate):
            tid = ConstantField
            nid = ConstantField
            time = IntegerField

        V = Visit
        AT = ArrivalTime

        v11 = V("t1", "n1")
        v12 = V("t1", "n2")
        v21 = V("t2", "n1")
        v22 = V("t2", "n2")

        atv11 = AT("t1", "n1", 20)
        atv12 = AT("t1", "n2", 10)
        atv21 = AT("t2", "n1", 15)
        atv22 = AT("t2", "n2", 25)

        gv11 = (v11, atv11)
        gv12 = (v12, atv12)
        gv21 = (v21, atv21)
        gv22 = (v22, atv22)

        factmaps = factmaps_dict([v11, v12, v21, v22, atv11, atv12, atv21, atv22])

        pw = process_where
        pj = process_join
        pob = process_orderby
        fjoh = fixed_join_order

        roots = [V, AT]
        join = pj([V.nid == AT.nid], roots)
        where = pw(V.tid == AT.tid, roots)
        order_by = pob([V.tid, AT.time], roots)

        qspec = QuerySpec(roots=roots, joh=fjoh(V, AT), join=join, where=where, order_by=order_by)
        qe = QueryExecutor(factmaps, qspec)

        (qplan, _) = qe._make_plan_and_query()
        result = list(qe.all())
        expected = [gv12, gv11, gv21, gv22]
        self.assertEqual(expected, result)

    # --------------------------------------------------------------------------
    # Test that the default output order always follows the specification and
    # not the order decided by the join_order heuristic.
    # --------------------------------------------------------------------------
    def test_nonapi_default_output_spec(self):
        F = self.F
        G = self.G
        factmaps = self.factmaps

        pw = process_where
        pj = process_join
        pob = process_orderby
        roots = [F, G]
        join = pj([F.anum == G.anum, F.astr == G.astr], roots)
        where = pw((F.anum == 1) & (F.astr == "a"), roots)
        qspec = QuerySpec(roots=roots, join=join, where=where)

        # First case
        nqspec = qspec.newp(joh=fixed_join_order(F, G))
        qe = QueryExecutor(factmaps, nqspec)
        self.assertEqual(list(qe.all()), [(F(1, "a"), G(1, "a"))])

        # Swap the heuristic join order - should make no difference
        nqspec = qspec.newp(joh=fixed_join_order(G, F))
        qe = QueryExecutor(factmaps, nqspec)
        self.assertEqual(list(qe.all()), [(F(1, "a"), G(1, "a"))])

    # --------------------------------------------------------------------------
    # Test delete
    # --------------------------------------------------------------------------
    def test_api_QueryExecutor_delete(self):
        FA = alias(self.F)
        F = self.F
        G = self.G
        bjoh = basic_join_order
        bjoh = oppref_join_order

        def delete(*subroots):
            tmp = factmaps_to_factsets(self.factmaps)
            facts = [f for p, fs in tmp.items() for f in fs]
            factmaps = factmaps_dict(facts)
            pw = process_where
            pj = process_join
            pob = process_orderby

            roots = [FA, G]
            join = pj([FA.anum == G.anum], roots)
            where = pw(G.anum > 4, roots)
            orderby = pob([FA.anum, G.anum], roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=orderby, joh=bjoh, select=subroots
            )
            qe = QueryExecutor(factmaps, qspec)
            return (factmaps, qe.delete())

        # Test deleting all selected elements
        factmaps, count = delete()
        self.assertEqual(count, 4)
        self.assertEqual(len(factmaps), 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))

        # Test deleting all selected elements chosen explicitly
        factmaps, count = delete(FA, G)
        self.assertEqual(count, 4)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))

        # Test deleting only the F instances
        factmaps, count = delete(FA)
        self.assertEqual(count, 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))

        # Test deleting only the G instances using a path object
        factmaps, count = delete(G)
        self.assertEqual(count, 2)
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))

        # Bad delete - deleting an alias path that is not in the original
        with self.assertRaises(ValueError) as ctx:
            factmaps, count = delete(F)
        check_errmsg("For a 'delete' query", ctx)

        # Bad delete - deleting a field path
        with self.assertRaises(ValueError) as ctx:
            factmaps, count = delete(FA.anum)
        check_errmsg("For a 'delete' query", ctx)

        # Bad deletes -  deleting all plus an extra
        FA = alias(self.F)
        with self.assertRaises(ValueError) as ctx:
            fb, count = delete(F, G, FA)
        check_errmsg("For a 'delete' query", ctx)

    # --------------------------------------------------------------------------
    # Test special case delete of a single root item with no where clause
    # --------------------------------------------------------------------------
    def test_api_QueryExecutor_delete_nowhere_clause(self):
        F = self.F
        G = self.G

        def clean_factmaps():
            tmp = factmaps_to_factsets(self.factmaps)
            facts = [f for p, fs in tmp.items() for f in fs]
            return factmaps_dict(facts)

        original_fm = clean_factmaps()

        qe = QueryExecutor(clean_factmaps(), QuerySpec(roots=[F]))
        self.assertEqual(len(original_fm[F]), qe.delete())

        qe = QueryExecutor(clean_factmaps(), QuerySpec(roots=[G]))
        self.assertEqual(len(original_fm[G]), qe.delete())

    # --------------------------------------------------------------------------
    # Test modify
    # --------------------------------------------------------------------------
    def test_api_QueryExecutor_modify(self):
        FA = alias(self.F)
        F = self.F
        G = self.G
        bjoh = basic_join_order
        bjoh = oppref_join_order

        def modify(subroots, fn):
            tmp = factmaps_to_factsets(self.factmaps)
            facts = [f for p, fs in tmp.items() for f in fs]
            factmaps = factmaps_dict(facts)
            pw = process_where
            pj = process_join
            pob = process_orderby

            roots = [FA, G]
            join = pj([FA.anum == G.anum], roots)
            where = pw(G.anum > 4, roots)
            orderby = pob([FA.anum, G.anum], roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=orderby, joh=bjoh, select=subroots
            )
            qe = QueryExecutor(factmaps, qspec)
            return (factmaps, qe.modify(fn))

        # Test replacing all selected elemets chosen implicitly (using a return tuple)
        factmaps, (dcount, acount) = modify(
            [], lambda f, g: ((f, g), (f.clone(anum=f.anum + 10), g.clone(anum=g.anum + 10)))
        )
        self.assertEqual(dcount, 4)
        self.assertEqual(acount, 4)
        self.assertEqual(len(factmaps), 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(F(15, "a"), factmaps))
        self.assertTrue(f_in_factmaps(F(15, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(G(15, "a"), factmaps))
        self.assertTrue(f_in_factmaps(G(15, "foo"), factmaps))

        # Test replacing all selected elements chosen explicitly (using a return set)
        factmaps, (dcount, acount) = modify(
            [FA, G], lambda f, g: ({f, g}, {f.clone(anum=f.anum + 20), g.clone(anum=g.anum + 20)})
        )
        self.assertEqual(dcount, 4)
        self.assertEqual(acount, 4)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(F(25, "a"), factmaps))
        self.assertTrue(f_in_factmaps(F(25, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(G(25, "a"), factmaps))
        self.assertTrue(f_in_factmaps(G(25, "foo"), factmaps))

        # Test replacing only the F instances
        factmaps, (dcount, acount) = modify([FA], lambda f: (f, f.clone(anum=f.anum + 30)))
        self.assertEqual(dcount, 2)
        self.assertEqual(acount, 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(F(35, "a"), factmaps))
        self.assertTrue(f_in_factmaps(F(35, "foo"), factmaps))

        # Bad modify - selecting based on a path that is not in the original
        with self.assertRaises(ValueError) as ctx:
            factmaps, (dcount, acount) = modify([F], lambda f: ({}, {f.clone(anum=f.anum + 30)}))
        check_errmsg("For a 'modify' query", ctx)

        # Bad modify - selecting a path that is not a root path
        with self.assertRaises(ValueError) as ctx:
            factmaps, (dcount, acount) = modify(
                [FA.anum], lambda f: ({}, {f.clone(anum=f.anum + 30)})
            )
        check_errmsg("For a 'modify' query", ctx)

        # Bad modify -  selecting all plus an extra
        with self.assertRaises(ValueError) as ctx:
            factmaps, (dcount, acount) = modify(
                [FA, G, F],
                lambda f, g, fa: ({}, {f.clone(anum=f.anum + 20), g.clone(anum=g.anum + 20)}),
            )
        check_errmsg("For a 'modify' query", ctx)

    # --------------------------------------------------------------------------
    # Test replace - replace is just a special case of modify() with the parameter function fn is
    # wrapped before being passed to modify(). So just need to test that the wrapping is working.
    # --------------------------------------------------------------------------
    def test_api_QueryExecutor_replace(self):
        FA = alias(self.F)
        F = self.F
        G = self.G
        bjoh = basic_join_order
        bjoh = oppref_join_order

        def replace(subroots, fn):
            tmp = factmaps_to_factsets(self.factmaps)
            facts = [f for p, fs in tmp.items() for f in fs]
            factmaps = factmaps_dict(facts)
            pw = process_where
            pj = process_join
            pob = process_orderby

            roots = [FA, G]
            join = pj([FA.anum == G.anum], roots)
            where = pw(G.anum > 4, roots)
            orderby = pob([FA.anum, G.anum], roots)
            qspec = QuerySpec(
                roots=roots, join=join, where=where, order_by=orderby, joh=bjoh, select=subroots
            )
            qe = QueryExecutor(factmaps, qspec)
            return (factmaps, qe.replace(fn))

        # Test replacing all selected elemets chosen implicitly (using a return tuple)
        factmaps, (dcount, acount) = replace(
            [], lambda f, g: (f.clone(anum=f.anum + 10), g.clone(anum=g.anum + 10))
        )
        self.assertEqual(dcount, 4)
        self.assertEqual(acount, 4)
        self.assertEqual(len(factmaps), 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(G(5, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(F(15, "a"), factmaps))
        self.assertTrue(f_in_factmaps(F(15, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(G(15, "a"), factmaps))
        self.assertTrue(f_in_factmaps(G(15, "foo"), factmaps))

        # Test replacing only the F instances
        factmaps, (dcount, acount) = replace([FA], lambda f: f.clone(anum=f.anum + 30))
        self.assertEqual(dcount, 2)
        self.assertEqual(acount, 2)
        self.assertFalse(f_in_factmaps(F(5, "a"), factmaps))
        self.assertFalse(f_in_factmaps(F(5, "foo"), factmaps))
        self.assertTrue(f_in_factmaps(F(35, "a"), factmaps))
        self.assertTrue(f_in_factmaps(F(35, "foo"), factmaps))

    # ----------------------------------------------------------------------------------------
    # Test the output order of the predicates for a complex join matches the input order. This
    # is to track down a bug that is not re-aligning the order when the query execution plan
    # internally changes the order.
    #
    # NOTE: the original bug is to do with passing a function/lambda to the "select" clause.
    # Internally since no input signature is associated with the function/lambda it should be
    # given the signature of the query roots. This wasn't happening and was instead being
    # passed the inputs as they were generated by the query plan. The fix is to use the query
    # root as the input signature for a function/lambda.
    # ----------------------------------------------------------------------------------------
    def test_api_QueryExecutor_output_alignment(self):
        class F(Predicate):
            aint = IntegerField

        class G(Predicate):
            astr = StringField

        class H(Predicate):
            aint = IntegerField
            astr = StringField

        pw = process_where
        pj = process_join
        roots = [F, H, G]

        factmaps = factmaps_dict(
            [F(1), F(2), G("a"), G("b"), H(1, "a"), H(2, "b")], [G.astr, F.aint, H.astr]
        )

        qspec = QuerySpec(
            roots=roots,
            join=pj([F.aint == H.aint, G.astr == H.astr], roots),
            where=pw(F.aint == 1, roots),
            select=(lambda f, h, g: (f, h, g),),
        )

        qe = QueryExecutor(factmaps, qspec)
        plan, _ = qe._make_plan_and_query()
        plan_roots = [x.root.meta.predicate for x in plan]

        # To check that the bug is fixed and the order of the output is the same as the input
        # we need to make sure the order of the input roots is different to the plan roots.
        self.assertNotEqual(roots, plan_roots)
        output = list(qe.all())
        self.assertEqual(len(output), 1)
        f, h, g = output[0]
        self.assertEqual(type(f), F)
        self.assertEqual(type(g), G)
        self.assertEqual(type(h), H)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
