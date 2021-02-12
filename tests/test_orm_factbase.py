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
    ph_, ph1_, ph2_, func_, alias, \
    basic_join_order_heuristic, fixed_join_order_heuristic

# Implementation imports
from clorm.orm.factbase import FactIndex, FactMap, _FactSet, \
    make_first_prejoin_query, make_prejoin_query_source, make_first_join_query, \
    make_chained_join_query, make_query, \
    InQuerySorter, QueryOutput, QueryExecutor

from clorm.orm.queryplan import PositionalPlaceholder, NamedPlaceholder, QuerySpec

from clorm.orm.queryplan import process_where, process_join, process_orderby, \
    make_query_plan, make_input_alignment_functor

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'FactIndexTestCase',
    'FactBaseTestCase',
    'InQuerySorterTestCase',
    'QueryTestCase',
    'QueryOutputTestCase',
    'SelectNoJoinTestCase',
    'SelectJoinTestCase',
    'QueryExecutorTestCase',
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Test the FactIndex class
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

    #--------------------------------------------------------------------------
    # Alternative for accessing elements - this looks at some performance
    # differences
    # --------------------------------------------------------------------------

    def _test_getter_performance(self):
        import timeit

        testsetup='''
from clorm import Predicate, IntegerField
import random
from operator import attrgetter

class F(Predicate):
    anum = IntegerField
randlist=[]
for i in range(0,10000):
    randlist.append(F(random.randint(1,100)))
'''
        teststmt1='''
randlist.sort(key=lambda x: x.anum)
'''
        teststmt2='''
randlist.sort(key=F.anum)
'''
        teststmt3='''
randlist.sort(key=F.anum.meta.attrgetter)
'''
        teststmt4='''
randlist.sort(key=attrgetter('anum'))
'''
        repeat=1000
        print("Lambda: {}".format(
            timeit.timeit(stmt=teststmt1,setup=testsetup,number=repeat)))
        print("Path: {}".format(
            timeit.timeit(stmt=teststmt2,setup=testsetup,number=repeat)))
        print("PathAttrGetter: {}".format(
            timeit.timeit(stmt=teststmt3,setup=testsetup,number=repeat)))
        print("RawAttrGetter: {}".format(
            timeit.timeit(stmt=teststmt4,setup=testsetup,number=repeat)))


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_create(self):
        Afact = self.Afact
        fi1 = FactIndex(Afact.num1)
        self.assertTrue(type(fi1), FactIndex)
        self.assertFalse(fi1)

        # Should only accept fields
        with self.assertRaises(TypeError) as ctx:
            f2 = FactIndex(1)
        with self.assertRaises(TypeError) as ctx:
            f2 = FactIndex(Afact)

    def test_add(self):
        Afact = self.Afact
        Bfact = self.Bfact
        fi1 = FactIndex(Afact.num1)
        fi2 = FactIndex(Afact.str1)
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

        fi = FactIndex(Afact.num1)
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

        fi = FactIndex(Afact.num1)
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
        fi = FactIndex(Afact.num1)
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

        fi1 = FactIndex(Fact.ct1.num1)
        fi2 = FactIndex(Fact.ct2[1])
        fi3 = FactIndex(Fact.ct1)

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
# InQuerySorterTest. Test functions for the underlying query mechanism
# ------------------------------------------------------------------------------

class InQuerySorterTestCase(unittest.TestCase):
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
        factindex = FactIndex(G.astr)
        for f in [G(1,"a"),G(1,"foo"),G(5,"a"),G(5,"foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(G.astr)] = factindex
        self.factsets[G] = factset

        factset = _FactSet()
        factindex = FactIndex(F.anum)
        for f in [F(1,"a"),F(1,"foo"),F(5,"a"),F(5,"foo")]:
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
            orderby = pob([desc(F.astr),G.anum],[F,G])
            iqs = InQuerySorter(orderby)
        check_errmsg("Cannot create an InQuerySorter",ctx)

        with self.assertRaises(AttributeError) as ctx:
            iqs = InQuerySorter([])
        check_errmsg("'list' object has no attribute",ctx)

    def test_InQuerySorter_singlefacts(self):
        F = self.F
        factsetF = self.factsets[F]
        roots = [F]
        pob = process_orderby

        # Ascending order sorting in-place as well as generating a new list
        orderby = pob([F.astr],roots)
        iqs = InQuerySorter(orderby)
        inlistF = list(factsetF)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)

        self.assertEqual(len(inlistF),4)
        self.assertEqual(len(outlistF),4)
        self.assertEqual(inlistF[0].astr,"a")
        self.assertEqual(outlistF[0].astr,"a")
        self.assertEqual(inlistF[1].astr,"a")
        self.assertEqual(outlistF[1].astr,"a")
        self.assertEqual(inlistF[2].astr,"foo")
        self.assertEqual(outlistF[2].astr,"foo")
        self.assertEqual(inlistF[3].astr,"foo")
        self.assertEqual(outlistF[3].astr,"foo")

        # Descending order sorting
        orderby = pob([desc(F.astr)],roots)
        iqs = InQuerySorter(orderby)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)

        self.assertEqual(len(outlistF),4)
        self.assertEqual(outlistF[0].astr,"foo")
        self.assertEqual(outlistF[1].astr,"foo")
        self.assertEqual(outlistF[2].astr,"a")
        self.assertEqual(outlistF[3].astr,"a")

        # Multiple criteria sort
        orderby = pob([desc(F.astr),F.anum],roots)
        iqs = InQuerySorter(orderby)
        iqs.listsort(inlistF)
        outlistF = iqs.sorted(inlistF)
        self.assertEqual(outlistF,
                         [F(1,"foo"),F(5,"foo"),F(1,"a"),F(5,"a"),])

    def test_InQuerySorter_facttuples(self):
        F = self.F
        G = self.G
        factsetF = self.factsets[F]
        factsetG = self.factsets[G]
        roots = [F,G]
        pob = process_orderby
        cp = []
        for f in factsetF:
            for g in factsetG: cp.append((f,g))

        orderby = pob([desc(F.anum),G.anum,desc(F.astr),desc(G.astr)],roots)
        iqs = InQuerySorter(orderby,roots)
        outlistF = iqs.sorted(cp)

        expected = [
            (F(5,"foo"), G(1,"foo")),
            (F(5,"foo"), G(1,"a")),
            (F(5,"a"), G(1,"foo")),
            (F(5,"a"), G(1,"a")),
            (F(5,"foo"), G(5,"foo")),
            (F(5,"foo"), G(5,"a")),
            (F(5,"a"), G(5,"foo")),
            (F(5,"a"), G(5,"a")),
            (F(1,"foo"), G(1,"foo")),
            (F(1,"foo"), G(1,"a")),
            (F(1,"a"), G(1,"foo")),
            (F(1,"a"), G(1,"a")),
            (F(1,"foo"), G(5,"foo")),
            (F(1,"foo"), G(5,"a")),
            (F(1,"a"), G(5,"foo")),
            (F(1,"a"), G(5,"a")),
        ]
        self.assertEqual(outlistF,expected)


#------------------------------------------------------------------------------
# QueryTest. Test functions for the underlying query mechanism
# ------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# support function to take a list of fact tuples transforms the order of facts
# based on the signature transform
# ------------------------------------------------------------------------------

def align_facts(insig, outsig, it):
    insig = tuple([path(a) for a in insig])
    outsig = tuple([path(a) for a in outsig])
    f = make_input_alignment_functor(insig,outsig)
    return [ f(t) for t in it ]


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
        factindex = FactIndex(G.astr)
        for f in [G(1,"a"),G(1,"foo"),G(5,"a"),G(5,"foo")]:
            factset.add(f)
            factindex.add(f)
        self.indexes[hashable_path(G.astr)] = factindex
        self.factsets[G] = factset

        factset = _FactSet()
        factindex = FactIndex(F.anum)
        for f in [F(1,"a"),F(1,"foo"),F(5,"a"),F(5,"foo")]:
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
        roots = [F,G]
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic
    
        # Simplest case. Nothing specified so pass through the factset
        qspec = QuerySpec(roots=roots,join=[],where=[],order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(out is factsets[G])

        # A prejoin key but nothing else
        where = pw(G.astr == "foo",roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(set(out), set([G(1,"foo"),G(5,"foo")]))

        # A prejoin clause but nothing else
        where = pw(G.anum == 1,roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(set(out), set([G(1,"a"),G(1,"foo")]))

        # Both a prejoin key and a prejoin clause
        where = pw((G.anum == 1) & (G.astr == "foo"),roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(set(out), set([G(1,"foo")]))

        # A prejoin key with no join and a single ascending order matching an index
        where = pw(G.astr == "foo",roots)
        orderby = pob([F.astr,asc(G.astr)],roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(out[0].astr, "foo")
        self.assertEqual(out[1].astr, "foo")
        self.assertEqual(len(out),2)

        # A prejoin key with no join and a single desc order matching an index
        where = pw(G.astr == "foo",roots)
        orderby = pob([F.astr,desc(G.astr)],roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(out[0].astr, "foo")
        self.assertEqual(out[1].astr, "foo")
        self.assertEqual(len(out),2)

        # A prejoin key with no join and a complex order
        where = pw(G.astr == "foo",roots)
        orderby = pob([F.astr,desc(G.astr),G.anum],roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out0 = make_prejoin_query_source(qp[0], factsets, indexes)()
        out1 = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertEqual(out0[0].astr, "a")
        self.assertEqual(out0[1].astr, "a")
        self.assertEqual(out0[2].astr, "foo")
        self.assertEqual(out0[3].astr, "foo")
        self.assertEqual(out1, [G(1,"foo"),G(5,"foo")])

        # A prejoin key with no join and non index matching sort
        where = pw(G.astr == "foo",roots)
        orderby = pob([F.astr,desc(G.anum)],roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,list))
        self.assertEqual(out, [G(5,"foo"),G(1,"foo")])

        # A join key that matches an existing index but nothing else
        join = pj([F.astr == G.astr],roots)
        qspec = QuerySpec(roots=roots,join=join,where=[],order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(out is indexes[hashable_path(G.astr)])

        # A join key that doesn't match an existing index - and nothing else
        join = pj([F.anum == G.anum],roots)
        qspec = QuerySpec(roots=roots,join=join,where=[],order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.anum))
        self.assertEqual(set(out), set(factsets[G]))

        # A join key and a prejoin key
        join = pj([F.astr == G.astr],roots)
        where = pw(G.astr == "foo",roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.astr))
        self.assertEqual(set(out), set([G(1,"foo"),G(5,"foo")]))

        # A join key and a prejoin clause
        join = pj([F.astr == G.astr],roots)
        where = pw(G.anum == 1,roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        out = make_prejoin_query_source(qp[1], factsets, indexes)()
        self.assertTrue(isinstance(out,FactIndex))
        self.assertEqual(hashable_path(out.path), hashable_path(G.astr))
        self.assertEqual(set(out), set([G(1,"a"),G(1,"foo")]))

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
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic
        roots = [F,G]

#        orderby = pob([F.astr,desc(G.anum)],roots)

        # Simplest case. No join or no G-where clauses.
        # (Note: the where clause for F is to simplify to only one join).
        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(1,"a")),
                              (F(1,"foo"), G(1,"foo")),
                              (F(1,"foo"), G(5,"a")),
                              (F(1,"foo"), G(5,"foo"))]))

        # No join but a prejoin where clause
        where = pw(((F.anum == 1) & (F.astr == "foo")) & (G.anum == 1), roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(1,"a")),
                              (F(1,"foo"), G(1,"foo"))]))

        # No join but a post-join where clause - by adding useless extra F
        where = pw(((F.anum == 1) & (F.astr == "foo")) &
                   ((G.anum == 1) | (F.anum == 5)), roots)
        qspec = QuerySpec(roots=roots,join=[],where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(1,"a")),
                              (F(1,"foo"), G(1,"foo"))]))

        # A join key but nothing else
        join = pj([F.astr == G.astr],roots)
        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=[],joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(1,"foo")),
                              (F(1,"foo"), G(5,"foo"))]))

        # A join key and a prejoin-sort
        join = pj([F.astr == G.astr],roots)
        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        orderby = pob([F.astr,desc(G.anum)],roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(5,"foo")),
                              (F(1,"foo"), G(1,"foo"))]))


        # A join key and a post join-sort
        join = pj([F.astr == G.astr],roots)
        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        orderby = pob([desc(G.anum)],roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)
        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(5,"foo")),
                              (F(1,"foo"), G(1,"foo"))]))

        # A join key and a complex post join sort
        join = pj([F.astr == G.astr],roots)
        where = pw((F.anum == 1) & (F.astr == "foo"),roots)
        orderby = pob([desc(G.anum),F.anum,G.astr],roots)
        qspec = QuerySpec(roots=roots,join=join,where=where,order_by=orderby,joh=fjoh)
        qp = make_query_plan(indexes.keys(), qspec)

        inquery=make_first_join_query(qp[0], factsets, indexes)
        query = make_chained_join_query(qp[1], inquery, factsets, indexes)()
        self.assertEqual(set(query),
                         set([(F(1,"foo"), G(5,"foo")),
                              (F(1,"foo"), G(1,"foo"))]))

 
    #--------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    #--------------------------------------------------------------------------
    def test_make_first_prejoin_query(self):
        def strip(it): return [f for f, in it]

        G = self.G
        pw = process_where
        pob = process_orderby
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic
        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.astr == "foo"),[G])
        qspec1 = QuerySpec(roots=[G],join=[],where=which1,order_by=[],joh=bjoh)
        qp1 = make_query_plan([G.astr],qspec1)
        q1 = make_first_prejoin_query(qp1[0],factsets,indexes)
        self.assertEqual(set([f for (f,) in q1()]),set([G(1,"foo"),G(5,"foo")]))

        which2 = pw((G.astr == "foo") | (G.astr == "a") ,[G])
        qspec2 = QuerySpec(roots=[G],join=[],where=which2,order_by=[],joh=bjoh)
        qp2 = make_query_plan([G.astr],qspec2)
        q2 = make_first_prejoin_query(qp2[0],factsets,indexes)
        self.assertEqual(set([f for (f,) in q2()]),
                         set([G(1,"foo"),G(5,"foo"),G(1,"a"),G(5,"a")]))


    #--------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    #--------------------------------------------------------------------------
    def test_make_first_join_query(self):
        def strip(it): return [f for f, in it]

        G = self.G
        pw = process_where
        pob = process_orderby
        bjoh = basic_join_order_heuristic
        fjoh = fixed_join_order_heuristic

        indexes = self.indexes
        factsets = self.factsets

        which1 = pw((G.anum > 4) & (G.astr == "foo"),[G])
        orderbys = pob([G.anum,desc(G.astr)],[G])
        qspec = QuerySpec(roots=[G],join=[],where=which1,order_by=orderbys,joh=bjoh)
        qp1 = make_query_plan([G.astr],qspec)

        query1 = make_first_join_query(qp1[0], factsets, indexes)
        self.assertEqual(set(strip(query1())), set([G(5,"foo")]))


        which2 = pw((G.anum > 4) | (G.astr == "foo"),[G])
        qspec = QuerySpec(roots=[G],join=[],where=which2,order_by=orderbys,joh=bjoh)
        qp2 = make_query_plan([G.astr], qspec)

        query2 = make_first_join_query(qp2[0], factsets, indexes)
        self.assertEqual(list(strip(query2())),
                         [G(1,"foo"), G(5,"foo"), G(5,"a")])


    #--------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    #--------------------------------------------------------------------------
    def test_make_query(self):
        F = self.F
        G = self.G
        indexes = self.indexes
        factsets = self.factsets
        pw = process_where
        pj = process_join
        pob = process_orderby
        bjoh = basic_join_order_heuristic
        fjoh = fixed_join_order_heuristic
        roots = [F,G]

        joins1 = pj([F.anum == G.anum],roots)
        which1 = pw((G.anum > 4) | (F.astr == "foo"),roots)
        orderbys = pob([desc(G.anum),F.astr,desc(G.astr)],roots)
        qspec = QuerySpec(roots=roots,join=joins1,where=which1,order_by=orderbys,joh=bjoh)
        qp1 = make_query_plan(indexes.keys(), qspec)
        q1 = make_query(qp1, factsets, indexes)
        result = list(q1())
        expected = [
            (F(5,"a"),G(5,"foo")),
            (F(5,"a"),G(5,"a")),
            (F(5,"foo"),G(5,"foo")),
            (F(5,"foo"),G(5,"a")),
            (F(1,"foo"),G(1,"foo")),
            (F(1,"foo"),G(1,"a")),
        ]
        self.assertEqual(expected, result)

        # Ungrounded query
        joins2 = pj([F.anum == G.anum],roots)
        which2 = pw((G.anum > 4) | (F.astr == ph1_),roots)
        orderbys2 = pob([desc(G.anum),F.astr,desc(G.astr)],roots)
        qspec = QuerySpec(roots=roots,join=joins2,where=which2,order_by=orderbys2,joh=bjoh)
        qp2 = make_query_plan(indexes.keys(),qspec)
        with self.assertRaises(ValueError) as ctx:
            q1 = make_query(qp2, factsets, indexes)
        check_errmsg("Cannot execute an ungrounded query",ctx)

#------------------------------------------------------------------------------
# QueryOutputTest. Test functions for the post-processing the query
# ------------------------------------------------------------------------------

def factbase_to_factsets(fb):
    return { ptype : fm.factset for ptype,fm in fb.factmaps.items() }


class QueryOutputTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

        factbase = FactBase([
            G(1,"a"),G(1,"foo"),G(5,"a"),G(5,"foo"),
            F(1,"a"),F(1,"foo"),F(5,"a"),F(5,"foo")])
        self.factbase = factbase

    #--------------------------------------------------------------------------
    # Test some basic configurations
    #--------------------------------------------------------------------------
    def test_api_QueryOutput(self):
        F = self.F
        G = self.G
        factbase=self.factbase
        indexes = {}
        factsets = factbase_to_factsets(factbase)
        pw = process_where
        pj = process_join
        pob = process_orderby
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic
        roots = [F,G]

        joins1 = pj([F.anum == G.anum],roots)
        where1 = pw((G.anum > 4) | (F.astr == "foo"),roots)
        orderbys = pob([F.anum,G.anum],roots)
        qspec = QuerySpec(roots=roots, join=joins1,where= where1,order_by= orderbys,joh=bjoh)
        qp1 = make_query_plan(indexes.keys(),qspec)
        q1 = make_query(qp1, factsets, indexes)

        # Test output with no options
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo)
        expected = set([(F(1,"foo"),G(1,"a")), (F(1,"foo"),G(1,"foo")),
                        (F(5,"a"),G(5,"a")), (F(5,"a"),G(5,"foo")),
                        (F(5,"foo"),G(5,"a")), (F(5,"foo"),G(5,"foo"))])
        self.assertEqual(expected, set(result))

        # Test output with no options - using the explicit all() method
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.all())
        expected = set([(F(1,"foo"),G(1,"a")), (F(1,"foo"),G(1,"foo")),
                        (F(5,"a"),G(5,"a")), (F(5,"a"),G(5,"foo")),
                        (F(5,"foo"),G(5,"a")), (F(5,"foo"),G(5,"foo"))])
        self.assertEqual(expected, set(result))

        # Test output with no options - using the count() method
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        self.assertEqual(qo.count(),6)

        # Test output with a simple swapped signature
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G,F))
        expected = set([(G(1,"a"),F(1,"foo")), (G(1,"foo"),F(1,"foo")),
                        (G(5,"a"),F(5,"a")), (G(5,"foo"),F(5,"a")),
                        (G(5,"a"),F(5,"foo")), (G(5,"foo"),F(5,"foo"))])
        self.assertEqual(expected, set(result))

        # Test output with filtered signature
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G.anum))
        expected = set([1,5])
        self.assertEqual(expected, set(result))

        # Test output with an complex implicit function signature
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G.anum,
                                lambda f,g: "X{}".format(f.astr)))
        expected = set([(1,"Xfoo"),(5,"Xa"),(5,"Xfoo")])
        self.assertEqual(expected, set(result))

        # Test output with an complex explicit function signature
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G.anum,
                                func_([F.astr], lambda v: "X{}".format(v))))
        expected = set([(1,"Xfoo"),(5,"Xa"),(5,"Xfoo")])
        self.assertEqual(expected, set(result))

        # Test output with filtered signature and uniqueness
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G.anum).unique())
        expected = set([1,5])
        self.assertTrue(result == [1,5] or result == [5,1])

        # Test output with filtered signature and forced tuple
        qo = QueryOutput(factbase.factmaps, qspec, qp1, q1)
        result = list(qo.output(G.anum).tuple())
        expected = set([(1,),(5,)])
        self.assertEqual(expected, set(result))

    #--------------------------------------------------------------------------
    # Test singleton, count, first
    #--------------------------------------------------------------------------
    def test_api_QueryOutput_singleton_count_first(self):
        F = self.F
        G = self.G
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic

        factbase=self.factbase

        def qsetup(where):
            indexes = {}
            factsets = factbase_to_factsets(factbase)
            pw = process_where
            pj = process_join
            pob = process_orderby
            roots = [F,G]

            join = pj([F.anum == G.anum],roots)
            where = pw(where,roots)
            orderby = pob([F.astr],roots)
            qspec = QuerySpec(roots=roots, join=join, where=where, order_by=orderby,joh=bjoh)
            qplan = make_query_plan(indexes.keys(),qspec)
            query = make_query(qplan, factsets, indexes)
            return QueryOutput(factbase.factmaps, qspec, qplan, query)

        # Test getting the first element
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        self.assertEqual(qo.first(),(F(5,"a"),G(5,"foo")))

        # Test getting the first element with filtered output
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        qo.output(F)
        self.assertEqual(qo.first(),F(5,"a"))

        # Test the count
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        qo.output(F)
        self.assertEqual(qo.count(),2)

        # Test count with filtered output and uniqueness
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        qo.output(F.anum).unique()
        self.assertEqual(qo.count(),1)

        # Test singleton with filtered output and uniqueness
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        qo.output(F.anum).unique()
        self.assertEqual(qo.singleton(),5)

        # Test singleton failure
        qo = qsetup((G.anum == 5) & (G.astr == "foo"))
        with self.assertRaises(ValueError) as ctx:
            qo.singleton()
        check_errmsg("Query returned more",ctx)

    #--------------------------------------------------------------------------
    # Test delete
    #--------------------------------------------------------------------------
    def test_api_QueryOutput_delete(self):
        F = self.F
        G = self.G
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic

        def delsetup():
            factbase=FactBase(self.factbase)
            indexes = {}
            factsets = factbase_to_factsets(factbase)
            pw = process_where
            pj = process_join
            pob = process_orderby
            roots = [F,G]

            join = pj([F.anum == G.anum],roots)
            where = pw(G.anum > 4,roots)
            orderby = pob([F.anum,G.anum],roots)
            qspec = QuerySpec(roots=roots, join=join,where=where,
                              order_by=orderby,joh=bjoh)
            qplan = make_query_plan(indexes.keys(),qspec)
            query = make_query(qplan, factsets, indexes)
            return (factbase,QueryOutput(factbase.factmaps, qspec, qplan, query))

        # Test deleting all selected elements
        fb,qo = delsetup()
        qo.delete()

        self.assertEqual(len(fb),4)
        self.assertFalse(F(5,"a") in fb)
        self.assertFalse(F(5,"foo") in fb)
        self.assertFalse(G(5,"a") in fb)
        self.assertFalse(G(5,"foo") in fb)

        # Test deleting all selected elements chosen explicitly
        fb,qo = delsetup()
        qo.delete(F,G)

        self.assertEqual(len(fb),4)
        self.assertFalse(F(5,"a") in fb)
        self.assertFalse(F(5,"foo") in fb)
        self.assertFalse(G(5,"a") in fb)
        self.assertFalse(G(5,"foo") in fb)

        # Test deleting only the F instances
        fb,qo = delsetup()
        qo.delete(F)

        self.assertEqual(len(fb),6)
        self.assertFalse(F(5,"a") in fb)
        self.assertFalse(F(5,"foo") in fb)

        # Test deleting only the G instances using a path object
        fb,qo = delsetup()
        qo.delete(path(G))

        self.assertEqual(len(fb),6)
        self.assertFalse(G(5,"a") in fb)
        self.assertFalse(G(5,"foo") in fb)

        # Bad delete - deleting an alias path that is not in the original
        fb,qo = delsetup()
        FA = alias(self.F)
        with self.assertRaises(ValueError) as ctx:
            qo.delete(FA)
        check_errmsg("The roots to delete",ctx)

        # Bad deletes -  deleting all plus an extra
        fb,qo = delsetup()
        FA = alias(self.F)
        with self.assertRaises(ValueError) as ctx:
            qo.delete(F,G,FA)
        check_errmsg("The roots to delete",ctx)

    #--------------------------------------------------------------------------
    # Test group_by
    #--------------------------------------------------------------------------
    def test_api_QueryOutput_group_by(self):
        F = self.F
        G = self.G
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic

        factbase=self.factbase

        def qsetup(ordering, where):
            indexes = {}
            factsets = factbase_to_factsets(factbase)
            pw = process_where
            pj = process_join
            pob = process_orderby
            roots = [F,G]

            join = pj([F.anum == G.anum],roots)
            where = pw(where,roots) if where else []
            orderby = pob(ordering,roots) if ordering else []
            qspec = QuerySpec(roots=roots, join=join,where=where,order_by=orderby,joh=bjoh)
            qplan = make_query_plan(indexes.keys(),qspec)
            query = make_query(qplan, factsets, indexes)
            return QueryOutput(factbase.factmaps, qspec, qplan, query)

        # Test some bad group_by setups
        qo = qsetup([], (G.anum == 5) & (G.astr == "foo"))
        with self.assertRaises(ValueError) as ctx:
            qo.group_by()
        check_errmsg("group_by() can only",ctx)

        qo = qsetup([F.anum], (G.anum == 5) & (G.astr == "foo"))
        with self.assertRaises(ValueError) as ctx:
            qo.group_by(0)
        check_errmsg("The grouping must be a positive integer",ctx)

        qo = qsetup([F.anum], (G.anum == 5) & (G.astr == "foo"))
        with self.assertRaises(ValueError) as ctx:
            qo.group_by(2)
        check_errmsg("The grouping size",ctx)

        qo = qsetup([F.anum], (G.anum == 5) & (G.astr == "foo"))
        with self.assertRaises(ValueError) as ctx:
            qo.group_by(1).group_by()
        check_errmsg("group_by() can only be specified once",ctx)

        # Test output with various options

        # Default grouping by first item (removes tuple)
        qo = qsetup([F.anum,F.astr], None)
#        print("\nTHE SPEC\n{}".format(qo._qspec))
#        print("\nTHE PLAN\n{}".format(qo._qplan))
        self.assertEqual([k for k,_ in list(qo.group_by())], [1,5])

        # Default grouping by first item but different order (removes tuple)
        qo = qsetup([desc(F.anum),F.astr], None)
        self.assertEqual([k for k,_ in list(qo.group_by())], [5,1])

        # Default grouping by first item with tuple not removed
        qo = qsetup([F.anum,F.astr], None).tuple()
        self.assertEqual([k for k,_ in list(qo.group_by())], [(1,),(5,)])

        # Default grouping by first item - check number of items
        qo = qsetup([F.anum,F.astr], None)
        for k,g in qo.group_by():
            self.assertEqual(len(list(g)),4)

        # Group by both items - check keys
        qo = qsetup([F.anum,F.astr], None)
        self.assertEqual([k for k,_ in list(qo.group_by(2).output(G))],
                         [(1,'a'),(1,'foo'),(5,'a'),(5,'foo')])

        # Group by both items with unique - single output for each group
        qo = qsetup([F.anum,F.astr], None)
        for k,g in qo.group_by(2).output(G.anum).unique():
            self.assertEqual(len(list(g)),1)


#------------------------------------------------------------------------------
# Test the Select class
#------------------------------------------------------------------------------

class SelectNoJoinTestCase(unittest.TestCase):
    def setUp(self):
        pass

    #--------------------------------------------------------------------------
    #   Test that the select works
    #--------------------------------------------------------------------------
    def test_api_select_factbase2(self):
        class Afact1(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()
            class Meta: name = "afact"

        f1 = Afact1(1,1,"1")
        f3 = Afact1(3,3,"3")
        f4 = Afact1(4,4,"4")
        f42 = Afact1(4,42,"42")
        f10 = Afact1(10,10,"10")
        fb1 = FactBase([f1,f3,f4,f42,f10], [Afact1.num1,Afact1.str1])
        fb2 = FactBase([f1,f3,f4,f42,f10])

        s1_all = fb1.select2(Afact1)
        s1_num1_eq_4 = fb1.select2(Afact1).where(Afact1.num1 == 4)
        s1_num1_ne_4 = fb1.select2(Afact1).where(Afact1.num1 != 4)
        s1_num1_lt_4 = fb1.select2(Afact1).where(Afact1.num1 < 4)
        s1_num1_le_4 = fb1.select2(Afact1).where(Afact1.num1 <= 4)
        s1_num1_gt_4 = fb1.select2(Afact1).where(Afact1.num1 > 4)
        s1_num1_ge_4 = fb1.select2(Afact1).where(Afact1.num1 >= 4)
        s1_str1_eq_4 = fb1.select2(Afact1).where(Afact1.str1 == "4")
        s1_num2_eq_4 = fb1.select2(Afact1).where(Afact1.num2 == 4)

        s2_all = fb1.select2(Afact1)
        s2_num1_eq_4 = fb2.select2(Afact1).where(Afact1.num1 == 4)
        s2_num1_ne_4 = fb2.select2(Afact1).where(Afact1.num1 != 4)
        s2_num1_lt_4 = fb2.select2(Afact1).where(Afact1.num1 < 4)
        s2_num1_le_4 = fb2.select2(Afact1).where(Afact1.num1 <= 4)
        s2_num1_gt_4 = fb2.select2(Afact1).where(Afact1.num1 > 4)
        s2_num1_ge_4 = fb2.select2(Afact1).where(Afact1.num1 >= 4)
        s2_str1_eq_4 = fb2.select2(Afact1).where(Afact1.str1 == "4")
        s2_num2_eq_4 = fb2.select2(Afact1).where(Afact1.num2 == 4)

        self.assertEqual(s1_all.query_plan()[0].prejoin_key,None)
        self.assertEqual(str(s1_num1_eq_4.query_plan()[0].prejoin_key),
                         "[ Afact1.num1 == 4 ]")
        self.assertEqual(str(s1_str1_eq_4.query_plan()[0].prejoin_key),
                         "[ Afact1.str1 == '4' ]")
        self.assertEqual(s2_all.query_plan()[0].prejoin_key,None)
        self.assertEqual(s2_num1_eq_4.query_plan()[0].prejoin_key, None)
        self.assertEqual(s2_str1_eq_4.query_plan()[0].prejoin_key, None)

        self.assertEqual(set(list(s1_all.run())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s1_num1_eq_4.run())), set([f4,f42]))
        self.assertEqual(set(list(s1_num1_ne_4.run())), set([f1,f3,f10]))
        self.assertEqual(set(list(s1_num1_lt_4.run())), set([f1,f3]))
        self.assertEqual(set(list(s1_num1_le_4.run())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s1_num1_gt_4.run())), set([f10]))
        self.assertEqual(set(list(s1_num1_ge_4.run())), set([f4,f42,f10]))
        self.assertEqual(s1_str1_eq_4.run().singleton(), f4)
        self.assertEqual(s1_num2_eq_4.run().singleton(), f4)

        self.assertEqual(set(list(s2_all.run())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s2_num1_eq_4.run())), set([f4,f42]))
        self.assertEqual(set(list(s2_num1_ne_4.run())), set([f1,f3,f10]))
        self.assertEqual(set(list(s2_num1_lt_4.run())), set([f1,f3]))
        self.assertEqual(set(list(s2_num1_le_4.run())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s2_num1_gt_4.run())), set([f10]))
        self.assertEqual(set(list(s2_num1_ge_4.run())), set([f4,f42,f10]))
        self.assertEqual(s2_str1_eq_4.run().singleton(), f4)
        self.assertEqual(s2_num2_eq_4.run().singleton(), f4)


        # Test simple conjunction select
        s1_conj1 = fb1.select2(Afact1).where(Afact1.str1 == "42", Afact1.num1 == 4)
        s1_conj2 = fb1.select2(Afact1).where(Afact1.num1 == 4, Afact1.str1 == "42")
        s1_conj3 = fb1.select2(Afact1).where(lambda x: x.str1 == "42", Afact1.num1 == 4)

        self.assertNotEqual(s1_conj1.query_plan()[0].prejoin_key, None)
        self.assertEqual(s1_conj1.run().singleton(), f42)
        self.assertEqual(s1_conj2.run().singleton(), f42)
        self.assertEqual(s1_conj3.run().singleton(), f42)

        # Test select with placeholders
        s1_ph1 = fb1.select2(Afact1).where(Afact1.num1 == ph_("num1"))
        s1_ph2 = fb1.select2(Afact1).where(Afact1.str1 == ph_("str1","42"),
                                          Afact1.num1 == ph_("num1"))
        self.assertEqual(set(s1_ph1.run(num1=4)), set([f4,f42]))
        self.assertEqual(set(list(s1_ph1.run(num1=3))), set([f3]))
        self.assertEqual(set(list(s1_ph1.run(num1=2))), set([]))
        self.assertEqual(s1_ph2.run(num1=4).singleton(), f42)
        self.assertEqual(s1_ph2.run(str1="42",num1=4).singleton(), f42)

        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph1.run(num1=4).singleton())  # fails because of multiple values
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph2.run(num2=5))         # fails because of no values
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph2.run(str1="42"))


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

        s1 = fb1.select2(Fact).where(fpb == ph1_)
        self.assertEqual(list(s1.run(f1)), [f1])
        s1 = fb2.select2(Fact).where(fpb == ph1_)
        self.assertEqual(list(s1.run(f1)), [f1])

        s2 = fb1.select2(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(list(s2.run(f2b)), [f1,f2,f2b])
        s2 = fb2.select2(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(list(s2.run(f2b)), [f1,f2,f2b])

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

        s_af_all = fb.select2(Afact)
        s_af_num1_eq_1 = fb.select2(Afact).where(Afact.num1 == 1)
        s_af_num1_le_2 = fb.select2(Afact).where(Afact.num1 <= 2)
        s_af_num2_eq_20 = fb.select2(Afact).where(Afact.num2 == 20)
        s_bf_str1_eq_aaa = fb.select2(Bfact).where(Bfact.str1 == "aaa")
        s_bf_str1_eq_ccc = fb.select2(Bfact).where(Bfact.str1 == "ccc")
        s_cf_num1_eq_1 = fb.select2(Cfact).where(Cfact.num1 == 1)

        self.assertEqual(set(s_af_all.run()), set([af1,af2,af3]))
        self.assertEqual(s_af_all.run().count(), 3)
        self.assertEqual(set(s_af_num1_eq_1.run()), set([af1]))
        self.assertEqual(set(s_af_num1_le_2.run()), set([af1,af2]))
        self.assertEqual(set(s_af_num2_eq_20.run()), set([af2, af3]))
        self.assertEqual(set(s_bf_str1_eq_aaa.run()), set([bf1]))
        self.assertEqual(set(s_bf_str1_eq_ccc.run()), set([]))
        self.assertEqual(set(s_cf_num1_eq_1.run()), set([cf1]))

        fb.clear()
        self.assertEqual(set(s_af_all.run()), set())
        self.assertEqual(set(s_af_num1_eq_1.run()), set())
        self.assertEqual(set(s_af_num1_le_2.run()), set())
        self.assertEqual(set(s_af_num2_eq_20.run()), set())
        self.assertEqual(set(s_bf_str1_eq_aaa.run()), set())
        self.assertEqual(set(s_bf_str1_eq_ccc.run()), set())
        self.assertEqual(set(s_cf_num1_eq_1.run()), set())

        # Test that the select can work with an initially empty factbase
        fb2 = FactBase()
        s2 = fb2.select2(Afact).where(Afact.num1 == 1)
        self.assertEqual(set(s2.run()), set())
        fb2.add([af1,af2])
        self.assertEqual(set(s2.run()), set([af1]))

        # Test select with placeholders
#        fb3 = FactBase([Afact.num1])
        fb3 = FactBase()
        fb3.add([af1,af2,af3])
####        self.assertEqual(fb3.add([af1,af2,af3]),3)
        s3 = fb3.select2(Afact).where(Afact.num1 == ph_("num1"))
        self.assertEqual(s3.run(num1=1).singleton(), af1)
        self.assertEqual(s3.run(num1=2).singleton(), af2)
        self.assertEqual(s3.run(num1=3).singleton(), af3)


        # Test placeholders with positional arguments
        s4 = fb3.select2(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(set(list(s4.run(1))), set([]))
        self.assertEqual(set(list(s4.run(2))), set([af1]))
        self.assertEqual(set(list(s4.run(3))), set([af1,af2]))

        s5 = fb3.select2(Afact).where(Afact.num1 <= ph1_, Afact.num2 == ph2_)
        self.assertEqual(set(s5.run(3,10)), set([af1]))

        # Missing positional argument
        with self.assertRaises(ValueError) as ctx:
            tmp = list(s5.run(1))

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

        q=fb.select2(Afact).where((Afact.num1 == 2) | (Afact.num2 == 10))
        self.assertEqual(set([af1,af2]), set(q.run()))

        q=fb.select2(Afact).where((Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af2]), set(q.run()))


        q=fb.select2(Afact).where(~(Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af3]), set(q.run()))

        q=fb.select2(Afact).where(~((Afact.num1 == 2) & (Afact.num2 == 20)))
        self.assertEqual(set([af1,af3]), set(q.run()))


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


        q=fb.select2(F).where((F.num1 == 1) & (lambda f : f.str1 == "b"))
        q=fb.select2(F).where((F.num1 == 1) & (lambda f,v : f.str1 == v))

        self.assertEqual(set([f2]), set(q.run("b")))
        self.assertEqual(set([f2]), set(q.run(v="b")))

    #--------------------------------------------------------------------------
    #   Test that we can use the same placeholder multiple times
    #--------------------------------------------------------------------------
    def test_api_factbase_select_multi_placeholder(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)
        fb1 = FactBase([f1,f2,f3,f4,f5], [Afact.num1])

        s1 = fb1.select2(Afact).where(Afact.num1 == ph1_, Afact.num2 == ph1_)
        self.assertTrue(set([f for f in s1.run(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.run(2)]), set([f5]))

        s2 = fb1.select2(Afact).where(Afact.num1 == ph_("a",1), Afact.num2 == ph_("a",2))
        self.assertTrue(set([f for f in s2.run(a=1)]), set([f1]))
        self.assertTrue(set([f for f in s2.run(a=2)]), set([f5]))
        self.assertTrue(set([f for f in s2.run()]), set([f2]))

        # test that we can do different parameters with normal functions
        def tmp(f,a,b=2):
            return f.num1 == a and f.num2 == b

        s3 = fb1.select2(Afact).where(tmp)
        with self.assertRaises(ValueError) as ctx:
            r=[f for f in s3.run()]

        self.assertTrue(set([f for f in s3.run(a=1)]), set([f2]))
        self.assertTrue(set([f for f in s3.run(a=1,b=3)]), set([f3]))

        # Test manually created positional placeholders
        s1 = fb1.select2(Afact).where(Afact.num1 == ph1_, Afact.num2 == ph_(1))
        self.assertTrue(set([f for f in s1.run(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.run(2)]), set([f5]))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by
    #--------------------------------------------------------------------------
    def test_api_factbase_select_order_by(self):
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

        q = fb.select2(Afact).order_by(Afact.num1)
        self.assertEqual([f1,f2,f3,f4,f5], list(q.run()))

        q = fb.select2(Afact).order_by(asc(Afact.num1))
        self.assertEqual([f1,f2,f3,f4,f5], list(q.run()))

        q = fb.select2(Afact).order_by(desc(Afact.num1))
        self.assertEqual([f5,f4,f3,f2,f1], list(q.run()))

        q = fb.select2(Afact).order_by(Afact.str2)
        self.assertEqual([f5,f4,f3,f2,f1], list(q.run()))

        q = fb.select2(Afact).order_by(desc(Afact.str2))
        self.assertEqual([f1,f2,f3,f4,f5], list(q.run()))

        q = fb.select2(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], list(q.run()))

        q = fb.select2(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], list(q.run()))

        # Adding a duplicate object to a factbase shouldn't do anything
        f6 = Afact(num1=5,str1="1",str2="1")
        fb.add(f6)
        q = fb.select2(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], list(q.run()))


    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_api_factbase_select_order_by_complex_term(self):

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

        q = fb.select2(AFact).order_by(AFact.astr)
        self.assertEqual([f1,f2,f3,f4], list(q.run()))

        q = fb.select2(AFact).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2,f1], list(q.run()))

        q = fb.select2(AFact).where(AFact.cmplx <= ph1_).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2], list(q.run(cmplx2)))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_api_factbase_select_complex_term_placeholders(self):

        class AFact(Predicate):
            astr = StringField()
            cmplx1 = (IntegerField(), IntegerField())
            cmplx2 = (IntegerField(), IntegerField())

        f1 = AFact(astr="aaa", cmplx1=(1,2), cmplx2=(1,2))
        f2 = AFact(astr="bbb", cmplx1=(1,2), cmplx2=(1,5))
        f3 = AFact(astr="ccc", cmplx1=(1,5), cmplx2=(1,5))
        f4 = AFact(astr="ddd", cmplx1=(1,4), cmplx2=(1,2))

        fb = FactBase(facts=[f1,f2,f3,f4])

        q = fb.select2(AFact).where(AFact.cmplx1 == (1,2))
        self.assertEqual([f1,f2], list(q.run()))

        q = fb.select2(AFact).where(AFact.cmplx1 == ph1_)
        self.assertEqual([f1,f2], list(q.run((1,2))))

        q = fb.select2(AFact).where(AFact.cmplx1 == AFact.cmplx2)
        self.assertEqual([f1,f3], list(q.run()))

        # Some type mismatch failures
#        with self.assertRaises(TypeError) as ctx:
#            fb.select2(AFact).where(AFact.cmplx1 == 1).run()

        # Fail because of type mismatch
#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select2(AFact).where(AFact.cmplx1 == (1,2,3)).run()

#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select2(AFact).where(AFact.cmplx1 == ph1_).run((1,2,3))

    #--------------------------------------------------------------------------
    #   Test that the indexing works
    #--------------------------------------------------------------------------
    def test_api_factbase_select_indexing(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)
        f6 = Afact(3,1)
        fb1 = FactBase([f1,f2,f3,f4,f5,f6], indexes=[Afact.num1])

        # Use a function to track the facts that are visited. This will show
        # that the first operator selects only the appropriate terms.
        facts = set()
        def track(f,a,b):
            nonlocal facts
            facts.add(f)
            return f.num2 == b

        s1 = fb1.select2(Afact).where(Afact.num1 == ph1_, track)
        s2 = fb1.select2(Afact).where(Afact.num1 < ph1_, track)

        self.assertTrue(set([f for f in s1.run(2,1)]), set([f4]))
        self.assertTrue(facts, set([f4,f5]))

        self.assertTrue(set([f for f in s2.run(2,2)]), set([f2]))
        self.assertTrue(facts, set([f1,f2,f3]))

    #--------------------------------------------------------------------------
    #   Test the delete
    #--------------------------------------------------------------------------
    def test_factbase_delete(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()

        f1 = Afact(1,1,"1")
        f3 = Afact(3,3,"3")
        f4 = Afact(4,4,"4")
        f42 = Afact(4,42,"42")
        f10 = Afact(10,10,"10")

        fb1 = FactBase(facts=[f1,f3, f4,f42,f10], indexes = [Afact.num1, Afact.num2])
        d1_num1 = fb1.select2(Afact).where(Afact.num1 == ph1_)
        s1_num1 = fb1.select2(Afact).where(Afact.num1 == ph1_)
        self.assertEqual(set([f for f in s1_num1.run(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.run(4).delete(), 2)
        self.assertEqual(set([f for f in s1_num1.run(4)]), set([]))

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
        s1 = fb.select2(Fact).where(Fact.ct1.num1 <= ph1_).order_by(Fact.ct2)
        s2 = fb.select2(Fact).where(Fact.ct1 == ph1_)
        s3 = fb.select2(Fact).where(Fact.ct2 == ph1_)
        s4 = fb.select2(Fact).where(Fact.ct3 == ph1_)

        self.assertEqual(list(s1.run(20)), [f2,f1])
        self.assertEqual(list(s2.run(CT(20,"b"))), [f2])

        # NOTE: Important test as it requires tuple complex terms to have the
        # same hash as the corresponding python tuple.
        self.assertEqual(list(s3.run((1,2))), [f2])
        self.assertEqual(list(s4.run((2,1))), [f2])

        # One query doesn't use the index
        s4 = fb.select2(Fact).where(Fact.ct1.str1 == ph1_)
        self.assertEqual(list(s4.run("c")), [f3])

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
            q = fb.select2(F).where(F.num1 == 1).where(F.num2 == 2)
        check_errmsg("Cannot specify 'where' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select2(F).where()
        check_errmsg("Empty 'where' expression",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).where(G.num1 == 1)
        check_errmsg("Invalid 'where' expression 'G.num1",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).where(F.num1 == G.num1)
        check_errmsg("Invalid 'where' expression",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).where(F.num1 == 1, G.num1 == 1)
        check_errmsg("Invalid 'where' expression",ctx)

#        with self.assertRaises(TypeError) as ctx:
#            q = fb.select2(F).where(0)
#        check_errmsg("'int' object is not callable",ctx)

        # Bad delete where clause
        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).where(G.num1 == 1).run().delete()
        check_errmsg("Invalid 'where' expression",ctx)


        # Making multiple calls to select order_by()
        with self.assertRaises(TypeError) as ctx:
            q = fb.select2(F).order_by(F.num1).order_by(F.num2)
        check_errmsg("Cannot specify 'order_by' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select2(F).order_by()
        check_errmsg("Empty 'order_by' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select2(F).order_by(1)
        check_errmsg("Invalid 'order_by' expression",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).order_by(G.num1)
        check_errmsg("Invalid 'order_by' expression",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).order_by(F.num1,G.num1)
        check_errmsg("Invalid 'order_by' expression",ctx)

        with self.assertRaises(ValueError) as ctx:
            q = fb.select2(F).order_by(F.num1,desc(G.num1))
        check_errmsg("Invalid 'order_by' expression",ctx)


#------------------------------------------------------------------------------
# Tests for additional V2 select and delete statements
#------------------------------------------------------------------------------

class SelectJoinTestCase(unittest.TestCase):
    def setUp(self):
        pass

    #--------------------------------------------------------------------------
    #   Test that the select works
    #--------------------------------------------------------------------------
    def test_api_select_self_join(self):
        class P(Predicate):
            pid = ConstantField
            name = StringField
            postcode = IntegerField

        class F(Predicate):
            src = ConstantField
            dst = ConstantField


        jill = P("jill", "Jill J", 2001)
        jane = P("jane", "Jane J", 2002)
        bob  = P("bob",  "Bob B",  2003)
        bill = P("bill", "Bill B", 2004)
        sal  = P("sal",  "Sal S",  2004)
        dave = P("dave", "Dave D", 2004)

        people = [jill,jane,bob,bill,sal,dave]
        friends = [F(jill.pid,dave.pid),F(dave.pid,jill.pid),
                   F(dave.pid,bill.pid),F(bill.pid,dave.pid),
                   F(jane.pid,sal.pid),F(sal.pid,jane.pid)]

        fb2 = FactBase(people+friends,indexes=[P.pid,F.src,F.dst])

        s1_people = fb2.select2(P).order_by(P.pid)
        self.assertEqual(list(s1_people.run()),[bill,bob,dave,jane,jill,sal])

        PA=alias(P)
        all_friends = fb2.select2(P,PA,F)\
            .join(P.pid == F.src,PA.pid == F.dst)
        close_friends = all_friends\
            .where(P.name < PA.name,
                   func_([P.postcode,PA.postcode], lambda p,pa : abs(p-pa) < 3))\
            .order_by(P.name)
        all_friends_sorted=all_friends.order_by(P.pid,PA.pid)

        results = list(all_friends_sorted.run().output(F))
        self.assertEqual([F(bill.pid,dave.pid),
                          F(dave.pid,bill.pid),F(dave.pid,jill.pid),
                          F(jane.pid,sal.pid),
                          F(jill.pid,dave.pid),
                          F(sal.pid,jane.pid)], results)

        all_friends = all_friends.order_by(P.pid,PA.name)
        tmp = { p : list(fs) for p,fs in all_friends.run()\
                .group_by(1).output(PA.name) }
        self.assertEqual(len(tmp), 5)
        self.assertEqual(len(tmp["bill"]), 1)
        self.assertEqual(len(tmp["dave"]), 2)
        self.assertEqual(len(tmp["jane"]), 1)
        self.assertEqual(len(tmp["jill"]), 1)
        self.assertEqual(len(tmp["sal"]), 1)


class QueryExecutorTestCase(unittest.TestCase):
    def setUp(self):
        class F(Predicate):
            anum=IntegerField
            astr=StringField
        self.F = F

        class G(Predicate):
            anum=IntegerField
            astr=StringField
        self.G = G

        factbase = FactBase([
            G(1,"a"),G(1,"foo"),G(5,"a"),G(5,"foo"),
            F(1,"a"),F(1,"foo"),F(5,"a"),F(5,"foo")])
        self.factbase = factbase

    #--------------------------------------------------------------------------
    # Test some basic configurations
    #--------------------------------------------------------------------------
    def test_nonapi_QueryExecutor(self):
        F = self.F
        G = self.G
        factbase=self.factbase
        pw = process_where
        pj = process_join
        pob = process_orderby
        fjoh = fixed_join_order_heuristic
        bjoh = basic_join_order_heuristic

        roots = (F,G)
        join = pj([F.anum == G.anum],roots)
        where = pw((F.astr == "foo"),roots)
        order_by = pob([G.anum,G.astr],roots)
        qspec = QuerySpec(roots=roots, join=join, where=where, order_by=order_by,joh=bjoh)

        qe = QueryExecutor(factbase.factmaps, qspec)

        # Test output with no options
        result = list(qe.all())
        expected = set([(F(1,"foo"),G(1,"a")), (F(1,"foo"),G(1,"foo")),
                        (F(5,"foo"),G(5,"a")), (F(5,"foo"),G(5,"foo"))])
        self.assertEqual(expected, set(result))
 
#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
