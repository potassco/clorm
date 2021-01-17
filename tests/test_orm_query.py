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
from clorm.orm.core import QueryCondition

# Official Clorm API imports for the fact base components
from clorm.orm import desc, asc, not_, and_, or_, \
    ph_, ph1_, ph2_, func_

from clorm.orm.query import PositionalPlaceholder, NamedPlaceholder, \
    FunctorComparisonCondition, make_query_alignment_functor, \
    make_comparison_callable, \
    validate_query_condition, \
    check_query_condition, simplify_query_condition, \
    instantiate_query_condition, evaluate_query_condition, \
    negate_query_condition, \
    normalise_to_nnf_query_condition, normalise_to_cnf_query_condition, \
    Clause, normalise_query_condition

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'QueryConditionTestCase',
    'QueryConditionManipulateTestCase'
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Test functions that manipulate query conditional and evaluate the conditional
# w.r.t a fact.
# ------------------------------------------------------------------------------

class QueryConditionTestCase(unittest.TestCase):
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

    #--------------------------------------------------------------------------
    #  Test the overloaded bitwise comparators (&,|,~)
    #--------------------------------------------------------------------------
    def _to_rewrite_test_query_bitwise_comparator_overloads(self):
        class Afact(Predicate):
            anum1=IntegerField
            anum2=IntegerField
            astr=StringField

        fc1 = Afact.anum1 == 1 ; fc2 = Afact.anum1 == 2
        ac = fc1 & fc2
        self.assertEqual(type(ac), BoolComparator)
        self.assertEqual(ac.boolop, operator.and_)
        self.assertEqual(ac.args, (fc1,fc2))

        oc = (Afact.anum1 == 1) | (Afact.anum2 == 2)
        self.assertEqual(type(oc), BoolComparator)
        self.assertEqual(oc.boolop, operator.or_)

        nc1 = ~fc1
        self.assertEqual(type(nc1), BoolComparator)
        self.assertEqual(nc1.boolop, operator.not_)
        self.assertEqual(nc1.args, (fc1,))

        nc2 = ~(Afact.anum1 == 1)
        self.assertEqual(type(nc2), BoolComparator)
        self.assertEqual(nc2.boolop, operator.not_)

        # Test the __rand__ and __ror__ operators
        nc3 = (lambda x: x.astr == "str") | (Afact.anum2 == 2)
        self.assertEqual(type(nc3), BoolComparator)

        nc4 = (lambda x: x.astr == "str") & (Afact.anum2 == 2)
        self.assertEqual(type(nc4), BoolComparator)

        # Test that the comparators actually work
        f1=Afact(1,1,"str")
        f2=Afact(1,2,"nostr")
        f3=Afact(1,2,"str")

        self.assertFalse(ac(f1))
        self.assertFalse(ac(f2))
        self.assertFalse(ac(f3))

        self.assertTrue(oc(f1))
        self.assertTrue(oc(f2))
        self.assertTrue(oc(f3))

        self.assertFalse(nc1(f1)) ; self.assertFalse(nc2(f1))
        self.assertFalse(nc1(f2)) ; self.assertFalse(nc2(f2))
        self.assertFalse(nc1(f3)) ; self.assertFalse(nc2(f3))

        self.assertTrue(nc3(f1))
        self.assertTrue(nc3(f2))
        self.assertTrue(nc3(f3))

        self.assertFalse(nc4(f1))
        self.assertFalse(nc4(f2))
        self.assertTrue(nc4(f3))


    #--------------------------------------------------------------------------
    # Test that simplification is working for the boolean comparator
    #--------------------------------------------------------------------------
    def _to_rewrite_test_bool_comparator_simplified(self):

        def is_static(fc):
            return isinstance(fc, StaticComparator)

        class Afact(Predicate):
            anum1=IntegerField()
            anum2=IntegerField()
            astr=StringField()
        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1 = Afact(1,1,"bbb")
        af2 = Afact(2,3,"aaa")
        af3 = Afact(1,3,"aaa")
        bf1 = Bfact(1,"aaa")

        e1 = Afact.anum1 == 2
        e2 = Afact.anum1 == Afact.anum2
        e3 = Afact.anum1 == Afact.anum1
        e4 = Afact.anum2 != Afact.anum2
        e5 = Bfact.astr == "aaa"

        and1 = and_(e1, e3)
        and2 = and_(e2, e4)
        or1 = or_(e1, e3)
#        sand1 = and1.simplified()
#        sand2 = and2.simplified()
#        sor1 = or1.simplified()

#        self.assertEqual(str(sand1), "Afact.anum1 == 2")
#        self.assertEqual(str(sand2), "False")
#        self.assertEqual(str(sor1), "True")

        or2 = or_(or1,and1)
#        sor2 = or2.simplified()
#        self.assertEqual(str(sor2),"True")

        and3 = and_(and1,and2)
#        sand3 = and3.simplified()
#        self.assertEqual(str(sand3),"False")

        or4 = or_(and3,e1)
#        sor4 = or4.simplified()
#        self.assertEqual(str(sor4), "Afact.anum1 == 2")

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

        # Test the strings generated for simple comparison operators
        self.assertEqual(str(F.anum == 2), "F.anum == 2")
        self.assertEqual(str(F.anum != 2), "F.anum != 2")
        self.assertEqual(str(F.anum < 2), "F.anum < 2")
        self.assertEqual(str(F.anum <= 2), "F.anum <= 2")
        self.assertEqual(str(F.anum > 2), "F.anum > 2")
        self.assertEqual(str(F.anum >= 2), "F.anum >= 2")

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
        c1 = QueryCondition(operator.eq, 2, F.anum)
        check_query_condition(c1)
        self.assertEqual(str(c1), "2 == F.anum")
        self.assertEqual(simplify_query_condition(c1),c1)
        self.assertTrue(evaluate_query_condition(c1,af1))

        c1 = QueryCondition(operator.eq,2,2)
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

        c1 = QueryCondition(operator.eq,2,1)
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
            check_query_condition(QueryCondition(operator.eq, F.anum, f))
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

#------------------------------------------------------------------------------
# Tests of manipulating/cleaning the query conditions
#------------------------------------------------------------------------------

class QueryConditionManipulateTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
            atuple=(IntegerField,StringField)
        self.F = F

        class G(Predicate):
            anum=IntegerField
        self.G = G

    #------------------------------------------------------------------------------
    #
    #------------------------------------------------------------------------------
    def test_nonapi_make_query_alignment_functor(self):
        F = self.F
        G = self.G
        f1 = F(1,"a",(2,"b"))
        f2 = F(3,"c",(4,"d"))
        g1 = G(4)

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

    #------------------------------------------------------------------------------
    # Test the wrapping of comparison functors in FunctorComparisonCondition
    #------------------------------------------------------------------------------
    def test_nonapi_FunctorComparisonCondition(self):
        def hps(paths):
            return [hashable_path(p) for p in paths ]

        F = self.F

        func1 = lambda x : x.anum >= 0
        func2 = lambda x,y : x == y

        bf1 = FunctorComparisonCondition(func1,[path(F)])
        bf2 = FunctorComparisonCondition(func2,[F.anum, F.atuple[0]])

        self.assertTrue(bf1.ground().is_ground)
        self.assertTrue(bf2.ground().is_ground)

        self.assertEqual(hps(bf1.path_signature), hps([path(F)]))
        self.assertEqual(hps(bf2.path_signature), hps([F.anum,F.atuple[0]]))

        self.assertEqual(bf1.predicates, set([F]))
        self.assertEqual(bf2.predicates, set([F]))

        nbf1 = FunctorComparisonCondition(func1,[path(F)],negative=True)
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

        with self.assertRaises(RuntimeError) as ctx:
            bf1.ground().ground()
        check_errmsg("Internal bug: cannot ground", ctx)

        with self.assertRaises(RuntimeError) as ctx:
            bf1.make_callable([F])
        check_errmsg("Internal bug: make_callable", ctx)

        with self.assertRaises(TypeError) as ctx:
            bf = FunctorComparisonCondition(func1,[])
        check_errmsg("Invalid empty path signature", ctx)

    #------------------------------------------------------------------------------
    # Test more complex case of wrapping of comparison functors in
    # FunctorComparisonCondition
    # ------------------------------------------------------------------------------
    def test_nonapi_FunctorComparisonCondition_with_args(self):
        def hps(paths):
            return [hashable_path(p) for p in paths ]

        F = self.F
        func1 = lambda x, y : x.anum >= y
        func2 = lambda x, y=10 : x.anum >= y

        bf1 = FunctorComparisonCondition(func1,[F.anum,F.astr])
        self.assertTrue(bf1.ground().is_ground)
        bf1 = FunctorComparisonCondition(func1,[F.anum])
        self.assertFalse(bf1.is_ground)
        bf1 = FunctorComparisonCondition(func1,[F.anum],assignment={'y': 5})
        self.assertTrue(bf1.is_ground)

        bf1 = FunctorComparisonCondition(func2,[F.anum])
        self.assertFalse(bf1.is_ground)
        self.assertTrue(bf1.ground().is_ground)
        self.assertTrue(bf1.ground({'y':10}).is_ground)
        self.assertEqual(bf1.ground(),bf1.ground({'y':10}))
        self.assertNotEqual(bf1.ground(),bf1.ground({'y':11}))

        bf1 = FunctorComparisonCondition(func1,[path(F)])
        assignment={'y' : 1}
        gbf1 = FunctorComparisonCondition(func1,[path(F)],False,assignment)
        self.assertEqual(gbf1,bf1.ground(assignment))

        # Partial grounding will fail
        with self.assertRaises(ValueError) as ctx:
            bf1.ground({})
        check_errmsg("Even after the named placeholders", ctx)

        # Too many paths
        with self.assertRaises(TypeError) as ctx:
            bf1 = FunctorComparisonCondition(func1,[F.anum,F.astr,F.atuple])
        check_errmsg("More paths specified", ctx)

        # Bad assignment parameter value
        with self.assertRaises(TypeError) as ctx:
            bf1 = FunctorComparisonCondition(func1,[F.anum],assignment={'k': 5})
        check_errmsg("FunctorComparisonCondition is being given an assignment", ctx)


        bf1 = FunctorComparisonCondition(lambda x,y : x < y,[F.anum,F.atuple[0]])
        sat1 = bf1.ground().make_callable([F])
        nsat1 = bf1.negate().ground().make_callable([F])
        fact1 = F(1,"ab",(-2,"abc"))
        fact2 = F(-1,"ab",(2,"abc"))

        self.assertFalse(sat1((fact1,))) ; self.assertTrue(nsat1((fact1,)))
        self.assertTrue(sat1((fact2,))) ; self.assertFalse(nsat1((fact2,)))

    #------------------------------------------------------------------------------
    # Test the func_ API functor for creating FunctorComparisonCondition
    # ------------------------------------------------------------------------------
    def test_api_func_(self):

        F = self.F
        G = self.G
        func1 = lambda x, y : x.anum == y.anum

        wrap1 = FunctorComparisonCondition(func1,[F,G])
        wrap2 = func_([F,G],func1)
        self.assertEqual(wrap1,wrap2)
        sat1 = wrap1.ground().make_callable([F,G])
        sat2 = wrap2.ground().make_callable([F,G])

        f1 = F(1,"ab",(-2,"abc"))
        f2 = F(-1,"ab",(2,"abc"))
        g1 = G(1)
        g2 = G(-1)
        self.assertTrue(sat1((f1,g1)))
        self.assertEqual(sat1((f1,g1)),sat2((f1,g1)))

        self.assertFalse(sat1((f2,g1)))
        self.assertEqual(sat1((f2,g1)),sat2((f2,g1)))

    # ------------------------------------------------------------------------------
    # Make ComparisonCallable objects from either any ground comparison condition.
    # ------------------------------------------------------------------------------
    def test_nonapi_make_comparison_callable(self):
        F = self.F
        G = self.G
        func1 = lambda x, y : x == y

        wrap2 = func_([F.anum,G.anum],func1)
        sat1 = make_comparison_callable([G,F], wrap2.ground())
        sat2 = make_comparison_callable([G,F], F.anum == G.anum)

        f1 = F(1,"ab",(-2,"abc"))
        f2 = F(-1,"ab",(2,"abc"))
        g1 = G(1)
        g2 = G(-1)

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
            make_comparison_callable([G], F.anum == G.anum)
        check_errmsg("Invalid signature match", ctx)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------

    def test_nonapi_validate_query_condition_single_predicate(self):
        F = self.F
        vqc = validate_query_condition

        # Some valid conditionals where no simpification is done
        self.assertEqual(vqc((F.anum == 4), (F,)), F.anum == 4)
        self.assertEqual(vqc(~(F.anum == 4), (F,)), ~(F.anum == 4))
        self.assertEqual(vqc((F.anum == 4) & (F.astr == "df"), (F,)),
                         (F.anum == 4) & (F.astr == "df"))
        self.assertEqual(vqc((F.anum == 4) | (F.astr == "df"), (F,)),
                         (F.anum == 4) | (F.astr == "df"))
        self.assertEqual(vqc((F.anum == 4) | \
                             ((F.astr == "df") & ~(F.atuple[0] < 2)), (F,)),
                         (F.anum == 4) | \
                         ((F.astr == "df") & ~(F.atuple[0] < 2)))

        f=lambda x: x + F.anum
        self.assertEqual(vqc(f,[F]), func_([F], f))

        cond1 = F.anum == 4
        cond2 = F.anum == 4
        self.assertEqual(vqc(cond1, (F,)),cond2)

        cond1 = (F.anum == 4) & (F.astr == "df")
        cond2 = (F.anum == 4) & (F.astr == "df")
        self.assertEqual(vqc(cond1, (F,)),cond2)

        cond1 = (F.anum == 4) & f
        cond2 = (F.anum == 4) & func_([F],f)
        self.assertEqual(vqc(cond1, (F,)),cond2)
        self.assertEqual(vqc(cond2, (F,)),cond2)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_negate_query_condition(self):
        F = self.F
        nqc = negate_query_condition

        bf = func_([F.anum],lambda x: x < 2)
        nbf = bf.negate()

        self.assertEqual(nqc(nbf), bf)
        self.assertEqual(nqc(F.anum == 3), F.anum != 3)
        self.assertEqual(nqc(F.anum != 3), F.anum == 3)
        self.assertEqual(nqc(F.anum < 3), F.anum >= 3)
        self.assertEqual(nqc(F.anum <= 3), F.anum > 3)
        self.assertEqual(nqc(F.anum > 3), F.anum <= 3)
        self.assertEqual(nqc(F.anum >= 3), F.anum < 3)

        c = (F.anum == 3) | (bf)
        nc = (F.anum != 3) & (nbf)
        self.assertEqual(nqc(c),nc)
        self.assertEqual(nqc(nc),c)

        c = ~(~(F.anum == 3) | ~(F.anum != 4))
        nc = (F.anum != 3) | (F.anum == 4)
        self.assertEqual(nqc(c),nc)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_normalise_to_nnf_query_condition(self):
        F = self.F
        tonnf = normalise_to_nnf_query_condition

        c = ~(~(F.anum == 3) | ~(F.anum == 4))
        nnfc = (F.anum == 3) & (F.anum == 4)
        self.assertEqual(tonnf(c),nnfc)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_normalise_to_cnf_query_condition(self):
        F = self.F
        tocnf = normalise_to_cnf_query_condition

        # NOTE: Equality test relies on the order - to make this better would
        # need to introduce ordering over comparison conditions.

        f = ((F.anum == 4) & (F.anum == 3)) | (F.anum == 6)
        cnf = ((F.anum == 4) | (F.anum == 6)) & ((F.anum == 3) | (F.anum == 6))
        self.assertEqual(tocnf(f),cnf)

        f = (F.anum == 6) | ((F.anum == 4) & (F.anum == 3))
        cnf = ((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3))
        self.assertEqual(tocnf(f),cnf)

        f = ((F.anum == 6) & (F.anum == 5)) | ((F.anum == 4) & (F.anum == 3))
        cnf = (((F.anum == 6) | (F.anum == 4)) & ((F.anum == 6) | (F.anum == 3))) & \
              (((F.anum == 5) | (F.anum == 4)) & ((F.anum == 5) | (F.anum == 3)))
        self.assertEqual(tocnf(f),cnf)

    # ------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------
    def test_nonapi_clause(self):
        F = self.F
        G = self.G

        c1 = Clause([F.anum == 4, F.astr == "b", F.atuple[0] == 6])
        self.assertTrue(c1.is_ground)
        self.assertEqual(set([hashable_path(p) for p in [F.anum,F.astr,F.atuple[0]]]),
                         c1.hashable_paths)
        self.assertEqual(c1.predicates,set([F]))

        c1 = Clause([G.anum == ph1_, F.astr == "b", F.atuple[0] == 6])
        self.assertFalse(c1.is_ground)
        self.assertEqual(set([hashable_path(p) for p in [G.anum,F.astr,F.atuple[0]]]),
                         c1.hashable_paths)
        self.assertEqual(c1.predicates,set([F,G]))

        #### FIXUP
        return
        
        f = func_([F.anum], lambda x : x == 2)
        c1 = Clause([f])
        self.assertTrue(c1.is_ground)
        self.assertEqual(set([hashable_path(p) for p in [F.anum]]), c1.hashable_paths)
        self.assertEqual(c1.predicates,set([F]))

    def test_nonapi_normalise_query_condition(self):
        F = self.F
        tonorm = normalise_query_condition

#        return
    
        f = F.anum == 4
        self.assertEqual(tonorm(f), [Clause([f])])

        f = func_([F.anum], lambda x : x == 2)
        self.assertEqual(tonorm(f), [Clause([f])])

        f = ((F.anum == 4) & (F.anum == 3)) | (F.anum == 6)
        clauses = [Clause([F.anum == 4, F.anum == 6]),
                   Clause([F.anum == 3, F.anum == 6])]
        norm = tonorm(f)
        self.assertEqual(tonorm(f),clauses)



#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
