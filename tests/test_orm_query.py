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
    Predicate, ComplexTerm, path, hashable_path

# Implementation imports
from clorm.orm.core import QueryCondition

# Official Clorm API imports for the fact base components
from clorm.orm import desc, asc, not_, and_, or_, \
    ph_, ph1_, ph2_

from clorm.orm.query import PositionalPlaceholder, NamedPlaceholder, \
    check_query_condition, simplify_query_condition, \
    instantiate_query_condition, evaluate_query_condition

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'QueryConditionTestCase'
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
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
