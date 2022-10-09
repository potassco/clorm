# ------------------------------------------------------------------------------
# Unit tests for FactIndex and FactMap.
# ------------------------------------------------------------------------------

import operator
import unittest

# Official Clorm API imports for the core complements
from clorm.orm import (
    ComplexTerm,
    ConstantField,
    IntegerField,
    Predicate,
    StringField,
    hashable_path,
)
from clorm.orm.core import notcontains

# Implementation imports
from clorm.orm.factcontainers import FactIndex, FactMap

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "FactIndexTestCase",
    "FactMapTestCase",
]

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Test the FactIndex class
# ------------------------------------------------------------------------------


class FactIndexTestCase(unittest.TestCase):
    def setUp(self):
        class Afact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        self.Afact = Afact
        self.Bfact = Bfact

    # --------------------------------------------------------------------------
    # Alternative for accessing elements - this looks at some performance
    # differences
    # --------------------------------------------------------------------------

    def _test_getter_performance(self):
        import timeit

        testsetup = """
from clorm import Predicate, IntegerField
import random
from operator import attrgetter

class F(Predicate):
    anum = IntegerField
randlist=[]
for i in range(0,10000):
    randlist.append(F(random.randint(1,100)))
"""
        teststmt1 = """
randlist.sort(key=lambda x: x.anum)
"""
        teststmt2 = """
randlist.sort(key=F.anum)
"""
        teststmt3 = """
randlist.sort(key=F.anum.meta.attrgetter)
"""
        teststmt4 = """
randlist.sort(key=attrgetter('anum'))
"""
        repeat = 1000
        print("Lambda: {}".format(timeit.timeit(stmt=teststmt1, setup=testsetup, number=repeat)))
        print("Path: {}".format(timeit.timeit(stmt=teststmt2, setup=testsetup, number=repeat)))
        print(
            "PathAttrGetter: {}".format(
                timeit.timeit(stmt=teststmt3, setup=testsetup, number=repeat)
            )
        )
        print(
            "RawAttrGetter: {}".format(
                timeit.timeit(stmt=teststmt4, setup=testsetup, number=repeat)
            )
        )

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
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
        self.assertEqual(fi1.keys, [1, 2])
        self.assertEqual(fi2.keys, ["b", "c"])
        fi1.add(Afact(num1=3, str1="b"))
        fi2.add(Afact(num1=3, str1="b"))
        self.assertEqual(fi1.keys, [1, 2, 3])
        self.assertEqual(fi2.keys, ["b", "c"])

    def test_remove(self):
        Afact = self.Afact
        Bfact = self.Bfact

        af1a = Afact(num1=1, str1="a")
        af2a = Afact(num1=2, str1="a")
        af2b = Afact(num1=2, str1="b")
        af3a = Afact(num1=3, str1="a")
        af3b = Afact(num1=3, str1="b")

        fi = FactIndex(Afact.num1)
        for f in [af1a, af2a, af2b, af3a, af3b]:
            fi.add(f)
        self.assertEqual(fi.keys, [1, 2, 3])

        fi.remove(af1a)
        self.assertEqual(fi.keys, [2, 3])

        fi.discard(af1a)
        with self.assertRaises(KeyError) as ctx:
            fi.remove(af1a)

        fi.remove(af2a)
        self.assertEqual(fi.keys, [2, 3])

        fi.remove(af3a)
        self.assertEqual(fi.keys, [2, 3])

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
        allfacts = [af1a, af2a, af2b, af3a, af3b]
        for f in allfacts:
            fi.add(f)

        self.assertEqual(set(fi.find(operator.eq, 1)), set([af1a]))
        self.assertEqual(set(fi.find(operator.eq, 2)), set([af2a, af2b]))
        self.assertEqual(set(fi.find(operator.ne, 5)), set(allfacts))
        self.assertEqual(set(fi.find(operator.ne, 0)), set(allfacts))
        self.assertEqual(set(fi.find(operator.ne, 3)), set([af1a, af2a, af2b]))
        self.assertEqual(set(fi.find(operator.eq, 5)), set([]))
        self.assertEqual(set(fi.find(operator.lt, 1)), set([]))
        self.assertEqual(set(fi.find(operator.lt, 2)), set([af1a]))
        self.assertEqual(set(fi.find(operator.le, 2)), set([af1a, af2a, af2b]))
        self.assertEqual(set(fi.find(operator.gt, 2)), set([af3a, af3b]))
        self.assertEqual(set(fi.find(operator.ge, 3)), set([af3a, af3b]))
        self.assertEqual(set(fi.find(operator.gt, 3)), set([]))
        self.assertEqual(set(fi.find(operator.gt, 0)), set(allfacts))
        self.assertEqual(set(fi.find(operator.ge, 0)), set(allfacts))

    def test_find_ordering(self):
        Afact = self.Afact

        af1 = Afact(num1=1, str1="a")
        af3 = Afact(num1=3, str1="a")
        af5 = Afact(num1=5, str1="a")
        af7 = Afact(num1=7, str1="a")
        af9 = Afact(num1=9, str1="a")

        fi = FactIndex(Afact.num1)
        allfacts = [af1, af3, af5, af7, af9]
        for f in allfacts:
            fi.add(f)

        # Checking ordering of standard operators
        self.assertEqual(list(fi.find(operator.ne, 6)), allfacts)
        self.assertEqual(list(fi.find(operator.ne, 0)), allfacts)
        self.assertEqual(list(fi.find(operator.ne, 3)), [af1, af5, af7, af9])
        self.assertEqual(list(fi.find(operator.lt, 3)), [af1])
        self.assertEqual(list(fi.find(operator.lt, 4)), [af1, af3])
        self.assertEqual(list(fi.find(operator.le, 3)), [af1, af3])
        self.assertEqual(list(fi.find(operator.gt, 2)), [af3, af5, af7, af9])
        self.assertEqual(list(fi.find(operator.ge, 0)), allfacts)

        # The contains/notcontains operator
        self.assertEqual(list(fi.find(operator.contains, [])), [])
        self.assertEqual(list(fi.find(operator.contains, [3])), [af3])
        self.assertEqual(list(fi.find(operator.contains, [4])), [])
        self.assertEqual(list(fi.find(operator.contains, [4, 7])), [af7])
        self.assertEqual(list(fi.find(operator.contains, [3, 7])), [af3, af7])
        self.assertEqual(list(fi.find(notcontains, [])), allfacts)
        self.assertEqual(list(fi.find(notcontains, [4])), allfacts)
        self.assertEqual(list(fi.find(notcontains, [5, 6])), [af1, af3, af7, af9])
        self.assertEqual(list(fi.find(notcontains, [3, 7])), [af1, af5, af9])

        # Checking reverse ordering for standard operators
        allfacts.reverse()
        self.assertEqual(list(fi.find(operator.ne, 6, reverse=True)), allfacts)
        self.assertEqual(list(fi.find(operator.ne, 0, reverse=True)), allfacts)
        self.assertEqual(list(fi.find(operator.ne, 3, reverse=True)), [af9, af7, af5, af1])
        self.assertEqual(list(fi.find(operator.lt, 4, reverse=True)), [af3, af1])
        self.assertEqual(list(fi.find(operator.le, 3, reverse=True)), [af3, af1])
        self.assertEqual(list(fi.find(operator.gt, 2, reverse=True)), [af9, af7, af5, af3])
        self.assertEqual(list(fi.find(operator.ge, 0, reverse=True)), allfacts)

    def test_clear(self):
        Afact = self.Afact
        fi = FactIndex(Afact.num1)
        fi.add(Afact(num1=1, str1="a"))
        fi.clear()
        self.assertEqual(fi.keys, [])

    # --------------------------------------------------------------------------
    # Test the support for indexes of subfields
    # --------------------------------------------------------------------------
    def test_subfields(self):
        class CT(ComplexTerm):
            num1 = IntegerField()
            str1 = StringField()

        class Fact(Predicate):
            ct1 = CT.Field()
            ct2 = (IntegerField(), IntegerField())

        fi1 = FactIndex(Fact.ct1.num1)
        fi2 = FactIndex(Fact.ct2[1])
        fi3 = FactIndex(Fact.ct1)

        f1 = Fact(CT(10, "a"), (1, 4))
        f2 = Fact(CT(20, "b"), (2, 3))
        f3 = Fact(CT(30, "c"), (5, 2))
        f4 = Fact(CT(40, "d"), (6, 1))

        fi1.add(f1)
        fi2.add(f1)
        fi3.add(f1)
        fi1.add(f2)
        fi2.add(f2)
        fi3.add(f2)
        fi1.add(f3)
        fi2.add(f3)
        fi3.add(f3)
        fi1.add(f4)
        fi2.add(f4)
        fi3.add(f4)

        self.assertEqual(fi1.keys, [10, 20, 30, 40])
        self.assertEqual(fi2.keys, [1, 2, 3, 4])
        self.assertEqual(set(fi3.keys), set([CT(10, "a"), CT(20, "b"), CT(30, "c"), CT(40, "d")]))


# ------------------------------------------------------------------------------
# Test FactMap
# ------------------------------------------------------------------------------
class FactMapTestCase(unittest.TestCase):
    def setUp(self):
        class Afact(Predicate):
            anum = IntegerField
            aconst = ConstantField

        self.Afact = Afact

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_factmap_basics(self):

        Afact = self.Afact
        hp = hashable_path

        af1 = Afact(1, "bbb")
        af2 = Afact(2, "ccc")

        fm = FactMap(Afact, [Afact.anum])
        self.assertFalse(fm)
        self.assertEqual(fm.predicate, Afact)
        self.assertEqual(list(fm.path2factindex.keys()), [hp(Afact.anum)])

        fm.add_fact(af1)
        self.assertTrue(fm)
        self.assertEqual(set(fm.factset), set([af1]))
        self.assertEqual(set(fm.path2factindex[hp(Afact.anum)]), set([af1]))

        fm.pop()
        self.assertFalse(fm)
        self.assertFalse(set(fm.factset))
        self.assertFalse(set(fm.path2factindex[hp(Afact.anum)]))

        fm.add_facts([af1, af2])
        self.assertTrue(fm)
        self.assertEqual(set(fm.factset), set([af1, af2]))

        fm.discard(af1)
        self.assertTrue(fm)
        self.assertEqual(set(fm.factset), set([af2]))

        fm.clear()
        self.assertFalse(fm)
        self.assertFalse(set(fm.factset))

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_set_ops(self):
        def fm2set(fm):
            return set(fm.factset)

        Afact = self.Afact

        af1 = Afact(anum=1, aconst="a")
        af2 = Afact(anum=2, aconst="a")
        af3 = Afact(anum=3, aconst="c")
        af4 = Afact(anum=4, aconst="c")

        # Test union
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af3])
        r = fm1.union(fm1)
        self.assertEqual(fm2set(r), set([af1, af2]))
        r = fm1.union(fm2)
        self.assertEqual(fm2set(r), set([af1, af2, af3]))
        r = fm1.union(fm2, [af4])
        self.assertEqual(fm2set(r), set([af1, af2, af3, af4]))

        # Test intersection
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        r = fm1.intersection(fm1)
        self.assertEqual(fm2set(r), set(fm2set(fm1)))

        r = fm1.intersection(fm2)
        self.assertEqual(fm2set(r), set([af2]))
        r = fm1.intersection(fm2, [af2, af3, af4])
        self.assertEqual(fm2set(r), set([af2]))
        r = fm1.intersection(fm2, [af3, af4])
        self.assertEqual(fm2set(r), set())

        # Test difference
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        r = fm1.difference(fm1)
        self.assertEqual(fm2set(r), set([]))
        r = fm1.difference([af1])
        self.assertEqual(fm2set(r), set([af2]))
        r = fm1.difference(fm2)
        self.assertEqual(fm2set(r), set([af1]))

        # Test symmetric difference
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        r = fm1.symmetric_difference(fm1)
        self.assertEqual(fm2set(r), set())
        r = fm1.symmetric_difference(fm2)
        self.assertEqual(fm2set(r), set([af1, af3]))

        # Test update()
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        fm1.update([af3], [af4])
        self.assertEqual(fm2set(fm1), set([af1, af2, af3, af4]))

        # Test intersection()
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        fm1.intersection_update(fm2)
        self.assertEqual(fm2set(fm1), set([af2]))
        fm1.add_facts([af1, af2])
        fm1.intersection_update([af3])
        self.assertEqual(fm2set(fm1), set())

        # Test difference_update()
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        fm1.difference_update(fm2)
        self.assertEqual(fm2set(fm1), set([af1]))

        # Test symmetric_difference_update()
        fm1 = FactMap(Afact, [Afact.anum])
        fm2 = FactMap(Afact, [Afact.aconst])
        fm1.add_facts([af1, af2])
        fm2.add_facts([af2, af3])
        fm1.symmetric_difference_update(fm2)
        self.assertEqual(fm2set(fm1), set([af1, af3]))

    # --------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    # --------------------------------------------------------------------------

    def test_factmap_copy(self):
        Afact = self.Afact
        hp = hashable_path

        af1 = Afact(anum=1, aconst="a")
        af2 = Afact(anum=2, aconst="a")
        af3 = Afact(anum=3, aconst="c")
        af4 = Afact(anum=4, aconst="c")

        fm1 = FactMap(Afact, [Afact.anum])
        fm1.add_facts([af1, af2, af3, af4])

        fm2 = fm1.copy()

        self.assertTrue(not fm1 is fm2)
        self.assertTrue(not fm1.factset is fm2.factset)
        self.assertTrue(not fm1.path2factindex is fm2.path2factindex)
        self.assertTrue(
            not fm1.path2factindex[hp(Afact.anum)] is fm2.path2factindex[hp(Afact.anum)]
        )

        self.assertEqual(fm1.path2factindex, fm2.path2factindex)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
