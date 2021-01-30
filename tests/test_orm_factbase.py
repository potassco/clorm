# ------------------------------------------------------------------------------
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

# Official Clorm API imports for the fact base components
from clorm.orm import FactBase, desc, asc, not_, and_, or_, \
    ph_, ph1_, ph2_

# Implementation imports
from clorm.orm.factbase import _FactIndex, _FactMap, _FactSet, \
    make_first_join_query, make_chained_join_query

from clorm.orm.queryplan import PositionalPlaceholder, NamedPlaceholder, \
    check_query_condition, simplify_query_condition, \
    instantiate_query_condition, evaluate_query_condition

from clorm.orm.queryplan import process_which, process_join, make_query_plan, \
    simple_query_join_order, make_query_alignment_functor

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'FactIndexTestCase',
    'FactMapTestCase',
    'FactBaseTestCase',
    'QueryTestCase',
    'SelectTestCase',
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Test the _FactIndex class
#------------------------------------------------------------------------------

class FactIndexTestCase(unittest.TestCase):
    def setUp(self):
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        self.Afact = Afact
        self.Bfact = Bfact

    def test_create(self):
        Afact = self.Afact
        fi1 = _FactIndex(Afact.num1)
        self.assertTrue(fi1)

        # Should only accept fields
        with self.assertRaises(TypeError) as ctx:
            f2 = _FactIndex(1)
        with self.assertRaises(TypeError) as ctx:
            f2 = _FactIndex(Afact)

    def test_add(self):
        Afact = self.Afact
        Bfact = self.Bfact
        fi1 = _FactIndex(Afact.num1)
        fi2 = _FactIndex(Afact.str1)
        self.assertEqual(fi1.keys, [])

        fi1.add(Afact(num1=1, str1="c"))
        fi2.add(Afact(num1=1, str1="c"))
        self.assertEqual(fi1.keys, [1])
        self.assertEqual(fi2.keys, ["c"])

        fi1.add(Afact(num1=2, str1="b"))
        fi2.add(Afact(num1=2, str1="b"))
        self.assertEqual(fi1.keys, [1,2])
        self.assertEqual(fi2.keys, ["b","c"])
        fi1.add(Afact(num1=3, str1="b"))
        fi2.add(Afact(num1=3, str1="b"))
        self.assertEqual(fi1.keys, [1,2,3])
        self.assertEqual(fi2.keys, ["b","c"])

    def test_remove(self):
        Afact = self.Afact
        Bfact = self.Bfact

        af1a = Afact(num1=1, str1="a")
        af2a = Afact(num1=2, str1="a")
        af2b = Afact(num1=2, str1="b")
        af3a = Afact(num1=3, str1="a")
        af3b = Afact(num1=3, str1="b")

        fi = _FactIndex(Afact.num1)
        for f in [ af1a, af2a, af2b, af3a, af3b ]: fi.add(f)
        self.assertEqual(fi.keys, [1,2,3])

        fi.remove(af1a)
        self.assertEqual(fi.keys, [2,3])

        fi.discard(af1a)
        with self.assertRaises(KeyError) as ctx:
            fi.remove(af1a)

        fi.remove(af2a)
        self.assertEqual(fi.keys, [2,3])

        fi.remove(af3a)
        self.assertEqual(fi.keys, [2,3])

        fi.remove(af2b)
        self.assertEqual(fi.keys, [3])

        fi.remove(af3b)
        self.assertEqual(fi.keys, [])

    def test_find(self):
        Afact = self.Afact

        af1a = Afact(num1=1, str1="a")
        af2a = Afact(num1=2, str1="a")
        af2b = Afact(num1=2, str1="b")
        af3a = Afact(num1=3, str1="a")
        af3b = Afact(num1=3, str1="b")

        fi = _FactIndex(Afact.num1)
        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fi.add(f)

        self.assertEqual(set(fi.find(operator.eq, 1)), set([af1a]))
        self.assertEqual(set(fi.find(operator.eq, 2)), set([af2a, af2b]))
        self.assertEqual(set(fi.find(operator.ne, 5)), set(allfacts))
        self.assertEqual(set(fi.find(operator.eq, 5)), set([]))
        self.assertEqual(set(fi.find(operator.lt, 1)), set([]))
        self.assertEqual(set(fi.find(operator.lt, 2)), set([af1a]))
        self.assertEqual(set(fi.find(operator.le, 2)), set([af1a, af2a, af2b]))
        self.assertEqual(set(fi.find(operator.gt, 2)), set([af3a, af3b]))
        self.assertEqual(set(fi.find(operator.ge, 3)), set([af3a, af3b]))
        self.assertEqual(set(fi.find(operator.gt, 3)), set([]))

    def test_clear(self):
        Afact = self.Afact
        fi = _FactIndex(Afact.num1)
        fi.add(Afact(num1=1, str1="a"))
        fi.clear()
        self.assertEqual(fi.keys,[])


    #--------------------------------------------------------------------------
    # Test the support for indexes of subfields
    #--------------------------------------------------------------------------
    def test_subfields(self):
        class CT(ComplexTerm):
            num1=IntegerField()
            str1=StringField()
        class Fact(Predicate):
            ct1=CT.Field()
            ct2=(IntegerField(),IntegerField())

        fi1 = _FactIndex(Fact.ct1.num1)
        fi2 = _FactIndex(Fact.ct2[1])
        fi3 = _FactIndex(Fact.ct1)

        f1=Fact(CT(10,"a"),(1,4))
        f2=Fact(CT(20,"b"),(2,3))
        f3=Fact(CT(30,"c"),(5,2))
        f4=Fact(CT(40,"d"),(6,1))

        fi1.add(f1); fi2.add(f1); fi3.add(f1)
        fi1.add(f2); fi2.add(f2); fi3.add(f2)
        fi1.add(f3); fi2.add(f3); fi3.add(f3)
        fi1.add(f4); fi2.add(f4); fi3.add(f4)

        self.assertEqual(fi1.keys, [10,20,30,40])
        self.assertEqual(fi2.keys, [1,2,3,4])
        self.assertEqual(set(fi3.keys),
                         set([CT(10,"a"),CT(20,"b"),CT(30,"c"),CT(40,"d")]))

#------------------------------------------------------------------------------
# Test the _FactMap and Select _Delete class
#------------------------------------------------------------------------------

class FactMapTestCase(unittest.TestCase):
    def setUp(self):

        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        self.Afact = Afact
        self.Bfact = Bfact

    def test_init(self):
        Afact = self.Afact
        Bfact = self.Bfact

        fm1 = _FactMap(Afact)
        self.assertEqual(fm1.indexes, ())

        fm1 = _FactMap(Afact, [Afact.num1, Afact.str1])
        self.assertEqual(fm1.indexes, (Afact.num1, Afact.str1))

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(1)

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(Afact.num1)

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(Afact, [Bfact.num1])

    def test_add_and_container_ops(self):
        Afact = self.Afact
        fm = _FactMap(Afact, [Afact.num1, Afact.str1])

        af1a = Afact(num1=1, str1="a", str2="a")
        af2a = Afact(num1=2, str1="a", str2="a")
        af2b = Afact(num1=2, str1="b", str2="a")
        af3a = Afact(num1=3, str1="a", str2="c")
        af3b = Afact(num1=3, str1="b", str2="c")

        # Test add() and  __contains__()
        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fm.add(f)
        self.assertTrue(af2b in fm)
        self.assertTrue(af2a in fm)
        self.assertFalse(Afact(num1=1, str1="a", str2="b") in fm)
        for f in allfacts: fm.add(f)
        self.assertTrue(af2b in fm)

        # Test __bool__ and __len__
        fm2 = _FactMap(Afact, [Afact.num1, Afact.str1])
        self.assertTrue(bool(fm))
        self.assertFalse(fm2)
        self.assertEqual(len(fm), 5)
        self.assertEqual(len(fm2), 0)

        # Test __iter__
        self.assertEqual(set(fm), set(allfacts))
        self.assertEqual(set(fm2), set())

    def test_remove_discard_clear(self):
        Afact = self.Afact
        fm = _FactMap(Afact, [Afact.num1, Afact.str1])

        af1a = Afact(num1=1, str1="a", str2="a")
        af2a = Afact(num1=2, str1="a", str2="a")
        af2b = Afact(num1=2, str1="b", str2="a")
        af3a = Afact(num1=3, str1="a", str2="c")
        af3b = Afact(num1=3, str1="b", str2="c")

        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fm.add(f)

        fm.remove(af1a)
        fm.discard(af1a)
        with self.assertRaises(KeyError) as ctx:
            fm.remove(af1a)

        fm.clear()
        self.assertFalse(af1a in fm)
        self.assertFalse(af2a in fm)
        self.assertFalse(af2b in fm)
        self.assertFalse(af3a in fm)
        self.assertFalse(af3b in fm)

    def test_set_comparison_ops(self):
        Afact = self.Afact
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm3 = _FactMap(Afact)
        fm1_alt = _FactMap(Afact)

        af1 = Afact(num1=1, str1="a", str2="a")
        af2 = Afact(num1=2, str1="a", str2="a")
        af3 = Afact(num1=3, str1="b", str2="a")
        af4 = Afact(num1=4, str1="a", str2="c")
        af5 = Afact(num1=5, str1="b", str2="c")

        fm1.add([af1,af2])
        fm2.add([af1,af2,af3])
        fm3.add([af1,af2,af3,af4])

        fm1_alt.add([af1,af2])

        # Test __eq__ and __ne__
        self.assertTrue(fm1 == fm1_alt)
        self.assertTrue(fm1 != fm2)

        # Test __lt__, __le__, __gt__, __ge__
        self.assertFalse(fm1 < fm1_alt)
        self.assertFalse(fm1 > fm1_alt)
        self.assertTrue(fm1 <= fm1_alt)
        self.assertTrue(fm1 >= fm1_alt)
        self.assertTrue(fm1 < fm2)
        self.assertFalse(fm1 > fm2)
        self.assertTrue(fm1 <= fm2)
        self.assertFalse(fm1 >= fm2)
        self.assertFalse(fm2 < fm1)
        self.assertFalse(fm2 <= fm1)

    def test_set_ops(self):
        Afact = self.Afact
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm3 = _FactMap(Afact)
        fm4 = _FactMap(Afact)
        fm5 = _FactMap(Afact)
        fm6 = _FactMap(Afact)
        fm7 = _FactMap(Afact)

        af1 = Afact(num1=1, str1="a", str2="a")
        af2 = Afact(num1=2, str1="b", str2="b")
        af3 = Afact(num1=3, str1="c", str2="c")
        af4 = Afact(num1=4, str1="d", str2="d")
        af5 = Afact(num1=5, str1="e", str2="e")

        fm1.add([af1,af2])
        fm2.add([af2,af3])
        fm3.add([af3,af4])
        fm4.add([af1,af2,af3,af4])
        fm5.add([])
        fm6.add([af1])
        fm7.add([af1,af3])

        fmo1=fm1.union(fm2,fm3)
        fmo2=fm1.intersection(fm2,fm3)
        fmo3=fm1.difference(fm2)
        fmo4=fm1.symmetric_difference(fm2)
        self.assertEqual(fm4,fmo1)
        self.assertEqual(fm5,fmo2)
        self.assertEqual(fm6,fmo3)
        self.assertEqual(fm7,fmo4)

        # Symmetric difference too many arguments
        with self.assertRaises(TypeError) as ctx:
            fmo4=fm3.symmetric_difference(fm1,fm4)

        # Test copy function
        r=fm1.copy() ; self.assertEqual(fm1,r)

        # Update function
        fm6.update(fm3,fm7)
        self.assertEqual(fm6.facts(), set([af1,af3,af3,af4]))

        # Intersection update function
        fm6.intersection_update(fm3,fm7)
        self.assertEqual(fm6.facts(), set([af3]))

        # Difference update function
        fm7.difference_update(fm6,fm5)
        self.assertEqual(fm7.facts(), set([af1]))
        fm7.difference_update(fm3)
        self.assertEqual(fm7.facts(), set([af1]))

        # Symmetric difference update function
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm1.add([af1,af2,af3])
        fm2.add([af2,af3,af4])
        fm1.symmetric_difference_update(fm2)
        self.assertEqual(fm1.facts(), set([af1,af4]))

#------------------------------------------------------------------------------
# Test the FactBase
#------------------------------------------------------------------------------
class FactBaseTestCase(unittest.TestCase):
    def setUp(self):

        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Cfact(Predicate):
            num1=IntegerField()

        self._Afact = Afact
        self._Bfact = Bfact
        self._Cfact = Cfact

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_factbase_normal_init(self):

        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(1,10,"bbb")
        bf1 = Bfact(1,"aaa", "bbb")
        cf1 = Cfact(1)

        fs1 = FactBase([af1,bf1,cf1])
        self.assertTrue(af1 in fs1)
        self.assertTrue(bf1 in fs1)
        self.assertTrue(cf1 in fs1)

        fs2 = FactBase()
        fs2.add([af1,bf1,cf1])
        self.assertTrue(af1 in fs2)
        self.assertTrue(bf1 in fs2)
        self.assertTrue(cf1 in fs2)

        fs3 = FactBase()
        fs3.add([af1])
        asp_str = fs3.asp_str().lstrip().rstrip()
        self.assertEqual(asp_str, "{}.".format(str(af1)))

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_delayed_init(self):

        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(1,10,"bbb")
        bf1 = Bfact(1,"aaa","bbb")
        cf1 = Cfact(1)

        fs1 = FactBase(lambda: [af1,bf1])
        self.assertTrue(fs1._delayed_init)
        self.assertTrue(af1 in fs1)
        self.assertFalse(cf1 in fs1)
        fs1.add(cf1)
        self.assertTrue(bf1 in fs1)
        self.assertTrue(cf1 in fs1)

        fs2 = FactBase([af1,bf1])
        self.assertFalse(fs2._delayed_init)


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_container_ops(self):

        Afact = self._Afact
        Bfact = self._Bfact

        delayed_init=lambda: []

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        bf1 = Bfact(num1=1, str1="1", str2="a")

        fb = FactBase([af1])
        fb3 = FactBase(facts=lambda: [])
        self.assertTrue(af1 in fb)
        self.assertFalse(af2 in fb)
        self.assertFalse(bf1 in fb)
        self.assertFalse(bf1 in fb3)

        # Test __bool__
        fb2 = FactBase()
        fb3 = FactBase(facts=lambda: [])
        self.assertTrue(fb)
        self.assertFalse(fb2)
        self.assertFalse(fb3)

        # Test __len__
        self.assertEqual(len(fb2), 0)
        self.assertEqual(len(fb), 1)
        self.assertEqual(len(FactBase([af1,af2])),2)
        self.assertEqual(len(FactBase(facts=lambda: [af1,af2, bf1])), 3)

        # Test __iter__
        input = set([])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2,bf1])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2,bf1])
        self.assertEqual(set(FactBase(facts=lambda: input)), input)

        # Test pop()
        fb1 = FactBase([af1])
        fb2 = FactBase([bf1])
        fb3 = FactBase([af1,bf1])
        f = fb3.pop()
        if f == af1:
            self.assertEqual(fb3,fb2)
            self.assertEqual(fb3.pop(), bf1)
        else:
            self.assertEqual(fb3,fb1)
            self.assertEqual(fb3.pop(), af1)
        self.assertFalse(fb3)

        # popping from an empty factbase should raise error
        with self.assertRaises(KeyError) as ctx: fb3.pop()


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_comparison_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        bf1 = Bfact(num1=1, str1="1", str2="a")

        fb1 = FactBase([af1,af2])
        fb2 = FactBase([af1,af2,bf1])
        fb3 = FactBase([af1,af2,bf1])
        fb4 = FactBase(facts=lambda: [af1,af2])
        fb5 = FactBase([af2, bf1])

        self.assertTrue(fb1 != fb2)
        self.assertFalse(fb1 == fb2)
        self.assertFalse(fb2 == fb5) # a case with same predicates keys

        self.assertTrue(fb1 == fb4)
        self.assertFalse(fb1 != fb4)
        self.assertTrue(fb2 == fb3)
        self.assertFalse(fb2 != fb3)

        # Test comparison against sets and lists
        self.assertTrue(fb2 == [af1,af2,bf1])
        self.assertTrue([af1,af2,bf1] == fb2)
        self.assertTrue(fb2 == set([af1,af2,bf1]))


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_set_comparison_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        af3 = Afact(num1=1, str1="1", str2="c")
        bf1 = Bfact(num1=1, str1="1", str2="a")
        bf2 = Bfact(num1=1, str1="1", str2="b")
        bf3 = Bfact(num1=1, str1="1", str2="c")

        fb1 = FactBase([af1,af2,bf1])
        fb2 = FactBase([af1,af2,bf1,bf2])
        fb3 = FactBase()

        self.assertTrue(fb1 <= fb1)
        self.assertTrue(fb1 < fb2)
        self.assertTrue(fb1 <= fb2)
        self.assertTrue(fb2 > fb1)
        self.assertTrue(fb2 >= fb1)

        self.assertFalse(fb1 > fb1)
        self.assertFalse(fb1 >= fb2)
        self.assertFalse(fb1 > fb2)
        self.assertFalse(fb2 <= fb1)
        self.assertFalse(fb2 < fb1)

        # Test comparison against sets and lists
        self.assertTrue(fb1 <= [af1,af2,bf1])
        self.assertTrue(fb1 < [af1,af2,bf1,bf2])
        self.assertTrue(fb1 <= [af1,af2,bf1,bf2])
        self.assertTrue(fb2 > [af1,af2,bf1])
        self.assertTrue(fb2 >= [af1,af2,bf1])
        self.assertTrue([af1,af2,bf1,bf2] >= fb1)


    #--------------------------------------------------------------------------
    # We want to ignore any insertion order when comparing fact bases. So
    # equality should return true iff two fact bases have the same facts.
    # --------------------------------------------------------------------------
    def test_equality_fb_different_order(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        af3 = Afact(num1=1, str1="1", str2="c")
        bf1 = Bfact(num1=1, str1="1", str2="a")
        bf2 = Bfact(num1=1, str1="1", str2="b")
        bf3 = Bfact(num1=1, str1="1", str2="c")

        inlist = [af1,af2,af3,bf1,bf2,bf3]
        fb1 = FactBase(inlist)
        inlist.reverse()
        fb2 = FactBase(inlist)

        self.assertTrue(fb1 == fb2)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_set_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        af3 = Afact(num1=1, str1="1", str2="c")
        bf1 = Bfact(num1=1, str1="1", str2="a")
        bf2 = Bfact(num1=1, str1="1", str2="b")
        bf3 = Bfact(num1=1, str1="1", str2="c")
        cf1 = Cfact(num1=1)
        cf2 = Cfact(num1=2)
        cf3 = Cfact(num1=3)

        fb0 = FactBase()
        fb1 = FactBase([af1,bf1])
        fb1_alt = FactBase(lambda: [af1,bf1])
        fb2 = FactBase([bf1,bf2])
        fb3 = FactBase([af2,bf3])
        fb4 = FactBase([af1,af2,bf1,bf2,bf3])
        fb5 = FactBase([af1,bf1,bf2])

        # Test union
        r=fb1.union(fb1); self.assertEqual(r,fb1)
        r=fb1.union(fb1_alt); self.assertEqual(r,fb1)
        r=fb0.union(fb1,fb2); self.assertEqual(r,fb5)
        r=fb1.union(fb2,[af2,bf3]); self.assertEqual(r,fb4)
        r = fb1 | fb2 | [af2,bf3]; self.assertEqual(r,fb4)  # overload version

        # Test intersection
        r=fb0.intersection(fb1); self.assertEqual(r,fb0)
        r=fb1.intersection(fb1_alt); self.assertEqual(r,fb1)
        r=fb1.intersection(fb2); self.assertEqual(r,FactBase([bf1]))
        r=fb4.intersection(fb2,fb3); self.assertEqual(r,fb0)
        r=fb4.intersection([af2,bf3]); self.assertEqual(r,fb3)
        r=fb4.intersection(FactBase([af1])); self.assertEqual(r,FactBase([af1]))

        r = fb5 & [af1,af2,bf1] ; self.assertEqual(r,[af1,bf1])

        # Test difference
        r=fb0.difference(fb1); self.assertEqual(r,fb0)
        r=fb1.difference(fb1_alt); self.assertEqual(r,fb0)
        r=fb2.difference([af1,bf1]); self.assertEqual(r,FactBase([bf2]))
        r=fb4.difference(fb5); self.assertEqual(r, FactBase([af2,bf3]))
        r = fb4 - fb5;  self.assertEqual(r, FactBase([af2,bf3]))

        # Test symmetric difference
        r=fb1.symmetric_difference(fb1_alt); self.assertEqual(r,fb0)
        r=fb1.symmetric_difference([af2,bf3]); self.assertEqual(r,FactBase([af1,bf1,af2,bf3]))
        r =fb1 ^ [af2,bf3]; self.assertEqual(r,FactBase([af1,bf1,af2,bf3]))

        # Test copy
        r=fb1.copy(); self.assertEqual(r,fb1)

        # Test update()
        fb=FactBase([af1,af2])
        fb.update(FactBase([af3,bf1]),[cf1,cf2])
        self.assertEqual(fb, FactBase([af1,af2,af3,bf1,cf1,cf2]))
        fb=FactBase([af1,af2])
        fb |= [af3,bf1]
        self.assertEqual(fb,FactBase([af1,af2,af3,bf1]))

        # Test intersection()
        fb=FactBase([af1,af2,bf1,cf1])
        fb.intersection_update(FactBase([af1,bf2]))
        self.assertEqual(fb, FactBase([af1]))
        fb=FactBase([af1,af2,bf1,cf1])
        fb.intersection_update(FactBase([af1,bf2]),[af1])
        self.assertEqual(fb, FactBase([af1]))
        fb=FactBase([af1,af2,bf1,cf1])
        fb &= [af1,bf2]
        self.assertEqual(fb, FactBase([af1]))

        # Test difference_update()
        fb=FactBase([af1,af2,bf1])
        fb.difference_update(FactBase([af2,bf2]),[bf3,cf1])
        self.assertEqual(fb, FactBase([af1,bf1]))
        fb=FactBase([af1,af2,bf1])
        fb -= [af2,bf1]
        self.assertEqual(fb, FactBase([af1]))

        # Test symmetric_difference_update()
        fb=FactBase([af1,af2,bf1])
        fb.symmetric_difference_update(FactBase([af2,bf2]))
        self.assertEqual(fb, FactBase([af1,bf1,bf2]))
        fb=FactBase([af1,af2,bf1])
        fb ^= FactBase([cf2])
        self.assertEqual(fb, FactBase([af1,af2,bf1,cf2]))

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_factbase_copy(self):
        class Afact(Predicate):
            num=IntegerField(index=True)
            pair=(IntegerField, IntegerField(index=True))

        af1=Afact(num=5,pair=(1,2))
        af2=Afact(num=6,pair=(1,2))
        af3=Afact(num=5,pair=(2,3))

        fb1=FactBase([af1,af2,af3],indexes=Afact.meta.indexes)
        fb2=FactBase(list(fb1))
        fb3=FactBase(fb1)

        # The data is the same so they are all equal
        self.assertEqual(fb1, fb2)
        self.assertEqual(fb2, fb3)

        # But the indexes can be different
        self.assertEqual(list(fb1.indexes), list(Afact.meta.indexes))
        self.assertEqual(list(fb2.indexes), [])
        self.assertEqual(list(fb3.indexes), list(fb1.indexes))


    #--------------------------------------------------------------------------
    # Test deterministic iteration. Namely, that there is determinism when
    # iterating over two factbases that have been constructed identically
    # --------------------------------------------------------------------------
    def test_factbase_iteration(self):
        class Afact(Predicate):
            num=IntegerField
        class Bfact(Predicate):
            num=IntegerField
        class Cfact(Predicate):
            num=IntegerField

        fb=FactBase()
        bfacts = [Bfact(i) for i in range(0,100)]
        cfacts = [Cfact(i) for i in range(0,100)]
        afacts = [Afact(i) for i in range(0,100)]
        allfacts = bfacts+cfacts+afacts
        fb.add(bfacts)
        fb.add(cfacts)
        fb.add(afacts)

        # Make sure all the different ways to get the list of fact provide the
        # same ordering as the original creation list
        output=list(fb)
        self.assertEqual(allfacts,fb.facts())
        self.assertEqual(allfacts,output)
        self.assertEqual(str(fb), "{" + ", ".join([str(f) for f in allfacts]) + "}")

        tmpstr = "".join(["{}.\n".format(f) for f in allfacts])
        self.assertEqual(tmpstr.strip(), fb.asp_str().strip())

    #--------------------------------------------------------------------------
    # Test the asp output string
    # --------------------------------------------------------------------------
    def test_factbase_aspstr_width(self):
        class A(Predicate):
            n=IntegerField
        class C(Predicate):
            s=StringField
            class Meta: name="a_very_long_predicate_name_that_cause_wrapping_well"

        fb=FactBase()
        afacts = [A(i) for i in range(0,10)]
        bfacts = [C("A long parameter for wrapping {}".format(i)) for i in range(0,10)]
        allfacts = afacts+bfacts
        fb.add(afacts)

        aspstr=fb.asp_str(width=30)
        afactsstr="a(0). a(1). a(2). a(3). a(4).\na(5). a(6). a(7). a(8). a(9).\n"
        self.assertEqual(aspstr,afactsstr)

        bfactsstr = "\n".join(["{}.".format(f) for f in bfacts]) + "\n"
        fb.add(bfacts)
        aspstr=fb.asp_str(width=30)
        self.assertEqual(aspstr,afactsstr+bfactsstr)

        aspstr=fb.asp_str(width=30,commented=True)
        afactspre="% FactBase predicate: a/1\n"
        bfactspre="% FactBase predicate: {}/1\n".format(C.meta.name)
        matchstr = afactspre+afactsstr + "\n" + bfactspre+bfactsstr
        self.assertEqual(aspstr,matchstr)









#------------------------------------------------------------------------------
# Test functions that manipulate query conditional and evaluate the conditional
# w.r.t a fact.
# ------------------------------------------------------------------------------

class QueryTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

        self.factsets = {}
        self.indexes = {}

        factset = _FactSet()
        factindex = _FactIndex(G.astr)
        for f in [G(1,"a"),G(1,"foo"),G(5,"a"),G(5,"foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(G.astr)] = factindex
        self.factsets[G] = factset

        factset = _FactSet()
        factindex = _FactIndex(F.anum)
        for f in [F(1,"a"),F(1,"foo"),F(5,"a"),F(5,"foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(F.anum)] = factindex
        self.factsets[F] = factset


    def test_make_first_join_query(self):
        def strip(it): return [f for f, in it]

        G = self.G
        pw = process_which

        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.anum > 4) & (G.astr == "foo"),[G])
        qp1 = make_query_plan(simple_query_join_order,[G.astr],
                              [G],[],which1)

        query1 = make_first_join_query(qp1[0], factsets, indexes)
        self.assertEqual(set(strip(query1())), set([G(5,"foo")]))


        which2 = pw((G.anum > 4) | (G.astr == "foo"),[G])
        qp2 = make_query_plan(simple_query_join_order,[G.astr],
                              [G],[],which2)

        query2 = make_first_join_query(qp2[0], factsets, indexes)
        self.assertEqual(set(strip(query2())),
                         set([G(1,"foo"), G(5,"a"), G(5,"foo")]))


    def test_make_chained_join_query(self):
        def align_facts(insig, outsig, it):
            f = make_query_alignment_functor(insig,outsig)
            return [ f(t) for t in it ]

        Fp = path(self.F)
        Gp = path(self.G)
        F = self.F
        G = self.G
        pw = process_which

        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.anum > 4) & (G.astr == "foo") & (F.anum == 1),[G,F])
        qp1 = make_query_plan(simple_query_join_order,[G.astr,F.anum],
                              [G,F],[],which1)
        #        print("\nQP:\n{}".format(qp1))
        query1 = make_first_join_query(qp1[0], factsets, indexes)
        query2 = make_chained_join_query(qp1[1], query1, factsets, indexes)
        output = align_facts(qp1.output_signature, (Fp,Gp), query2())
        #        print("RESULT: {}".format(output))
        self.assertEqual(set(output),
                         set([(F(1,"a"),G(5,"foo")), (F(1,"foo"),G(5,"foo"))]))


        which1 = pw((F.anum > 4) & (F.astr == "foo") & (G.anum == 1),[F,G])
        qp1 = make_query_plan(simple_query_join_order,[G.astr,F.anum],
                              [F,G],[],which1)
        #print("\nQP:\n{}".format(qp1))
        query1 = make_first_join_query(qp1[0], factsets, indexes)
        query2 = make_chained_join_query(qp1[1], query1, factsets, indexes)
        output = align_facts(qp1.output_signature, (Fp,Gp), query2())
        #print("RESULT: {}".format(output))
        self.assertEqual(set(query2()),
                         set([(F(5,"foo"),G(1,"a")), (F(5,"foo"),G(1,"foo"))]))


    def test_make_chained_join_query(self):
        def align_facts(insig, outsig, it):
            f = make_query_alignment_functor(insig,outsig)
            return [ f(t) for t in it ]

        Fp = path(self.F)
        Gp = path(self.G)
        F = self.F
        G = self.G
        indexes = self.indexes
        factsets = self.factsets
        pw = process_which
        pj = process_join

        return
        which2 = pw((G.anum > 4) & (G.astr == "foo"),[G])
        joins = pj([F.anum == G.anum],[F,G])
        qp2 = make_query_plan(simple_query_join_order,[G.astr,F.anum],
                              [G,F],[],which2)

        query1 = make_first_join_query(qp2[0], factsets, indexes)
        query2 = make_c_join_query(qp2[1], factsets, indexes)

        print("HERE1: {}".format(list(query1())))

        print("HERE2: {}".format(list(query2(query1))))
        self.assertEqual(set(query2(query1)),
                         set([(G(5,"foo"),F(1,"a")), (G(5,"foo"),F(1,"foo"))]))


        FA = alias(F)

#------------------------------------------------------------------------------
# Test the Select class
#------------------------------------------------------------------------------

class SelectTestCase(unittest.TestCase):
    def setUp(self):
        pass

    #--------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    #--------------------------------------------------------------------------
    def test_placeholder_instantiation(self):

        # Named placeholder with and without default
        p = ph_("test")
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertFalse(p.has_default)
        self.assertEqual(p.default,None)
        self.assertEqual(str(p), "ph_(\"test\")")

        p = ph_("test",default=0)
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default,0)
        self.assertEqual(str(p), "ph_(\"test\",0)")

        p = ph_("test",default=None)
        self.assertEqual(type(p), NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default,None)

        # Positional placeholder
        p = ph_(1)
        self.assertEqual(type(p), PositionalPlaceholder)
        self.assertEqual(p.posn, 0)
        self.assertEqual(str(p), "ph1_")

        # Some bad initialisation
        with self.assertRaises(TypeError) as ctx: ph_(1,2)
        with self.assertRaises(TypeError) as ctx: ph_("a",2,3)
        with self.assertRaises(TypeError) as ctx: ph_("a",default=2,arg=3)

    #--------------------------------------------------------------------------
    #   Test that the select works
    #--------------------------------------------------------------------------
    def test_select_over_factmap(self):
        class Afact1(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()
            class Meta: name = "afact"

        fm1 = _FactMap(Afact1, [Afact1.num1,Afact1.str1])
        fm2 = _FactMap(Afact1)
        f1 = Afact1(1,1,"1")
        f3 = Afact1(3,3,"3")
        f4 = Afact1(4,4,"4")
        f42 = Afact1(4,42,"42")
        f10 = Afact1(10,10,"10")
        fm1.add(f1)
        fm1.add(f3)
        fm1.add(f4)
        fm1.add(f42)
        fm1.add(f10)
        fm2.add(f1)
        fm2.add(f3)
        fm2.add(f4)
        fm2.add(f42)
        fm2.add(f10)

        s1_all = fm1.select()
        s1_num1_eq_4 = fm1.select().where(Afact1.num1 == 4)
        s1_num1_ne_4 = fm1.select().where(Afact1.num1 != 4)
        s1_num1_lt_4 = fm1.select().where(Afact1.num1 < 4)
        s1_num1_le_4 = fm1.select().where(Afact1.num1 <= 4)
        s1_num1_gt_4 = fm1.select().where(Afact1.num1 > 4)
        s1_num1_ge_4 = fm1.select().where(Afact1.num1 >= 4)
        s1_str1_eq_4 = fm1.select().where(Afact1.str1 == "4")
        s1_num2_eq_4 = fm1.select().where(Afact1.num2 == 4)

        s2_all = fm1.select()
        s2_num1_eq_4 = fm2.select().where(Afact1.num1 == 4)
        s2_num1_ne_4 = fm2.select().where(Afact1.num1 != 4)
        s2_num1_lt_4 = fm2.select().where(Afact1.num1 < 4)
        s2_num1_le_4 = fm2.select().where(Afact1.num1 <= 4)
        s2_num1_gt_4 = fm2.select().where(Afact1.num1 > 4)
        s2_num1_ge_4 = fm2.select().where(Afact1.num1 >= 4)
        s2_str1_eq_4 = fm2.select().where(Afact1.str1 == "4")
        s2_num2_eq_4 = fm2.select().where(Afact1.num2 == 4)

        self.assertFalse(s1_all._debug())
        self.assertEqual(s1_num1_eq_4._debug()[0], Afact1.num1)
        self.assertTrue(s1_num1_ne_4._debug())
        self.assertTrue(s1_num1_lt_4._debug())
        self.assertTrue(s1_num1_le_4._debug())
        self.assertTrue(s1_num1_gt_4._debug())
        self.assertTrue(s1_num1_ge_4._debug())
        self.assertEqual(s1_str1_eq_4._debug()[0], Afact1.str1)
        self.assertFalse(s1_num2_eq_4._debug())

        self.assertFalse(s2_all._debug())
        self.assertFalse(s2_num1_eq_4._debug())
        self.assertFalse(s2_num1_ne_4._debug())
        self.assertFalse(s2_num1_lt_4._debug())
        self.assertFalse(s2_num1_le_4._debug())
        self.assertFalse(s2_num1_gt_4._debug())
        self.assertFalse(s2_num1_ge_4._debug())
        self.assertFalse(s2_str1_eq_4._debug())
        self.assertFalse(s2_num2_eq_4._debug())

        self.assertEqual(set(list(s1_all.get())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s1_num1_eq_4.get())), set([f4,f42]))
        self.assertEqual(set(list(s1_num1_ne_4.get())), set([f1,f3,f10]))
        self.assertEqual(set(list(s1_num1_lt_4.get())), set([f1,f3]))
        self.assertEqual(set(list(s1_num1_le_4.get())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s1_num1_gt_4.get())), set([f10]))
        self.assertEqual(set(list(s1_num1_ge_4.get())), set([f4,f42,f10]))
        self.assertEqual(s1_str1_eq_4.get_unique(), f4)
        self.assertEqual(s1_num2_eq_4.get_unique(), f4)

        self.assertEqual(set(list(s2_all.get())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s2_num1_eq_4.get())), set([f4,f42]))
        self.assertEqual(set(list(s2_num1_ne_4.get())), set([f1,f3,f10]))
        self.assertEqual(set(list(s2_num1_lt_4.get())), set([f1,f3]))
        self.assertEqual(set(list(s2_num1_le_4.get())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s2_num1_gt_4.get())), set([f10]))
        self.assertEqual(set(list(s2_num1_ge_4.get())), set([f4,f42,f10]))
        self.assertEqual(s2_str1_eq_4.get_unique(), f4)
        self.assertEqual(s2_num2_eq_4.get_unique(), f4)


        # Test simple conjunction select
        s1_conj1 = fm1.select().where(Afact1.str1 == "42", Afact1.num1 == 4)
        s1_conj2 = fm1.select().where(Afact1.num1 == 4, Afact1.str1 == "42")
        s1_conj3 = fm1.select().where(lambda x: x.str1 == "42", Afact1.num1 == 4)

        self.assertEqual(s1_conj1._debug()[0], Afact1.num1)
        self.assertEqual(s1_conj2._debug()[0], Afact1.num1)
        self.assertEqual(s1_conj3._debug()[0], Afact1.num1)

        self.assertEqual(s1_conj1.get_unique(), f42)
        self.assertEqual(s1_conj2.get_unique(), f42)
        self.assertEqual(s1_conj3.get_unique(), f42)

        # Test select with placeholders
        s1_ph1 = fm1.select().where(Afact1.num1 == ph_("num1"))
        s1_ph2 = fm1.select().where(Afact1.str1 == ph_("str1","42"),
                                    Afact1.num1 == ph_("num1"))
        self.assertEqual(set(s1_ph1.get(num1=4)), set([f4,f42]))
        self.assertEqual(set(list(s1_ph1.get(num1=3))), set([f3]))
        self.assertEqual(set(list(s1_ph1.get(num1=2))), set([]))
        self.assertEqual(s1_ph2.get_unique(num1=4), f42)
        self.assertEqual(s1_ph2.get_unique(str1="42",num1=4), f42)

        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph1.get_unique(num1=4))  # fails because of multiple values
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph2.get(num2=5))         # fails because of no values
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph2.get(str1="42"))


    #--------------------------------------------------------------------------
    # Test select by the predicate object itself (and not a field). This is a
    # boundary case.
    # --------------------------------------------------------------------------

    def test_select_by_predicate(self):

        class Fact(Predicate):
            num1=IntegerField()
            str1=StringField()

        f1 = Fact(1,"bbb")
        f2 = Fact(2,"aaa")
        f2b = Fact(2,"bbb")
        f3 = Fact(3,"aaa")
        f4 = Fact(4,"aaa")
        facts=[f1,f2,f2b,f3,f4]

        self.assertTrue(f1 <= f2)
        self.assertTrue(f1 <= f2b)
        self.assertTrue(f2 <= f2b)
        self.assertTrue(f2b <= f2b)
        self.assertFalse(f3 <= f2b)

        fpb = path(Fact)
        self.assertEqual(f1, fpb(f1))
        self.assertFalse(f2 == fpb(f1))

        fb1 = FactBase(facts=facts, indexes=[path(Fact)])
        fb2 = FactBase(facts=facts)
        self.assertEqual(fb1, fb2)
        self.assertEqual(len(fb1), len(facts))

        s1 = fb1.select(Fact).where(fpb == ph1_)
        self.assertEqual(s1.get(f1), [f1])
        s1 = fb2.select(Fact).where(fpb == ph1_)
        self.assertEqual(s1.get(f1), [f1])

        s2 = fb1.select(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(s2.get(f2b), [f1,f2,f2b])
        s2 = fb2.select(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(s2.get(f2b), [f1,f2,f2b])

    #--------------------------------------------------------------------------
    # Test basic insert and selection of facts in a factbase
    #--------------------------------------------------------------------------

    def test_factbase_select(self):

        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Cfact(Predicate):
            num1=IntegerField()

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")
        cf1 = Cfact(1)

#        fb = FactBase([Afact.num1, Afact.num2, Afact.str1])
        fb = FactBase()
        facts=[af1,af2,af3,bf1,bf2,cf1]
        fb.add(facts)
#####        self.assertEqual(fb.add(facts), 6)

        self.assertEqual(set(fb.facts()), set(facts))
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))

        s_af_all = fb.select(Afact)
        s_af_num1_eq_1 = fb.select(Afact).where(Afact.num1 == 1)
        s_af_num1_le_2 = fb.select(Afact).where(Afact.num1 <= 2)
        s_af_num2_eq_20 = fb.select(Afact).where(Afact.num2 == 20)
        s_bf_str1_eq_aaa = fb.select(Bfact).where(Bfact.str1 == "aaa")
        s_bf_str1_eq_ccc = fb.select(Bfact).where(Bfact.str1 == "ccc")
        s_cf_num1_eq_1 = fb.select(Cfact).where(Cfact.num1 == 1)

        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))
        self.assertEqual(s_af_all.count(), 3)
        self.assertEqual(set(s_af_num1_eq_1.get()), set([af1]))
        self.assertEqual(set(s_af_num1_le_2.get()), set([af1,af2]))
        self.assertEqual(set(s_af_num2_eq_20.get()), set([af2, af3]))
        self.assertEqual(set(s_bf_str1_eq_aaa.get()), set([bf1]))
        self.assertEqual(set(s_bf_str1_eq_ccc.get()), set([]))
        self.assertEqual(set(s_cf_num1_eq_1.get()), set([cf1]))

        fb.clear()
        self.assertEqual(set(s_af_all.get()), set())
        self.assertEqual(set(s_af_num1_eq_1.get()), set())
        self.assertEqual(set(s_af_num1_le_2.get()), set())
        self.assertEqual(set(s_af_num2_eq_20.get()), set())
        self.assertEqual(set(s_bf_str1_eq_aaa.get()), set())
        self.assertEqual(set(s_bf_str1_eq_ccc.get()), set())
        self.assertEqual(set(s_cf_num1_eq_1.get()), set())

        # Test that the select can work with an initially empty factbase
        fb2 = FactBase()
        s2 = fb2.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(set(s2.get()), set())
        fb2.add([af1,af2])
        self.assertEqual(set(s2.get()), set([af1]))

        # Test select with placeholders
#        fb3 = FactBase([Afact.num1])
        fb3 = FactBase()
        fb3.add([af1,af2,af3])
####        self.assertEqual(fb3.add([af1,af2,af3]),3)
        s3 = fb3.select(Afact).where(Afact.num1 == ph_("num1"))
        self.assertEqual(s3.get_unique(num1=1), af1)
        self.assertEqual(s3.get_unique(num1=2), af2)
        self.assertEqual(s3.get_unique(num1=3), af3)


        # Test placeholders with positional arguments
        s4 = fb3.select(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(set(list(s4.get(1))), set([]))
        self.assertEqual(set(list(s4.get(2))), set([af1]))
        self.assertEqual(set(list(s4.get(3))), set([af1,af2]))

        s5 = fb3.select(Afact).where(Afact.num1 <= ph1_, Afact.num2 == ph2_)
        self.assertEqual(set(s5.get(3,10)), set([af1]))

        # Missing positional argument
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s5.get(1))

        # Test that the fact base index
        fb = FactBase(indexes=[Afact.num2, Bfact.str1])
        self.assertEqual(set([hashable_path(p) for p in fb.indexes]),
                         set([hashable_path(Afact.num2),
                              hashable_path(Bfact.str1)]))

    #--------------------------------------------------------------------------
    # Test factbase select with complex where clause
    #--------------------------------------------------------------------------

    def test_factbase_select_complex_where(self):

        class Afact(Predicate):
            num1=IntegerField
            num2=IntegerField
            str1=StringField

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        fb = FactBase([af1,af2,af3])

        q=fb.select(Afact).where((Afact.num1 == 2) | (Afact.num2 == 10))
        self.assertEqual(set([af1,af2]), set(q.get()))

        q=fb.select(Afact).where((Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af2]), set(q.get()))

        q=fb.select(Afact).where(~(Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af3]), set(q.get()))

        q=fb.select(Afact).where(~((Afact.num1 == 2) & (Afact.num2 == 20)))
        self.assertEqual(set([af1,af3]), set(q.get()))


    #--------------------------------------------------------------------------
    # Test factbase select with a lambda and placeholders
    #--------------------------------------------------------------------------

    def test_api_factbase_select_placeholders_with_lambda(self):

        class F(Predicate):
            num1=IntegerField
            str1=StringField

        f1 = F(1,"a")
        f2 = F(1,"b")
        f3 = F(2,"b")
        fb = FactBase([f1,f2,f3])


        q=fb.select(F).where((F.num1 == 1) & (lambda f : f.str1 == "b"))

        # NOTE: This fails because it is passing on the position argument 1 to
        # the lambda. TODO: Need to create a decorator that introspects the
        # lambda and can then ignore irrelevant parameters.
        with self.assertRaises(TypeError) as ctx:
            r=set(q.get(1))


        q=fb.select(F).where((F.num1 == 1) & (lambda f,v : f.str1 == v))
        self.assertEqual(set([f2]), set(q.get("b")))
        self.assertEqual(set([f2]), set(q.get(v="b")))

    #--------------------------------------------------------------------------
    #   Test that we can use the same placeholder multiple times
    #--------------------------------------------------------------------------
    def test_factbase_select_multi_placeholder(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap(Afact, [Afact.num1])
        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)

        fm1.add(f1) ; fm1.add(f2) ; fm1.add(f3) ; fm1.add(f4) ; fm1.add(f5)

        s1 = fm1.select().where(Afact.num1 == ph1_, Afact.num2 == ph1_)
        self.assertTrue(set([f for f in s1.get(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.get(2)]), set([f5]))

        s2 = fm1.select().where(Afact.num1 == ph_("a",1), Afact.num2 == ph_("a",2))
        self.assertTrue(set([f for f in s2.get(a=1)]), set([f1]))
        self.assertTrue(set([f for f in s2.get(a=2)]), set([f5]))
        self.assertTrue(set([f for f in s2.get()]), set([f2]))

        # test that we can do different parameters with normal functions
        def tmp(f,a,b=2):
            return f.num1 == a and f.num2 == 2

        s3 = fm1.select().where(tmp)
        with self.assertRaises(TypeError) as ctx:
            r=[f for f in s3.get()]

        self.assertTrue(set([f for f in s3.get(a=1)]), set([f2]))
        self.assertTrue(set([f for f in s3.get(a=1,b=3)]), set([f3]))

        # Test manually created positional placeholders
        s1 = fm1.select().where(Afact.num1 == ph1_, Afact.num2 == ph_(1))
        self.assertTrue(set([f for f in s1.get(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.get(2)]), set([f5]))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by
    #--------------------------------------------------------------------------
    def test_factbase_select_order_by(self):
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        f1 = Afact(num1=1,str1="1",str2="5")
        f2 = Afact(num1=2,str1="3",str2="4")
        f3 = Afact(num1=3,str1="5",str2="3")
        f4 = Afact(num1=4,str1="3",str2="2")
        f5 = Afact(num1=5,str1="1",str2="1")
        fb = FactBase(facts=[f1,f2,f3,f4,f5])

        q = fb.select(Afact).order_by(Afact.num1)
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(asc(Afact.num1))
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(desc(Afact.num1))
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(Afact.str2)
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(desc(Afact.str2))
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())

        q = fb.select(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())

        # Adding a duplicate object to a factbase shouldn't do anything
        f6 = Afact(num1=5,str1="1",str2="1")
        fb.add(f6)
        q = fb.select(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())


    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_factbase_select_order_by_complex_term(self):

        class SwapField(IntegerField):
            pytocl = lambda x: 100 - x
            cltopy = lambda x: 100 - x

        class AComplex(ComplexTerm):
            swap=SwapField(index=True)
            norm=IntegerField(index=True)

        class AFact(Predicate):
            astr = StringField(index=True)
            cmplx = AComplex.Field(index=True)

        cmplx1 = AComplex(swap=99,norm=1)
        cmplx2 = AComplex(swap=98,norm=2)
        cmplx3 = AComplex(swap=97,norm=3)

        f1 = AFact(astr="aaa", cmplx=cmplx1)
        f2 = AFact(astr="bbb", cmplx=cmplx2)
        f3 = AFact(astr="ccc", cmplx=cmplx3)
        f4 = AFact(astr="ddd", cmplx=cmplx3)

        fb = FactBase(facts=[f1,f2,f3,f4], indexes = [AFact.astr, AFact.cmplx])

        q = fb.select(AFact).order_by(AFact.astr)
        self.assertEqual([f1,f2,f3,f4], q.get())

        q = fb.select(AFact).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2,f1], q.get())

        q = fb.select(AFact).where(AFact.cmplx <= ph1_).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2], q.get(cmplx2))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_factbase_select_complex_term_placeholders(self):

        class AFact(Predicate):
            astr = StringField()
            cmplx1 = (IntegerField(), IntegerField())
            cmplx2 = (IntegerField(), IntegerField())

        f1 = AFact(astr="aaa", cmplx1=(1,2), cmplx2=(1,2))
        f2 = AFact(astr="bbb", cmplx1=(1,2), cmplx2=(1,5))
        f3 = AFact(astr="ccc", cmplx1=(1,5), cmplx2=(1,5))
        f4 = AFact(astr="ddd", cmplx1=(1,4), cmplx2=(1,2))

        fb = FactBase(facts=[f1,f2,f3,f4])

        q = fb.select(AFact).where(AFact.cmplx1 == (1,2))
        self.assertEqual([f1,f2], q.get())

        q = fb.select(AFact).where(AFact.cmplx1 == ph1_)
        self.assertEqual([f1,f2], q.get((1,2)))

        q = fb.select(AFact).where(AFact.cmplx1 == AFact.cmplx2)
        self.assertEqual([f1,f3], q.get())

        # Some type mismatch failures
#        with self.assertRaises(TypeError) as ctx:
#            fb.select(AFact).where(AFact.cmplx1 == 1).get()

        # Fail because of type mismatch
#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select(AFact).where(AFact.cmplx1 == (1,2,3)).get()

#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select(AFact).where(AFact.cmplx1 == ph1_).get((1,2,3))

    #--------------------------------------------------------------------------
    #   Test that the indexing works
    #--------------------------------------------------------------------------
    def test_factbase_select_indexing(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap(Afact, [Afact.num1])
        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)
        f6 = Afact(3,1)

        fm1.add(f1); fm1.add(f2); fm1.add(f3); fm1.add(f4); fm1.add(f5); fm1.add(f6)

        # Use a function to track the facts that are visited. This will show
        # that the first operator selects only the appropriate terms.
        facts = set()
        def track(f,a,b):
            nonlocal facts
            facts.add(f)
            return f.num2 == b

        s1 = fm1.select().where(Afact.num1 == ph1_, track)
        s2 = fm1.select().where(Afact.num1 < ph1_, track)

        self.assertTrue(set([f for f in s1.get(2,1)]), set([f4]))
        self.assertTrue(facts, set([f4,f5]))

        self.assertTrue(set([f for f in s2.get(2,2)]), set([f2]))
        self.assertTrue(facts, set([f1,f2,f3]))

    #--------------------------------------------------------------------------
    #   Test the delete
    #--------------------------------------------------------------------------
    def test_delete_over_factmap_and_factbase(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()

        fm1 = _FactMap(Afact, [Afact.num1,Afact.str1])
        fm2 = _FactMap(Afact)
        f1 = Afact(1,1,"1")
        f3 = Afact(3,3,"3")
        f4 = Afact(4,4,"4")
        f42 = Afact(4,42,"42")
        f10 = Afact(10,10,"10")
        fm1.add(f1) ; fm2.add(f1)
        fm1.add(f3) ; fm2.add(f3)
        fm1.add(f4) ; fm2.add(f4)
        fm1.add(f42) ; fm2.add(f42)
        fm1.add(f10) ; fm2.add(f10)

        d1_all = fm1.delete()
        d1_num1 = fm2.delete().where(Afact.num1 == ph1_)
        s1_num1 = fm2.select().where(Afact.num1 == ph1_)

        self.assertEqual(d1_all.execute(), 5)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.execute(4), 2)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([]))

#        return

        fb1 = FactBase(facts=[f1,f3, f4,f42,f10], indexes = [Afact.num1, Afact.num2])
        d1_num1 = fb1.delete(Afact).where(Afact.num1 == ph1_)
        s1_num1 = fb1.select(Afact).where(Afact.num1 == ph1_)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.execute(4), 2)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([]))

    #--------------------------------------------------------------------------
    # Test the support for indexes of subfields
    #--------------------------------------------------------------------------
    def test_factbase_select_with_subfields(self):
        class CT(ComplexTerm):
            num1=IntegerField()
            str1=StringField()
        class Fact(Predicate):
            ct1=CT.Field()
            ct2=(IntegerField(),IntegerField())
            ct3=(IntegerField(),IntegerField())

        fb = FactBase(indexes=[Fact.ct1.num1, Fact.ct1, Fact.ct2])

        f1=Fact(CT(10,"a"),(3,4),(4,3))
        f2=Fact(CT(20,"b"),(1,2),(2,1))
        f3=Fact(CT(30,"c"),(5,2),(2,5))
        f4=Fact(CT(40,"d"),(6,1),(1,6))

        fb.add(f1); fb.add(f2); fb.add(f3); fb.add(f4);

        # Three queries that uses index
        s1 = fb.select(Fact).where(Fact.ct1.num1 <= ph1_).order_by(Fact.ct2)
        s2 = fb.select(Fact).where(Fact.ct1 == ph1_)
        s3 = fb.select(Fact).where(Fact.ct2 == ph1_)
        s4 = fb.select(Fact).where(Fact.ct3 == ph1_)

        self.assertEqual(s1.get(20), [f2,f1])
        self.assertEqual(s2.get(CT(20,"b")), [f2])
        self.assertEqual(s3.get((1,2)), [f2])
        self.assertEqual(s4.get((2,1)), [f2])

        # One query doesn't use the index
        s4 = fb.select(Fact).where(Fact.ct1.str1 == ph1_)
        self.assertEqual(s4.get("c"), [f3])

    #--------------------------------------------------------------------------
    #   Test badly formed select/delete statements where the where clause (or
    #   order by clause for select statements) refers to fields that are not
    #   part of the predicate being queried. Instead of creating an error at
    #   query time creating the error when the statement is declared can help
    #   with debugging.
    #   --------------------------------------------------------------------------
    def test_bad_factbase_select_delete_statements(self):
        class F(Predicate):
            num1=IntegerField()
            num2=IntegerField()
        class G(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        f = F(1,2)
        fb = FactBase([f])

        # Making multiple calls to select where()
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == 1).where(F.num2 == 2)
        check_errmsg("cannot specify 'where' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where()
        check_errmsg("empty 'where' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == G.num1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == 1, G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select(F).where(0)
#        check_errmsg("'int' object is not callable",ctx)

        # Bad delete where clause
        with self.assertRaises(TypeError) as ctx:
            q = fb.delete(F).where(G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)


        # Making multiple calls to select order_by()
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1).order_by(F.num2)
        check_errmsg("cannot specify 'order_by' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by()
        check_errmsg("empty 'order_by' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(1)
        check_errmsg("Invalid 'order_by' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(G.num1)
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1,G.num1)
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1,desc(G.num1))
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
