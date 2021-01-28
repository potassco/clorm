#------------------------------------------------------------------------------
# Unit tests for Clorm ORM FactBase and associated classes and functions. This
# includes the query API.
#
# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import unittest
import operator
from .support import check_errmsg

from clingo import Control, Number, String, Function, SymbolType

# Official Clorm API imports for the core complements
from clorm.orm import RawField, IntegerField, StringField, ConstantField, \
    Predicate, ComplexTerm, path, hashable_path, alias

# Implementation imports
from clorm.orm.core import QCondition, trueall

# Official Clorm API imports for the fact base components
from clorm.orm import desc, asc, ph_, ph1_, ph2_, func_, not_, and_, or_, \
    joinall_

from clorm.orm.queryplan import PositionalPlaceholder, NamedPlaceholder, \
    is_boolean_qcondition, is_comparison_qcondition, \
    StandardComparator, FunctionComparator, \
    make_query_alignment_functor, \
    validate_which_expression, negate_which_expression, \
    which_expression_to_nnf, which_expression_to_cnf, \
    Clause, ClauseBlock, normalise_which_expression, \
    clauses_to_clauseblocks, \
    PreJoinPlan, JoinQueryPlan, QueryPlan, validate_join_expression, \
    simple_query_join_order, match_roots_joins_clauses, \
    make_prejoin_plan, make_query_plan, \
    check_query_condition, simplify_query_condition, \
    instantiate_query_condition, evaluate_query_condition

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'PlaceholderTestCase',
    'QQConditionTestCase',
    'ComparatorTestCase',
    'WhichExpressionTestCase',
    'JoinExpressionTestCase',
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
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
        self.assertEqual(ph1,ph1alt)
        self.assertNotEqual(ph1,ph2)

        self.assertEqual(ph1.name, "foo")
        self.assertFalse(ph1.has_default)
        self.assertTrue(ph2.has_default)
        self.assertTrue(ph3.has_default)
        self.assertEqual(ph2.default, "bar")
        self.assertEqual(ph3.default, None)

        with self.assertRaises(TypeError) as ctx:
            ph = NamedPlaceholder("foo")
        check_errmsg("__init__() takes 1 positional", ctx)

        with self.assertRaises(TypeError) as ctx:
            ph = NamedPlaceholder("foo","bar")
        check_errmsg("__init__() takes 1 positional", ctx)

        self.assertFalse(ph1 == 1)
        self.assertFalse(ph1 == 'a')

    def test_PositionalPlaceholder(self):
        ph2 = PositionalPlaceholder(posn=1)
        ph2alt = PositionalPlaceholder(posn=1)
        ph3 = PositionalPlaceholder(posn=2)

        self.assertEqual(ph2,ph2alt)
        self.assertNotEqual(ph2,ph3)

        self.assertEqual(ph2,ph2_)

        with self.assertRaises(TypeError) as ctx:
            ph = PositionalPlaceholder(0)
        check_errmsg("__init__() takes 1 positional", ctx)

        self.assertFalse(1 == ph2)
        self.assertTrue(1 != ph2)
        self.assertFalse(ph2 == 1)
        self.assertTrue(ph2 != 1)
        self.assertFalse(ph2 == 'a')

#------------------------------------------------------------------------------
# Test functions that manipulate query conditional and evaluate the conditional
# w.r.t a fact.
# ------------------------------------------------------------------------------

class QQConditionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
            atuple=(IntegerField,StringField)
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

    def _to_rewrite_test_path_comparator(self):

        F = self.F
        G = self.G
        H = self.H

        f1_pos = F(a=1)
        f1_neg = F(a=2,sign=False)

        g1 = G(a="a",b="b")
        h1_pos = H(a=1,b=f1_pos,c=g1)
        h1_pos2 = H(a=1,b=f1_pos,c=g1)
        h1_neg = H(a=1,b=f1_pos,c=g1,sign=False)
        h2_pos = H(a=2,b=f1_neg,c=g1)

        comp = path(H) == h1_pos
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_pos2))
        self.assertFalse(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.sign == True
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h2_pos))
        self.assertFalse(comp(h1_neg))

        comp = H.c.a == "a"
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h2_pos))
        self.assertTrue(comp(h1_neg))

        comp = H.c.a != "a"
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h2_pos))
        self.assertFalse(comp(h1_neg))

        comp = H.a < 2
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.a <= 2
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_neg))
        self.assertTrue(comp(h2_pos))

        comp = H.a > 1
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h1_neg))
        self.assertTrue(comp(h2_pos))

        comp = H.a > 2
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.a == H.b.a
        self.assertTrue(comp(h1_pos))

    #--------------------------------------------------------------------------
    #  Test that the fact comparators work
    #--------------------------------------------------------------------------

    def test_simple_comparison_conditional(self):
        F=self.F


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
        self.assertEqual(str(cn1),str(cp1))
        self.assertEqual(str(cn2),str(cp2))
        self.assertEqual(str(cn3),str(cp3))
        self.assertEqual(str(cn4),str(cp4))
        self.assertEqual(str(cn5),str(cp5))

        self.assertEqual(cn1,cp1)
        self.assertEqual(cn2,cp2)
        self.assertEqual(cn3,cp3)
        self.assertEqual(cn4,cp4)
        self.assertEqual(cn5,cp5)

        self.assertNotEqual(cn1,cn2)

        # Checking query condition doesn't raise exceptions
        check_query_condition(cn1)
        check_query_condition(cn2)
        check_query_condition(cn3)
        check_query_condition(cn4)
        check_query_condition(cn5)
        check_query_condition(cp1)
        check_query_condition(cp2)
        check_query_condition(cp3)
        check_query_condition(cp4)
        check_query_condition(cp5)

        # Simplification does nothing
        self.assertEqual(simplify_query_condition(cn1),cn1)
        self.assertEqual(simplify_query_condition(cn2),cn2)
        self.assertEqual(simplify_query_condition(cn3),cn3)
        self.assertEqual(simplify_query_condition(cn4),cn4)
        self.assertEqual(simplify_query_condition(cn5),cn5)

        # Instantiating the query conditions
        self.assertEqual(instantiate_query_condition(cn1),cn1)
        self.assertEqual(instantiate_query_condition(cn2),cn2)
        self.assertEqual(instantiate_query_condition(cn3),cn3)
        self.assertNotEqual(instantiate_query_condition(cn4,2),cn4)
        self.assertNotEqual(instantiate_query_condition(cn5,anum=2),cn4)
        self.assertEqual(instantiate_query_condition(cn4,2),cn1)
        self.assertEqual(instantiate_query_condition(cn5,anum=2),cn1)

        # Evaluating condition against some facts
        af1 = F(2,"bbb",(2,"bbb"))
        af2 = F(1,"aaa",(3,"bbb"))

        self.assertTrue(evaluate_query_condition(cn1,af1))
        self.assertTrue(evaluate_query_condition(cn2,af1))
        self.assertTrue(evaluate_query_condition(cn3,af1))

        c1=instantiate_query_condition(cn4,2)
        c2=instantiate_query_condition(cn5,anum=2)
        self.assertEqual(c1,cn1)
        self.assertEqual(c2,cn1)
        self.assertTrue(evaluate_query_condition(c1,af1))
        self.assertTrue(evaluate_query_condition(c2,af1))

        self.assertFalse(evaluate_query_condition(cn1,af2))
        self.assertFalse(evaluate_query_condition(cn2,af2))
        self.assertFalse(evaluate_query_condition(cn3,af2))
        self.assertFalse(evaluate_query_condition(c1,af2))
        self.assertFalse(evaluate_query_condition(c2,af2))

        # Some other query conditions that can't be defined with the nice syntax
        c1 = QCondition(operator.eq, 2, F.anum)
        check_query_condition(c1)
        self.assertEqual(str(c1), "2 == F.anum")
        self.assertEqual(simplify_query_condition(c1),c1)
        self.assertTrue(evaluate_query_condition(c1,af1))

        c1 = QCondition(operator.eq,2,2)
        check_query_condition(c1)
        self.assertEqual(str(c1), "2 == 2")
        c1 = simplify_query_condition(c1)
        self.assertEqual(c1,True)
        self.assertTrue(evaluate_query_condition(c1,af1))

        c1 = F.anum == F.anum
        check_query_condition(c1)
        self.assertEqual(str(c1), "F.anum == F.anum")
        c1 = simplify_query_condition(c1)
        self.assertEqual(c1,True)
        self.assertTrue(evaluate_query_condition(c1,af1))

        c1 = QCondition(operator.eq,2,1)
        check_query_condition(c1)
        self.assertEqual(str(c1), "2 == 1")
        c1 = simplify_query_condition(c1)
        self.assertEqual(c1,False)
        self.assertFalse(evaluate_query_condition(c1,af1))

        f = lambda x : x.anum == 2
        check_query_condition(f)
        self.assertEqual(simplify_query_condition(f),f)
        f2 = instantiate_query_condition(f)
        self.assertNotEqual(f,f2)
        f3 = instantiate_query_condition(f,1,anum=2)
        self.assertNotEqual(f,f3)
        self.assertTrue(evaluate_query_condition(f2,af1))
        self.assertFalse(evaluate_query_condition(f2,af2))

        # Test evaluating against a tuple
        c3 = F.atuple == ph1_
        c4 = simplify_query_condition(c3)
        c5 = instantiate_query_condition(c4,(3,"bbb"))
        self.assertEqual(c3,c4)
        self.assertNotEqual(c4,c5)
        self.assertEqual(c5, F.atuple == (3,"bbb"))
        self.assertTrue(evaluate_query_condition(c5,af2))
        self.assertFalse(evaluate_query_condition(c5,af1))

        # Test some invalid query conditions and evaluations

        with self.assertRaises(ValueError) as ctx:
            check_query_condition(F.anum)
        check_errmsg("Invalid condition \'F.anum\'", ctx)

        with self.assertRaises(ValueError) as ctx:
            check_query_condition(ph1_)
        check_errmsg("Invalid condition \'ph1_\'", ctx)

        with self.assertRaises(ValueError) as ctx:
            f = lambda x: x*2
            check_query_condition(F.anum == f)
        check_errmsg("Invalid functor", ctx)

        with self.assertRaises(ValueError) as ctx:
            f = lambda x: x*2
            check_query_condition(QCondition(operator.eq, F.anum, f))
        check_errmsg("Invalid functor", ctx)

        with self.assertRaises(ValueError) as ctx:
            instantiate_query_condition(cp4)
        check_errmsg("Missing positional placeholder argument 'ph1_'", ctx)

        with self.assertRaises(ValueError) as ctx:
            instantiate_query_condition(F.anum == ph_("blah"), anum=3)
        check_errmsg("Missing named placeholder argument 'ph_(\"blah\")'", ctx)

        with self.assertRaises(ValueError) as ctx:
            instantiate_query_condition(cp4,ph1_)
        check_errmsg("Invalid Placeholder argument 'ph1_'", ctx)

        with self.assertRaises(ValueError) as ctx:
            instantiate_query_condition(cp4,F.anum)
        check_errmsg("Invalid PredicatePath argument 'F.anum'", ctx)

        with self.assertRaises(ValueError) as ctx:
            evaluate_query_condition(cn4,af1)
        check_errmsg("Unresolved Placeholder", ctx)

        # Test evaluation against the wrong type of fact
        G=self.G
        with self.assertRaises(TypeError) as ctx:
            evaluate_query_condition(cn1,G(anum=1,astr="b"))
        check_errmsg("g(1,\"b\") is not of type ", ctx)


    def test_complex_comparison_conditional(self):
        F=self.F

        # Test that simplifying a complex works as expected
        c1 = and_(F.anum == 1, F.astr == ph1_)
        c2 = and_(F.anum == 1, F.astr == ph1_, True)
        c3 = and_(F.anum == 1, F.anum == F.anum, F.astr == ph1_)
        c4 = simplify_query_condition(c2)
        c5 = simplify_query_condition(c3)
        check_query_condition(c1)
        check_query_condition(c2)
        check_query_condition(c3)
        self.assertEqual(c1,c4)
        self.assertEqual(c1,c5)

        c1 = ((F.anum == 1) & (F.astr == ph1_)) | ~(F.atuple == ph2_)
        check_query_condition(c1)
        c2 = instantiate_query_condition(c1,"bbb",(1,"ccc"))

        self.assertTrue(evaluate_query_condition(c2,F(1,"bbb",(1,"bbb"))))
        self.assertTrue(evaluate_query_condition(c2,F(1,"ccc",(1,"bbb"))))
        self.assertFalse(evaluate_query_condition(c2,F(1,"ccc",(1,"ccc"))))

        # TEst simplifying works for a complex disjunction
        c1 = or_(F.anum == 1, F.anum == F.anum, F.astr == ph1_)
        c2 = simplify_query_condition(c1)
        self.assertEqual(c2,True)

        c1 = or_(F.anum == 1, F.anum != F.anum, F.astr == ph1_)
        c2 = or_(F.anum == 1, F.astr == ph1_)
        c3 = simplify_query_condition(c1)
        self.assertEqual(c2,c3)

    #-------------------------------------------------------------------------
    # Since we want to use the condition to model joins (such as using __mult__
    # to model a cross-product) so we now have non-bool and non-comparison
    # conditions. Make sure we can handle this
    # -------------------------------------------------------------------------
    def test_nonapi_not_bool_not_comparison_condition(self):
        F=self.F
        G=self.G

        self.assertTrue(is_boolean_qcondition((F.anum == 1) & (G.anum == 1)))
        self.assertFalse(is_boolean_qcondition(F.anum == 1))
        self.assertFalse(is_boolean_qcondition(joinall_(F,G)))


#------------------------------------------------------------------------------
# Testing of Comparator and related items - make_
# ------------------------------------------------------------------------------

class ComparatorTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
            atuple=(IntegerField,StringField)
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

    #------------------------------------------------------------------------------
    #
    #------------------------------------------------------------------------------
    def test_nonapi_make_query_alignment_functor(self):
        F = self.F
        G = self.G
        f1 = F(1,"a",(2,"b"))
        f2 = F(3,"c",(4,"d"))
        g1 = G(4,"df")

        getter = make_query_alignment_functor([F], [F.anum,F.atuple[0]])
        self.assertEqual(getter((f1,)), (1,2))

        getter = make_query_alignment_functor([F], [10])
        self.assertEqual(getter((f1,)), (10,))

        getter = make_query_alignment_functor([F,G], [F.atuple[0],G.anum])
        self.assertEqual(getter((f1,g1)), (2,4))

        getter = make_query_alignment_functor([F,G], [F.atuple[0]])
        self.assertEqual(getter((f1,g1)), (2,))

        getter = make_query_alignment_functor([F,G], [F.atuple[0],[1,2]])
        self.assertEqual(getter((f1,g1)), (2,[1,2]))

        # Make sure it can also deal with predicate aliases
        X = alias(F)
        getter = make_query_alignment_functor(
            [X,F], [F.atuple[1], X.atuple[0], X.anum])
        self.assertEqual(getter((f1,f2)), ("d",2,1))

        # Testing bad creation of the getter

        # Empty input or output
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([], [F.atuple[0],G.anum])
        check_errmsg("Empty input predicate", ctx)
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([F], [])
        check_errmsg("Empty output path", ctx)

        # Missing input predicate path
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([F], [F.atuple[0],G.anum])
        check_errmsg("Invalid signature match", ctx)

        # Bad input is not a path
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([2], [F.atuple[0]])
        check_errmsg("Invalid input predicate path signature", ctx)

        # Bad input is not a predicate
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([F.anum], [F.atuple[0]])
        check_errmsg("Invalid input predicate path", ctx)

        # Bad output is a placeholder
        with self.assertRaises(TypeError) as ctx:
            make_query_alignment_functor([F], [F.atuple[0], ph1_])
        check_errmsg("Output signature '[F.atuple.arg1", ctx)

        # Test bad inputs to the getter
        with self.assertRaises(TypeError) as ctx:
            getter((f1,))
        check_errmsg("Invalid input to getter function: expecting", ctx)

        with self.assertRaises(TypeError) as ctx:
            getter((f1,2))
        check_errmsg("Invalid input to getter function: 2 is not", ctx)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_StandardComparator(self):
        F = self.F
        G = self.G
        X = alias(F)

        def hps(paths): return set([ hashable_path(p) for p in paths])
        SC=StandardComparator

        # Test __str__
        self.assertEqual(str(SC(operator.eq,[F.anum,4])), "F.anum == 4")

        # Test __eq__ and __ne__
        self.assertEqual(SC(operator.eq,[F.anum,4]),SC(operator.eq,[F.anum,4]))
        self.assertNotEqual(SC(operator.eq,[F.anum,4]),SC(operator.eq,[F.anum,3]))
        self.assertNotEqual(SC(operator.eq,[F.anum,4]),SC(operator.eq,[F.anum,ph1_]))

        # Test __hash__
        self.assertEqual(hash(SC(operator.eq,[F.anum,4])),
                         hash(SC(operator.eq,[F.anum,4])))

        # Test negating
        self.assertEqual(SC(operator.eq,[F.anum,4]).negate(),SC(operator.ne,[F.anum,4]))
        self.assertEqual(SC(operator.ne,[F.anum,4]).negate(),SC(operator.eq,[F.anum,4]))
        self.assertEqual(SC(operator.lt,[F.anum,4]).negate(),SC(operator.ge,[F.anum,4]))
        self.assertEqual(SC(operator.le,[F.anum,4]).negate(),SC(operator.gt,[F.anum,4]))
        self.assertEqual(SC(operator.gt,[F.anum,4]).negate(),SC(operator.le,[F.anum,4]))
        self.assertEqual(SC(operator.ge,[F.anum,4]).negate(),SC(operator.lt,[F.anum,4]))

        self.assertNotEqual(SC(operator.eq,[F.anum,4]).negate(),SC(operator.eq,[F.anum,4]))

        # Test dealiasing
        self.assertEqual(SC(operator.eq,[F.anum,4]).dealias(), SC(operator.eq,[F.anum,4]))
        self.assertEqual(SC(operator.eq,[X.anum,4]).dealias(), SC(operator.eq,[F.anum,4]))
        self.assertEqual(SC(operator.eq,[X.anum,X.astr]).dealias(),
                         SC(operator.eq,[F.anum,F.astr]))

        # Test swap operation
        self.assertEqual(SC(operator.eq,[F.anum,4]).swap(),SC(operator.eq,[4,F.anum]))
        self.assertEqual(SC(operator.ne,[F.anum,4]).swap(),SC(operator.ne,[4,F.anum]))
        self.assertEqual(SC(operator.lt,[F.anum,4]).swap(),SC(operator.gt,[4,F.anum]))
        self.assertEqual(SC(operator.le,[F.anum,4]).swap(),SC(operator.ge,[4,F.anum]))
        self.assertEqual(SC(operator.gt,[F.anum,4]).swap(),SC(operator.lt,[4,F.anum]))
        self.assertEqual(SC(operator.ge,[F.anum,4]).swap(),SC(operator.le,[4,F.anum]))

        # Test paths
        self.assertEqual(hps(SC(operator.eq,[F.anum,4]).paths), hps([F.anum]))
        self.assertEqual(hps(SC(operator.eq,[F.anum,F.anum]).paths), hps([F.anum]))
        self.assertEqual(hps(SC(operator.eq,[F.anum,F.astr]).paths), hps([F.anum,F.astr]))

        # Test placeholders
        self.assertEqual(SC(operator.eq,[F.anum,4]).placeholders, set())
        self.assertEqual(SC(operator.eq,[F.anum,ph1_]).placeholders, set([ph1_]))
        self.assertEqual(SC(operator.eq,[F.anum,ph_("b")]).placeholders, set([ph_("b")]))

        # Test roots
        self.assertEqual(hps(SC(operator.eq,[F.anum,4]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq,[F.anum,F.anum]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq,[F.anum,F.astr]).roots), hps([F]))
        self.assertEqual(hps(SC(operator.eq,[F.anum,G.anum]).roots), hps([F,G]))
        X=alias(F)
        self.assertEqual(hps(SC(operator.eq,[X.anum,F.anum]).roots), hps([X,F]))

        # Test grounding
        self.assertEqual(SC(operator.eq,[F.anum,4]), SC(operator.eq,[F.anum,4]).ground())

        self.assertEqual(SC(operator.eq,[F.anum,ph2_]).ground(1,4),
                         SC(operator.eq,[F.anum,4]))
        self.assertEqual(SC(operator.eq,[F.anum,ph_("val")]).ground(1,4,val=4),
                         SC(operator.eq,[F.anum,4]))

        # Bad grounding
        with self.assertRaises(ValueError) as ctx:
            SC(operator.eq,[F.anum,ph_("val")]).ground(1,4)
        check_errmsg("Missing named", ctx)
        with self.assertRaises(ValueError) as ctx:
            SC(operator.eq,[F.anum,ph2_]).ground(1)
        check_errmsg("Missing positional", ctx)

        # Test make_callable
        self.assertTrue(SC(operator.eq,[1,1]).make_callable([G])(5))
        self.assertTrue(SC(operator.eq,[G.anum,1]).make_callable([G])((G(1,"b"),)))
        self.assertFalse(SC(operator.eq,[G.anum,1]).make_callable([G])((G(2,"b"),)))
        sc=SC(operator.eq,[G.anum,1]).make_callable([F,G])
        self.assertFalse(sc((F(1,"b",(1,"b")),G(2,"b"))))
        self.assertTrue(sc((F(1,"b",(1,"b")),G(1,"b"))))

        # Cannot make_callable on ungrounded
        with self.assertRaises(TypeError) as ctx:
            SC(operator.eq,[G.anum,ph1_]).make_callable([F,G])

    #------------------------------------------------------------------------------
    # Test the wrapping of comparison functors in FunctionComparator
    #------------------------------------------------------------------------------
    def test_nonapi_FunctionComparator(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths ])

        F = self.F
        G = self.G

        func1 = lambda x : x.anum >= 0
        func2 = lambda x,y : x == y

        bf1 = FunctionComparator(func1,[path(F)])
        bf2 = FunctionComparator(func2,[F.anum, F.atuple[0]])

        self.assertEqual(hps(bf1.paths), hps([F]))
        self.assertEqual(hps(bf2.paths), hps([F.anum,F.atuple[0]]))

        nbf1 = FunctionComparator(func1,[path(F)],negative=True)
        self.assertEqual(bf1.negate(), nbf1)

        sat1 = bf1.ground().make_callable([F])
        nsat1 = bf1.negate().ground().make_callable([F])
        nsat2 = bf1.ground().negate().make_callable([F])
        fact1 = F(1,"ab",(-2,"abc"))
        fact2 = F(-1,"ab",(2,"abc"))

        self.assertTrue(sat1((fact1,)))
        self.assertFalse(sat1((fact2,)))

        self.assertFalse(nsat1((fact1,)))
        self.assertFalse(nsat2((fact1,)))
        self.assertTrue(nsat1((fact2,)))
        self.assertTrue(nsat2((fact2,)))

        self.assertEqual(bf1.ground(),bf1.ground().ground())

        # Test the paths and roots properties
        func3 = lambda x,y,z : x==y+z
        X=alias(F)
        bf = func_([F.anum,X.anum,G.anum], func3)
        self.assertEqual(hps(bf.paths),hps([F.anum,X.anum,G.anum]))
        self.assertEqual(hps(bf.roots),hps([F,X,G]))

        func4 = lambda x : x > 5
        bf1 = func_([F.anum], func4)
        bf2 = func_([X.anum], func4)
        self.assertNotEqual(bf1,bf2)
        self.assertNotEqual(hps(bf1.roots),hps(bf2.roots))
        self.assertEqual(bf1,bf2.dealias())
        self.assertEqual(hps(bf1.roots),hps(bf2.dealias().roots))


        with self.assertRaises(RuntimeError) as ctx:
            bf1.make_callable([F])
        check_errmsg("Internal bug: make_callable", ctx)

        with self.assertRaises(TypeError) as ctx:
            bf = FunctionComparator(func1,[])
        check_errmsg("Invalid empty path signature", ctx)

    #------------------------------------------------------------------------------
    # Test more complex case of wrapping of comparison functors in
    # FunctionComparator
    # ------------------------------------------------------------------------------
    def test_nonapi_FunctionComparator_with_args(self):
        def hps(paths):
            return [hashable_path(p) for p in paths ]

        F = self.F
        func1 = lambda x, y : x.anum >= y
        func2 = lambda x, y=10 : x.anum >= y

        bf1 = FunctionComparator(func1,[F.anum,F.astr])
        self.assertEqual(bf1.ground().placeholders, set())
        bf1 = FunctionComparator(func1,[F.anum])
        self.assertEqual(bf1.placeholders, set([ph_("y")]))
        bf1 = FunctionComparator(func1,[F.anum],assignment={'y': 5})
        self.assertEqual(bf1.placeholders, set())

        bf1 = FunctionComparator(func2,[F.anum])
        self.assertEqual(bf1.ground(),bf1.ground(y=10))
        self.assertNotEqual(bf1.ground(),bf1.ground(y=11))

        bf1 = FunctionComparator(func1,[path(F)])
        assignment={'y' : 1}
        gbf1 = FunctionComparator(func1,[path(F)],False,assignment)
        self.assertEqual(gbf1,bf1.ground(**assignment))

        # Partial grounding will fail
        with self.assertRaises(ValueError) as ctx:
            bf1.ground()
        check_errmsg("Even after the named placeholders", ctx)

        # Too many paths
        with self.assertRaises(TypeError) as ctx:
            bf1 = FunctionComparator(func1,[F.anum,F.astr,F.atuple])
        check_errmsg("More paths specified", ctx)

        # Bad assignment parameter value
        with self.assertRaises(TypeError) as ctx:
            bf1 = FunctionComparator(func1,[F.anum],assignment={'k': 5})
        check_errmsg("FunctionComparator is being given an assignment", ctx)


        bf1 = FunctionComparator(lambda x,y : x < y,[F.anum,F.atuple[0]])
        sat1 = bf1.ground().make_callable([F])
        nsat1 = bf1.negate().ground().make_callable([F])
        fact1 = F(1,"ab",(-2,"abc"))
        fact2 = F(-1,"ab",(2,"abc"))

        self.assertFalse(sat1((fact1,))) ; self.assertTrue(nsat1((fact1,)))
        self.assertTrue(sat1((fact2,))) ; self.assertFalse(nsat1((fact2,)))

    #------------------------------------------------------------------------------
    # Test the func_ API functor for creating FunctionComparator
    # ------------------------------------------------------------------------------
    def test_api_func_(self):

        F = self.F
        G = self.G
        func1 = lambda x, y : x.anum == y.anum

        wrap1 = FunctionComparator(func1,[F,G])
        wrap2 = func_([F,G],func1)
        self.assertEqual(wrap1,wrap2)
        sat1 = wrap1.ground().make_callable([F,G])
        sat2 = wrap2.ground().make_callable([F,G])

        f1 = F(1,"ab",(-2,"abc"))
        f2 = F(-1,"ab",(2,"abc"))
        g1 = G(1,2)
        g2 = G(-1,4)
        self.assertTrue(sat1((f1,g1)))
        self.assertEqual(sat1((f1,g1)),sat2((f1,g1)))

        self.assertFalse(sat1((f2,g1)))
        self.assertEqual(sat1((f2,g1)),sat2((f2,g1)))

    # ------------------------------------------------------------------------------
    # Make ComparisonCallable objects from either any ground comparison condition.
    # ------------------------------------------------------------------------------
    def test_nonapi_comparison_callables(self):
        F = self.F
        G = self.G
        func1 = lambda x, y : x == y

        wrap2 = func_([F.anum,G.anum],func1)
        sat1 = wrap2.ground().make_callable([G,F])
        sat2 = StandardComparator.from_which_qcondition(F.anum == G.anum).make_callable([G,F])

        f1 = F(1,"ab",(-2,"abc"))
        f2 = F(-1,"ab",(2,"abc"))
        g1 = G(1,4)
        g2 = G(-1,4)

        self.assertTrue(sat1((g1,f1)))
        self.assertTrue(sat2((g1,f1)))
        self.assertTrue(sat1((g2,f2)))
        self.assertTrue(sat2((g2,f2)))

        self.assertFalse(sat1((g1,f2)))
        self.assertFalse(sat2((g1,f2)))
        self.assertFalse(sat1((g2,f1)))
        self.assertFalse(sat2((g2,f1)))

        # Bad calls to the callable
        with self.assertRaises(TypeError) as ctx:
            sat1(g1,f1)
        check_errmsg("__call__() takes 2", ctx)

        with self.assertRaises(TypeError) as ctx:
            sat1((f1,g1))
        check_errmsg("Invalid input", ctx)

        # Bad calls to make_comparison_callable
        with self.assertRaises(TypeError) as ctx:
            sc = StandardComparator.from_which_qcondition(F.anum == G.anum)
            sc.make_callable([G])
        check_errmsg("Invalid signature match", ctx)

#------------------------------------------------------------------------------
# Test query "which" expressions. Turning nested QConditions into a set of
# clauses.
# ------------------------------------------------------------------------------

class WhichExpressionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
            atuple=(IntegerField,StringField)
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_which_expression(self):
        F = self.F
        G = self.G

        vwe = validate_which_expression
        msc = StandardComparator.from_which_qcondition
        mfc = FunctionComparator.from_specification

        # Comparison QConditions and raw functions are turned into Comparators
        self.assertEqual(vwe((F.anum == 4), [F]), msc(F.anum == 4))
        self.assertEqual(vwe(~(F.anum == 4), [F]), not_(msc(F.anum == 4)))
        self.assertEqual(vwe((F.anum == 4) & (F.astr == "df"), [F]),
                         and_(msc(F.anum == 4),msc(F.astr == "df")))
        self.assertEqual(vwe((F.anum == 4) | (F.astr == "df"), [F]),
                         or_(msc(F.anum == 4),msc(F.astr == "df")))
        self.assertEqual(vwe((F.anum == 4) | \
                             ((F.astr == "df") & ~(F.atuple[0] < 2)), [F]),
                         or_(msc(F.anum == 4),
                             and_(msc(F.astr == "df"),not_(msc(F.atuple[0] < 2)))))

        f=lambda x: x + F.anum
        self.assertEqual(vwe(f,[F]), mfc([F], f))

        cond1 = (F.anum == 4) & f
        cond2 = and_(msc(F.anum == 4),mfc([F],f))
        self.assertEqual(vwe(cond1, [F]),cond2)
        self.assertEqual(vwe(cond2, [F]),cond2)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_negate_which_expression(self):
        F = self.F
        G = self.G
        vwe = validate_which_expression
        nwe = negate_which_expression

        bf = vwe(func_([F.anum],lambda x: x < 2),[F])
        nbf = bf.negate()

        self.assertEqual(nwe(nbf), bf)
        self.assertEqual(nwe(vwe(F.anum == 3,[F])), vwe(F.anum != 3,[F]))



        self.assertEqual(nwe(vwe(F.anum != 3)), vwe(F.anum == 3))
        self.assertEqual(nwe(vwe(F.anum < 3)) , vwe(F.anum >= 3))
        self.assertEqual(nwe(vwe(F.anum <= 3)), vwe(F.anum > 3))
        self.assertEqual(nwe(vwe(F.anum > 3)) , vwe(F.anum <= 3))
        self.assertEqual(nwe(vwe(F.anum >= 3)), vwe(F.anum < 3))

        c = vwe((F.anum == 3) | (bf))
        nc = vwe((F.anum != 3) & (nbf))
        self.assertEqual(nwe(c),nc)
        self.assertEqual(nwe(nc),c)

        c = vwe(~(~(F.anum == 3) | ~(F.anum != 4)))
        nc = vwe((F.anum != 3) | (F.anum == 4))
        self.assertEqual(nwe(c),nc)

    # ------------------------------------------------------------------------------
    # Test turning the which expression into NNF
    # ------------------------------------------------------------------------------
    def test_nonapi_which_expression_to_nnf(self):
        F = self.F
        vwe = validate_which_expression
        tonnf = which_expression_to_nnf

        c = vwe(~(~(F.anum == 3) | ~(F.anum == 4)))
        nnfc = vwe((F.anum == 3) & (F.anum == 4))
        self.assertEqual(tonnf(c),nnfc)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_which_expression_to_cnf(self):
        F = self.F
        vwe = validate_which_expression
        tocnf = which_expression_to_cnf

        # NOTE: Equality test relies on the order - to make this better would
        # need to introduce ordering over comparison conditions.

        f = vwe(((F.anum == 4) & (F.anum == 3)) | (F.anum == 6))
        cnf = vwe(((F.anum == 4) | (F.anum == 6)) & ((F.anum == 3) | (F.anum == 6)))
        self.assertEqual(tocnf(f),cnf)

        f = vwe((F.anum == 6) | ((F.anum == 4) & (F.anum == 3)))
        cnf = vwe(((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3)))
        self.assertEqual(tocnf(f),cnf)

        f = vwe(((F.anum == 6) & (F.anum == 5)) | ((F.anum == 4) & (F.anum == 3)))
        cnf = vwe((((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3))) & \
                  (((F.anum == 5) | (F.anum == 4)) & ((F.anum == 5) | (F.anum == 3))))
        self.assertEqual(tocnf(f),cnf)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_Clause(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths ])
        vwe = validate_which_expression

        F = self.F
        G = self.G

        cx1 = Clause([vwe(F.anum == 4)])
        cx2 = Clause([vwe(F.anum == 4)])
        cx3 = Clause([vwe(F.anum == ph1_)])

        # Test __eq__ and __ne__
        self.assertEqual(cx1,cx2)
        self.assertNotEqual(cx1,cx3)

        c1 = Clause([vwe(F.anum == 4), vwe(F.astr == "b"), vwe(F.atuple[0] == 6)])

        # Test paths and ground
        self.assertEqual(hps([F.anum,F.astr,F.atuple[0]]), hps(c1.paths))
        self.assertEqual(hps(c1.roots),hps([F]))
        self.assertEqual(c1,c1.ground())

        c2 = Clause([vwe(F.anum == ph1_), vwe(F.astr == "b"), vwe(F.atuple[0] == 6)])
        self.assertEqual(hps([F.anum,F.astr,F.atuple[0]]), hps(c2.paths))
        self.assertEqual(c2.ground(4),c1)
        self.assertEqual(hps(c1.roots),hps([F]))

        f = func_([F.anum], lambda x : x == 2)
        c1 = Clause([f])

        self.assertEqual(hps(c1.paths), hps([F.anum]))
        self.assertEqual(hps(c1.roots),hps([F]))

        # Test dealiasing
        X = alias(F)
        c3 = Clause([vwe(F.anum == 4)])
        c4 = Clause([vwe(X.anum == 4)])
        self.assertNotEqual(c3,c4)
        self.assertEqual(c3,c4.dealias())

        # Test __len__, __getitem__ and __iter__
        cmp10 = vwe(F.anum == 4)
        cmp11 = vwe(X.anum == 4)
        c10 = Clause([cmp10,cmp11])
        self.assertEqual(len(c10),2)
        self.assertEqual(list(c10),[cmp10,cmp11])
        self.assertEqual(c10[1],cmp11)


        # Test placeholders
        self.assertEqual(cx3.placeholders,set([ph1_]))
        fy = func_([F.anum], lambda x, y : x == y)
        self.assertEqual(Clause([fy]).placeholders,set([ph_("y")]))
        fy = func_([F.anum], lambda x, y=10 : x == y)
        self.assertEqual(Clause([fy]).placeholders,set([ph_("y",10)]))

        # Iterate over the conditions within a clause
        c1 = Clause([vwe(G.anum == ph1_),vwe(F.astr == "b"),vwe(F.atuple[0] == 6)])
        self.assertEqual(list(c1),
                         [vwe(G.anum == ph1_),vwe(F.astr == "b"),vwe(F.atuple[0] == 6)])

        # Test make_callable
        c1 = Clause([vwe(G.anum == ph1_),vwe(F.astr == "b")])
        cc = c1.ground(5).make_callable([F,G])

        f1 = F(1,"b",(2,"b"))
        f2 = F(3,"c",(4,"d"))
        g1 = G(4,"df")
        g2 = G(5,"df")
        self.assertTrue(cc((f1,g1)))
        self.assertTrue(cc((f2,g2)))
        self.assertTrue(cc((f1,g2)))
        self.assertFalse(cc((f2,g1)))

        # Test cannot make callable an ungrounded clause
        with self.assertRaises(TypeError) as ctx:
            cc = c1.make_callable([F,G])
        check_errmsg("Internal bug", ctx)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_ClauseBlock(self):
        def hps(paths):
            return set([hashable_path(p) for p in paths ])
        vwe = validate_which_expression

        F = self.F
        G = self.G
        X = alias(F)
        Y = alias(G)

        c1 = Clause([vwe(F.anum == 4), vwe(F.astr == "b")])
        c2 = Clause([vwe(X.anum == 5), vwe(X.astr == "c")])
        c3 = Clause([vwe(G.anum == 6)])
        c4 = Clause([vwe(G.anum == ph1_)])
        cb1 = ClauseBlock([c1,c2,c3])
        cb2 = ClauseBlock([c1,c2,c3])
        cb3 = ClauseBlock([c1,c2,c4])

        # Equality and inequlity
        self.assertEqual(cb1,cb2)
        self.assertNotEqual(cb2,cb3)

        # Test placeholders
        self.assertEqual(cb1.placeholders,set())

        cbt = ClauseBlock()
        self.assertEqual(hps([F.anum,F.astr,X.anum,X.astr,G.anum]), hps(cb1.paths))
        self.assertEqual(hps([F,X,G]), hps(cb1.roots))
        self.assertEqual(cb1.clauses, (c1,c2,c3))

        # Test dealiasing
        c10 = Clause([vwe(F.anum == 4)])
        c11 = Clause([vwe(X.anum == 4)])
        cb10 = ClauseBlock([c10])
        cb11 = ClauseBlock([c11])
        self.assertNotEqual(cb10,cb11)
        self.assertEqual(cb10,cb11.dealias())

        # Test __len__, __getitem__ and __iter__
        c10 = Clause([vwe(F.anum == 4)])
        c11 = Clause([vwe(X.anum == 4)])
        cb10 = ClauseBlock([c10,c11])
        self.assertEqual(len(cb10),2)
        self.assertEqual(list(cb10),[c10,c11])
        self.assertEqual(cb10[1],c11)


        # Test the concatenation of clause blocks
        x1 = ClauseBlock([c1])
        x2 = ClauseBlock([c2])
        x3 = ClauseBlock([c1,c2])
        self.assertEqual(x1+x2,x3)

        self.assertEqual(cb1.ground(),cb2)
        self.assertEqual(list(cb1), [c1,c2,c3])

        c1 = Clause([vwe(F.anum == ph1_)])
        c2 = Clause([vwe(G.anum == ph2_)])
        c1a = Clause([vwe(F.anum == 1)])
        c2b = Clause([vwe(G.anum == 2)])
        cb1 = ClauseBlock([c1,c2])
        cb2 = ClauseBlock([c1a,c2b])
        self.assertEqual(cb1.ground(1,2),cb2)

        # Test placeholders
        self.assertEqual(cb1.placeholders,set([ph1_,ph2_]))

        testfunc = cb2.make_callable([F,G])
        trivialtrue = cbt.make_callable([F,G])
        f1 = F(1,"a",(2,"b"))
        f2 = F(2,"a",(2,"b"))
        g1 = G(2,"a")
        g2 = G(3,"a")

        self.assertFalse(testfunc((f1,g2)))
        self.assertFalse(testfunc((f2,g1)))
        self.assertFalse(testfunc((f2,g2)))
        self.assertTrue(testfunc((f1,g1)))

        self.assertTrue(trivialtrue((f1,g2)))
        self.assertTrue(trivialtrue((f2,g1)))
        self.assertTrue(trivialtrue((f2,g2)))
        self.assertTrue(trivialtrue((f1,g1)))

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_normalise_which_expression(self):
        F = alias(self.F)
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        # Simple cases containing a single clause block
        f = vwe(F.anum == 4)
#        self.assertEqual(tonorm(f), [ClauseBlock([Clause([f])])])
        self.assertEqual(tonorm(f), [Clause([f])])

        f = func_([F.anum], lambda x : x == 2)
#        self.assertEqual(tonorm(f), [ClauseBlock([Clause([f])])])
        self.assertEqual(tonorm(f), [Clause([f])])

        f = vwe(((F.anum == 4) & (F.anum == 3)) | (F.anum == 6))
        clauses = [Clause([vwe(F.anum == 4), vwe(F.anum == 6)]),
                   Clause([vwe(F.anum == 3), vwe(F.anum == 6)])]
        norm = tonorm(f)
        self.assertEqual(tonorm(f),clauses)

        # More complex cases with multiple blocks
        G = alias(self.G)
        X = alias(F)
        Y = alias(G)

        f = vwe(and_(or_(F.anum == 4, F.astr == "b"),
                     X.anum == 5,
                     or_(X.anum == 6, Y.astr == "d"),
                     X.astr == "a"))
        norm = tonorm(f)
        clauses = [Clause([vwe(F.anum == 4), vwe(F.astr == "b")]),
                   Clause([vwe(X.anum == 5)]),
                   Clause([vwe(X.anum == 6), vwe(Y.astr == "d")]),
                   Clause([vwe(X.astr == "a")])]
        self.assertEqual(norm,clauses)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_clauses_to_clauseblocks(self):
        F = path(self.F)
        G = path(self.G)
        X = alias(F)
        Y = alias(G)
        vwe = validate_which_expression

        cf1 = Clause([vwe(F.anum == 4)])
        cx1 = Clause([vwe(X.anum == 5)])
        cbs, catchall = clauses_to_clauseblocks([cf1,cx1])
        self.assertEqual(cbs,[ClauseBlock([cf1]),ClauseBlock([cx1])])
        self.assertEqual(catchall, None)

        cf1 = Clause([vwe(F.anum == 4), vwe(F.astr == "b")])
        cx1 = Clause([vwe(X.anum == 5)])
        cx2 = Clause([vwe(X.astr == "a")])
        cxy1 = Clause([vwe(X.anum == 6), vwe(Y.astr == "d")])
        cbs, catchall = clauses_to_clauseblocks([cf1,cx1,cx2,cxy1])
        self.assertEqual(cbs,[ClauseBlock([cf1]),ClauseBlock([cx1,cx2])])
        self.assertEqual(catchall, ClauseBlock([cxy1]))



#------------------------------------------------------------------------------
# Tests of manipulating/cleaning the query conditions
#------------------------------------------------------------------------------

class JoinExpressionTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=IntegerField
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=IntegerField
        self.G = G

    # ------------------------------------------------------------------------------
    # Test validating a join expression (a list of join clauses)
    # ------------------------------------------------------------------------------
    def test_nonapi_validate_join_expression(self):
        F = path(self.F)
        G = path(self.G)
        SC=StandardComparator
        vje = validate_join_expression
        joins = vje([F.anum == G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.eq, [F.anum,G.anum])])
        self.assertEqual(SC(operator.eq, [F.anum,G.anum]).paths, (F.anum,G.anum))
        self.assertEqual(SC(operator.eq, [F.anum,G.anum]).roots, (path(F),path(G)))
        self.assertEqual(hash(SC(operator.eq, [F.anum,G.anum])),
                         hash(SC(operator.eq, [F.anum,G.anum])))

        joins = vje([F.anum != G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.ne, [F.anum,G.anum])])

        joins = vje([F.anum < G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.lt, [F.anum,G.anum])])

        joins = vje([F.anum <= G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.le, [F.anum,G.anum])])

        joins = vje([F.anum > G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.gt, [F.anum,G.anum])])

        joins = vje([F.anum >= G.anum],[F,G])
        self.assertEqual(joins,[SC(operator.ge, [F.anum,G.anum])])

        joins = vje([joinall_(F,G)],[F,G])
        self.assertEqual(joins,[])

        # Missing root path
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum <= G.anum],[F])
        check_errmsg("Join specification", ctx)

        # Only a single path
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum <= 1],[F,G])
        check_errmsg("A join specification must have", ctx)

        # Indentical argument
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == F.anum],[F,G])
        check_errmsg("A join specification must have", ctx)

        # Bad cross-product specification
        with self.assertRaises(ValueError) as ctx:
            vje([joinall_(F.anum,G.anum)],[F,G])
        check_errmsg("Cross-product expression", ctx)

        X = alias(F)
        Y = alias(G)

        # A disconnected graph
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == G.anum, X.anum == Y.anum],[F,G,X,Y])
        check_errmsg("Invalid join specification: contains un-joined", ctx)

        Z = alias(G)
        # Missing base root
        with self.assertRaises(ValueError) as ctx:
            vje([F.anum == G.anum, X.anum == Y.anum],[F,G,X,Y,Z])
        check_errmsg("Invalid join specification: missing joins", ctx)

    # ------------------------------------------------------------------------------
    # Test the PreJoinPlan class
    # ------------------------------------------------------------------------------

    def test_nonapi_PreJoinPlan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        cmp1 = vwe(F.anum == 5)
        cmp2 = vwe(F.anum == ph1_)
        cmp3 = vwe(FA.anum == 5)
        cmp4 = vwe(F.anum < F.astr)
        cmp5 = vwe(F.anum < FA.astr)

        cb1 = ClauseBlock([Clause([cmp4])])
        cb2 = ClauseBlock([Clause([cmp5])])

        pjp1 = PreJoinPlan(F.meta.predicate,cmp1,None)
        pjp2 = PreJoinPlan(F.meta.predicate,cmp2,None)
        self.assertTrue(pjp1.keycomparator == cmp1)
        self.assertTrue(pjp1.remainder is None)

        self.assertNotEqual(pjp1,pjp2)
        self.assertTrue(pjp1.ground() is pjp1)
        self.assertEqual(pjp2.ground(5), pjp1)
        self.assertEqual(pjp2.placeholders, set([ph1_]))

        pjp1 = PreJoinPlan(F.meta.predicate,None,cb1)
        self.assertTrue(pjp1.keycomparator is None)
        self.assertTrue(pjp1.remainder == cb1)

    # ------------------------------------------------------------------------------
    # Test the JoinQueryPlan class
    # ------------------------------------------------------------------------------

    def test_nonapi_JoinQueryPlan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        joins = vje([G.anum == F.anum, F.anum < GA.anum, joinall_(G,FA)],[F,G,FA,GA])

        cfcomplex = Clause([vwe(F.anum == GA.anum)])
        cfa1 = Clause([vwe(F.anum == 5)])
        cfa1alt = Clause([vwe(F.anum == ph1_)])

        # Good input
        qp1 =     JoinQueryPlan((F,G,GA),FA,joins,
                                PreJoinPlan(F.meta.predicate,None,ClauseBlock([cfa1])),
                                ClauseBlock([cfcomplex]))
        qp1copy = JoinQueryPlan((F,G,GA),FA,joins,
                                PreJoinPlan(F.meta.predicate,None,ClauseBlock([cfa1])),
                                ClauseBlock([cfcomplex]))

        qp2 = JoinQueryPlan((F,G,GA),FA,joins,
                            PreJoinPlan(F.meta.predicate,None,ClauseBlock([cfa1alt])),
                            ClauseBlock([cfcomplex]))

        # Test the equality and inequality overloads
        self.assertEqual(qp1,qp1copy)
        self.assertEqual(qp1.ground(),qp1)
        self.assertEqual(qp1.ground(5),qp1)
        self.assertNotEqual(qp1,qp2)
        self.assertEqual(qp2.ground(5),qp1)

        # Test placeholders
        self.assertEqual(qp1.placeholders,set())
        self.assertEqual(qp2.placeholders,set([ph1_]))

        self.assertEqual(qp1.input_signature, (path(F),path(G),path(GA)))
        self.assertEqual(qp1.root, path(FA))
        self.assertEqual(qp1.prejoin,
                         PreJoinPlan(F.meta.predicate,None,ClauseBlock([cfa1])))
        self.assertEqual(qp1.postjoin, ClauseBlock([cfcomplex]))

        # Missing roots in the input signature
        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((),F,joins,None,None)
        check_errmsg("Internal bug: join", ctx)

        # Bad root path and bad signature path
        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((),F.anum,joins,None,None)
        check_errmsg("Internal bug: 'F.anum' is not a root", ctx)

        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((G.anum,),F,joins,None,None)
        check_errmsg("Internal bug: 'G.anum' in input", ctx)

        # Bad join
        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((G,),F,joins,None,None)
        check_errmsg("Internal bug: join 'F.anum <", ctx)

        # Bad prejoin
        with self.assertRaises(ValueError) as ctx:
            pjp = PreJoinPlan(G.meta.predicate,None,
                              ClauseBlock([Clause([vwe(G.anum == 5)])]))
            qp1 = JoinQueryPlan((G,),F,[],pjp,None)
        check_errmsg("Internal bug: prejoin query", ctx)
        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((G,),F,[],ClauseBlock([cfcomplex]),None)
        check_errmsg("Internal bug: prejoin query", ctx)

        # Bad postjoin
        with self.assertRaises(ValueError) as ctx:
            qp1 = JoinQueryPlan((G,),F,[],None, ClauseBlock([cfcomplex]))
        check_errmsg("Internal bug: postjoin query", ctx)

    # ------------------------------------------------------------------------------
    # Test geneating the query plan when give the root join order, the joins,
    # and the where clauses.
    # ------------------------------------------------------------------------------

    def test_nonapi_make_prejoin_plan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        which = tonorm(vwe((FA.anum < 4) & (FA.astr == "foo" ) & (FA.anum == FA.astr) &
                           ((FA.anum > 10) | (FA.astr == "bar"))))
        cb = ClauseBlock(which)

        which2 = tonorm(vwe((F.anum < 4) & (F.anum == F.astr) &
                            ((F.anum > 10) | (F.astr == "bar"))))
        cbother = ClauseBlock(which2)
        pjp = make_prejoin_plan(F.meta.predicate,[F.anum,F.astr],cb)
        self.assertEqual(pjp.keycomparator, vwe(F.astr == "foo"))
        self.assertEqual(len(pjp.remainder), len(cbother))

    # ------------------------------------------------------------------------------
    # Test the JoinQueryPlan class
    # ------------------------------------------------------------------------------

    def test_nonapi_QueryPlan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        joins1 = []
        joins2 = vje([G.anum == F.anum],[F,G])
        joins3 = vje([G.anum == F.anum, F.anum < FA.anum],[F,G,FA])

        c1 = Clause([vwe(F.anum == 5)])
        c1ph = Clause([vwe(F.anum == ph1_)])
        c2 = Clause([vwe(F.astr == G.astr)])

        qpj1 = JoinQueryPlan((),F,joins1,c1,None)
        qpj1ph = JoinQueryPlan((),F,joins1,c1ph,None)
        qpj2 = JoinQueryPlan((F,),G,joins2,None,c2)
        qpj3 = JoinQueryPlan((F,G),FA,joins3,None,None)

        qp1 = QueryPlan([qpj1])
        self.assertEqual(len(qp1),1)
        self.assertEqual(qp1[0],qpj1)

        qp2 = QueryPlan([qpj1,qpj2])
        self.assertEqual(len(qp2),2)
        self.assertEqual(qp2[0],qpj1)
        self.assertEqual(qp2[1],qpj2)

        qp3 = QueryPlan([qpj1,qpj2,qpj3])
        self.assertEqual(len(qp3),3)

        self.assertEqual(list(qp3), [qpj1,qpj2,qpj3])

        qp3ph = QueryPlan([qpj1ph,qpj2,qpj3])
        self.assertNotEqual(qp3,qp3ph)
        self.assertEqual(qp3,qp3ph.ground(5))

        # Test placeholders
        self.assertEqual(qp3.placeholders,set())
        self.assertEqual(qp3ph.placeholders,set([ph1_]))
        self.assertEqual(qp3ph.ground(4).placeholders,set())

        # Bad query plans
        with self.assertRaises(ValueError) as ctx:
            qp = QueryPlan([qpj2])
        check_errmsg("Invalid 'input_signature'", ctx)
        with self.assertRaises(ValueError) as ctx:
            qp = QueryPlan([qpj2,qpj1,qpj3])
        check_errmsg("Invalid 'input_signature'", ctx)

    # ------------------------------------------------------------------------------
    # Test geneating the query plan when give the root join order, the joins,
    # and the where clauses.
    # ------------------------------------------------------------------------------

    def test_nonapi_match_roots_joins_clauses(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        joins = vje([G.anum == F.anum, F.anum < GA.anum, joinall_(G,FA)],[F,G,FA,GA])
        which = tonorm(vwe((F.anum == 4) & (FA.anum < 2)))

        queryplan = match_roots_joins_clauses([],[FA,GA,G,F],joins,which)

    # ------------------------------------------------------------------------------
    # Test the simple heuristic for generating the join order
    # ------------------------------------------------------------------------------
    def test_nonapi_simple_query_join_order(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression

        joins = vje([F.anum == G.anum, F.anum < GA.anum, joinall_(G,FA)],[F,G,FA,GA])
        qorder = simple_query_join_order([], joins, [F,G,FA,GA])
        self.assertEqual(qorder,[FA,GA,G,F])

    # ------------------------------------------------------------------------------
    # Test making a plan from joins and whereclauses
    # ------------------------------------------------------------------------------
    def test_make_query_plan(self):
        F = path(self.F)
        G = path(self.G)
        FA = alias(F)
        GA = alias(G)
        vje = validate_join_expression
        vwe = validate_which_expression
        tonorm = normalise_which_expression

        joins = vje([G.anum == F.anum, F.anum < GA.anum, joinall_(G,FA)],[F,G,FA,GA])
        which = tonorm(vwe((F.anum == 4) & (FA.anum < 2)))

        queryplan = make_query_plan(simple_query_join_order,[F.anum],
                                    [F,G,FA,GA],joins,which)


    # ------------------------------------------------------------------------------
    #
    # ------------------------------------------------------------------------------



#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')



