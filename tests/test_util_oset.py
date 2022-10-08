# ------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
# ------------------------------------------------------------------------------

import unittest

from clorm.util.oset import OrderedSet

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "OrderedSetTestCase",
]


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


class OrderedSetTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    def test_basic_creation_iteration(self):

        # Creating an OrderedSet with a list and will additional items
        inlist1 = ["a", "b", "c", "d"]
        oset = OrderedSet(inlist1)
        self.assertEqual(list(oset), inlist1)

        oset = OrderedSet()
        for e in inlist1:
            oset.add(e)
        self.assertEqual(list(oset), inlist1)

        oset = OrderedSet(inlist1)
        inlist2 = [1, 2, 3]
        for e in inlist2:
            oset.add(e)
        self.assertEqual(list(oset), inlist1 + inlist2)

    def test_basic_ops(self):

        # Test pop
        inlist = ["a", "b", "c", "d"]
        oset = OrderedSet(inlist)
        oset.pop()
        self.assertEqual(list(oset), ["a", "b", "c"])
        oset.pop(last=False)
        self.assertEqual(list(oset), ["b", "c"])

        # Test pop for empty set
        oset = OrderedSet()
        with self.assertRaises(KeyError) as ctx:
            oset.pop()

        # Test clear
        inlist = ["a", "b", "c", "d"]
        oset = OrderedSet(inlist)
        oset.clear()
        self.assertEqual(list(oset), [])

        # Test remove and discard
        oset = OrderedSet(["a", "b", "c", "d"])
        oset.remove("b")
        self.assertEqual(list(oset), ["a", "c", "d"])

        # removing a non-existent item throws an exception
        with self.assertRaises(KeyError) as ctx:
            oset.remove("e")

        # discarding a non-existent item does nothing
        oset.discard("e")
        self.assertEqual(list(oset), ["a", "c", "d"])

        oset.discard("c")
        self.assertEqual(list(oset), ["a", "d"])

    def test_copy_equality(self):
        inlist = ["a", "b", "c", "d"]
        oset1 = OrderedSet(inlist)
        oset2 = oset1.copy()
        self.assertEqual(oset1, oset2)
        self.assertEqual(list(oset1), list(oset2))
        oset1.pop()
        self.assertFalse(list(oset1) == list(oset2))

        # Test equality
        inlist = ["a", "b", "c", "d"]
        oset1 = OrderedSet(inlist)
        inlist.reverse()
        oset2 = OrderedSet(inlist)
        oset3 = OrderedSet(["a", "b", "c"])

        # OrderedSets with the same elements but different ordering are not
        # equal
        self.assertFalse(oset1 == oset2)
        self.assertFalse(oset1 == oset3)

        # But an OrderedSet is equal to a normal set with the same elements and
        # different ordering.
        set1 = set(inlist)
        self.assertEqual(oset1, set1)
        self.assertFalse(oset3 == set1)

        # Test that the new isequal() function ignores the ordering
        self.assertFalse(oset1 == oset2)
        self.assertTrue(oset1.isequal(oset2))
        self.assertFalse(oset1.isequal(oset3))

    def test_bool_len_contains(self):
        inlist = ["a", "b", "c", "d"]
        oset = OrderedSet(inlist)
        self.assertEqual(len(oset), len(inlist))
        self.assertTrue("a" in oset)
        self.assertTrue("b" in oset)
        self.assertTrue("c" in oset)
        self.assertTrue("d" in oset)
        self.assertFalse("e" in oset)

        self.assertTrue(oset)
        oset.clear()
        self.assertFalse(oset)

    def test_bool_ops(self):
        set1 = set([1, 2, 3])
        oset1 = OrderedSet([1, 2, 3])

        # certain comparions cause a TypeError
        with self.assertRaises(TypeError) as ctx:
            set1 <= [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            oset1 <= [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            set1 < [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            oset1 < [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            set1 >= [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            oset1 >= [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            set1 > [1, 2, 3]
        with self.assertRaises(TypeError) as ctx:
            oset1 > [1, 2, 3]

        # Not sure why this doesn't raise a TypeError for set but I want the
        # behaviour to be consistent with OrderedSet
        self.assertFalse(set1 == [1, 2, 3])
        self.assertFalse(oset1 == [1, 2, 3])
        self.assertTrue(set1 != [1, 2, 3])
        self.assertTrue(oset1 != [1, 2, 3])

        self.assertTrue(set1.issubset([1, 2, 3]))
        self.assertTrue(oset1.issubset([1, 2, 3]))
        self.assertTrue(set1 <= set([1, 2, 3]))
        self.assertTrue(oset1 <= set([1, 2, 3]))
        self.assertTrue(set1 == set([1, 2, 3]))
        self.assertTrue(oset1 == set([1, 2, 3]))

        #        self.assertFalse(oset1 < [1,2,3])

        self.assertTrue(set1.issubset([1, 2, 3, 4]))
        self.assertTrue(oset1.issubset([1, 2, 3, 4]))
        self.assertTrue(set1 <= set([1, 2, 3, 4]))
        self.assertTrue(set1 <= OrderedSet([1, 2, 3, 4]))
        self.assertTrue(oset1 <= set([1, 2, 3, 4]))
        self.assertTrue(oset1 <= OrderedSet([1, 2, 3, 4]))

        self.assertTrue(set1 < set([1, 2, 3, 4]))
        self.assertTrue(set1 < OrderedSet([1, 2, 3, 4]))
        self.assertTrue(oset1 < set([1, 2, 3, 4]))
        self.assertTrue(oset1 < OrderedSet([1, 2, 3, 4]))

        self.assertFalse(set1.issubset([1, 2]))
        self.assertFalse(oset1.issubset([1, 2]))
        self.assertFalse(set1 <= set([1, 2]))
        self.assertFalse(oset1 <= set([1, 2]))
        self.assertFalse(set1 < set([1, 2]))
        self.assertFalse(oset1 < set([1, 2]))

        self.assertFalse(set1.issubset([2, 4]))
        self.assertFalse(oset1.issubset([2, 4]))
        self.assertFalse(set1 <= set([2, 4]))
        self.assertFalse(oset1 <= set([2, 4]))

        self.assertTrue(set1.issuperset([1, 2]))
        self.assertTrue(oset1.issuperset([1, 2]))
        self.assertTrue(set1 >= set([1, 2]))
        self.assertTrue(set1 >= OrderedSet([1, 2]))
        self.assertTrue(oset1 >= set([1, 2]))
        self.assertTrue(oset1 >= OrderedSet([1, 2]))

        self.assertTrue(set1.issuperset([1, 2, 3]))
        self.assertTrue(oset1.issuperset([1, 2, 3]))
        self.assertTrue(set1 >= set([1, 2, 3]))
        self.assertTrue(set1 >= OrderedSet([1, 2, 3]))
        self.assertTrue(oset1 >= set([1, 2, 3]))
        self.assertTrue(oset1 >= OrderedSet([1, 2, 3]))
        self.assertFalse(oset1.issuperset([1, 2, 3, 4]))
        self.assertFalse(set1 >= set([1, 2, 3, 4]))
        self.assertFalse(oset1 >= set([1, 2, 3, 4]))

        self.assertTrue(set1 > set([1, 2]))
        self.assertTrue(set1 > OrderedSet([1, 2]))
        self.assertTrue(oset1 > set([1, 2]))
        self.assertTrue(oset1 > OrderedSet([1, 2]))

        self.assertFalse(set1 > set([1, 2, 3]))
        self.assertFalse(oset1 > set([1, 2, 3]))
        self.assertFalse(oset1 > OrderedSet([1, 2, 3]))
        self.assertFalse(set1 > set([1, 2, 3, 4]))
        self.assertFalse(oset1 > set([1, 2, 3, 4]))

        self.assertFalse(set1.isdisjoint([1, 2, 3]))
        self.assertFalse(oset1.isdisjoint([1, 2, 3]))
        self.assertFalse(set1.isdisjoint([1, 2, 3, 4]))
        self.assertFalse(oset1.isdisjoint([1, 2, 3, 4]))
        self.assertFalse(set1.isdisjoint([1, 2]))
        self.assertFalse(oset1.isdisjoint([1, 2]))
        self.assertFalse(set1.isdisjoint([1, 2, 4]))
        self.assertFalse(oset1.isdisjoint([1, 2, 4]))

        self.assertTrue(oset1.isdisjoint([]))
        self.assertTrue(oset1.isdisjoint([4]))
        self.assertTrue(oset1.isdisjoint([4, 5]))

    def test_str_repr(self):
        set1 = set([])
        set2 = set([1])
        set3 = set([1, 2])
        set4 = set(["rar"])
        oset1 = OrderedSet([])
        oset2 = OrderedSet([1])
        oset3 = OrderedSet([1, 2])
        oset4 = OrderedSet(["rar"])

        self.assertEqual(str(set1), str(oset1))
        self.assertEqual(str(set2), str(oset2))
        self.assertEqual(str(set3), str(oset3))
        self.assertEqual(str(set4), str(oset4))

        self.assertEqual(repr(oset1), "OrderedSet()")
        self.assertEqual(repr(set2), repr(oset2))
        self.assertEqual(repr(set3), repr(oset3))
        self.assertEqual(repr(set4), repr(oset4))

    def test_set_union_intersection_functions(self):
        set1 = set([1, 2])
        set2 = set([2, 3])
        set3 = set([3, 4])
        oset1 = OrderedSet([1, 2])
        oset2 = OrderedSet([2, 3])
        oset3 = OrderedSet([3, 4])

        # Union/intersection/differeence of nothing returns a copy
        self.assertEqual(oset1.union(), set1.union())
        self.assertEqual(oset1.intersection(), set1.intersection())
        self.assertEqual(oset1.difference(), set1.difference())

        # Make sure the behaviour for OrderedSet operating on non-sets is the
        # same as for normal set.
        tmp1 = set1.union([2, 3])
        otmp1 = oset1.union([2, 3])
        self.assertEqual(otmp1, tmp1)
        self.assertEqual(str(otmp1), str(tmp1))

        # The union function
        self.assertEqual(oset1.union(oset2), set1.union(set2))
        self.assertEqual(oset1.union(oset3), set1.union(set3))
        self.assertEqual(oset1.union(oset2, oset3), set1.union(set2, set3))

        # Union of OrderedSets preserves the order
        self.assertEqual(oset1.union(oset2, oset3), OrderedSet([1, 2, 3, 4]))

        # The intersection function
        self.assertEqual(oset1.intersection(oset2), set1.intersection(set2))
        self.assertEqual(oset1.intersection(oset3), set1.intersection(set3))
        self.assertEqual(oset1.intersection(oset2, oset3), set1.intersection(set2, set3))

        # Intersection of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 3, 4, 5, 6])
        otmp2 = otmp1.intersection(OrderedSet([2, 3, 4, 6]), OrderedSet([1, 2, 4, 5, 6]))
        self.assertEqual(otmp2, OrderedSet([2, 4, 6]))

        # The difference function
        self.assertEqual(oset1.difference(oset2), set1.difference(set2))
        self.assertEqual(oset1.difference(oset3), set1.difference(set3))
        self.assertEqual(oset1.difference(oset2, oset3), set1.difference(set2, set3))

        # Difference of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 3, 4, 5])
        otmp2 = otmp1.difference(OrderedSet([1, 4]), OrderedSet([2, 6]))
        self.assertEqual(otmp2, OrderedSet([3, 5]))

        # The symmetric_difference function
        self.assertEqual(oset1.symmetric_difference(oset2), set1.symmetric_difference(set2))
        self.assertEqual(oset1.symmetric_difference(oset3), set1.symmetric_difference(set3))

        # Symmetric_difference of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 4, 3])
        otmp2 = otmp1.symmetric_difference(OrderedSet([3, 4, 6, 5]))
        self.assertEqual(otmp2, OrderedSet([1, 2, 6, 5]))

    def test_update_set_union_intersection_functions(self):
        set1 = set([1, 2])
        set2 = set([2, 3])
        set3 = set([3, 4])
        oset1 = OrderedSet([1, 2])
        oset2 = OrderedSet([2, 3])
        oset3 = OrderedSet([3, 4])

        # Union/intersection/difference _update of nothing returns itself
        self.assertEqual(oset1.update(), set1.update())
        self.assertEqual(oset1.intersection_update(), set1.intersection_update())
        self.assertEqual(oset1.difference_update(), set1.difference_update())

        # The update function
        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.update(oset2)
        tmp1.update(set2)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.update(oset3)
        tmp1.update(set3)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.update(oset2, oset3)
        tmp1.update(set2, set3)
        self.assertEqual(otmp1, tmp1)

        # Updated of OrderedSets preserves the order
        otmp1 = OrderedSet(oset1)
        otmp1.update(oset2, oset3)
        self.assertEqual(otmp1, OrderedSet([1, 2, 3, 4]))

        # The intersection_update function
        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.intersection_update(oset2)
        tmp1.intersection_update(set2)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.intersection_update(oset3)
        tmp1.intersection_update(set3)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.intersection_update(oset2, oset3)
        tmp1.intersection_update(set2, set3)
        self.assertEqual(otmp1, tmp1)

        # Intersection_update of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 3, 4, 5, 6])
        otmp1.intersection_update(OrderedSet([2, 3, 4, 6]), OrderedSet([1, 2, 4, 5, 6]))
        self.assertEqual(otmp1, OrderedSet([2, 4, 6]))

        # The difference_update function
        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.difference_update(oset2)
        tmp1.difference_update(set2)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.difference_update(oset3)
        tmp1.difference_update(set3)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.difference_update(oset2, oset3)
        tmp1.difference_update(set2, set3)
        self.assertEqual(otmp1, tmp1)

        # Difference_update of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 3, 4, 5])
        otmp1.difference_update(OrderedSet([1, 4]), OrderedSet([2, 6]))
        self.assertEqual(otmp1, OrderedSet([3, 5]))

        # The symmetric_difference_update function
        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.symmetric_difference_update(oset2)
        tmp1.symmetric_difference_update(set2)
        self.assertEqual(otmp1, tmp1)

        otmp1 = OrderedSet(oset1)
        tmp1 = set(set1)
        otmp1.symmetric_difference_update(oset3)
        tmp1.symmetric_difference_update(set3)
        self.assertEqual(otmp1, tmp1)

        # Symmetric_difference_update of OrderedSets preserves the order
        otmp1 = OrderedSet([1, 2, 4, 3])
        otmp1.symmetric_difference_update(OrderedSet([3, 4, 6, 5]))
        self.assertEqual(otmp1, OrderedSet([1, 2, 6, 5]))

    def test_set_union_intersection_operators(self):
        set1 = set([1, 2])
        set2 = set([2, 3])
        set3 = set([3, 4])
        oset1 = OrderedSet([1, 2])
        oset2 = OrderedSet([2, 3])
        oset3 = OrderedSet([3, 4])

        self.assertEqual(oset1 | oset2, set1 | set2)
        self.assertEqual(oset1 | set2, set1 | set2)

        # I don't think I can do anything about `set | OrderedSet` being not supported
        #        self.assertEqual(set1|oset2, set1|set2)

        self.assertEqual(oset1 & oset2, set1 & set2)
        self.assertEqual(oset1 & set2, set1 & set2)

        self.assertEqual(oset1 - oset2, set1 - set2)
        self.assertEqual(oset1 - set2, set1 - set2)

        self.assertEqual(oset1 ^ oset2, set1 ^ set2)
        self.assertEqual(oset1 ^ set2, set1 ^ set2)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
