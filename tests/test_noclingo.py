#------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
#------------------------------------------------------------------------------

import inspect
import unittest
import datetime
import calendar
import operator
import clingo
import clorm.noclingo as noclingo

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'NoClingoTestCase'
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class NoClingoTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_symboltype_value_and_order(self):
        self.assertTrue(str(clingo.SymbolType.Number), str(noclingo.SymbolType.Number))
        self.assertTrue(str(clingo.SymbolType.String), str(noclingo.SymbolType.String))
        self.assertTrue(str(clingo.SymbolType.Function), str(noclingo.SymbolType.Function))
        self.assertTrue(str(clingo.SymbolType.Supremum), str(noclingo.SymbolType.Supremum))
        self.assertTrue(str(clingo.SymbolType.Infimum), str(noclingo.SymbolType.Infimum))

        if clingo.SymbolType.Number < clingo.SymbolType.String:
            self.assertTrue(noclingo.SymbolType.Number < noclingo.SymbolType.String)
        else:
            self.assertTrue(noclingo.SymbolType.Number > noclingo.SymbolType.String)

        if clingo.SymbolType.Number < clingo.SymbolType.Function:
            self.assertTrue(noclingo.SymbolType.Number < noclingo.SymbolType.Function)
        else:
            self.assertTrue(noclingo.SymbolType.Number > noclingo.SymbolType.Function)

        if clingo.SymbolType.String < clingo.SymbolType.Function:
            self.assertTrue(noclingo.SymbolType.String < noclingo.SymbolType.Function)
        else:
            self.assertTrue(noclingo.SymbolType.String > noclingo.SymbolType.Function)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_invalid_values(self):

        # The symbol type needs to be valid
        with self.assertRaises(TypeError) as ctx:
            noclingo.Symbol(6, 4)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_string(self):
        nc = noclingo.String("atest")
        c =  clingo.String("atest")
        self.assertEqual(nc.name, c.name)
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.String)

    def test_number(self):
        nc = noclingo.Number(1)
        c =  clingo.Number(1)
        self.assertEqual(nc.number, c.number)
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.Number)

    def test_infimum_supremum(self):
        nc1 = noclingo.Infimum
        nc2 = noclingo.Number(1)
        nc3 = noclingo.String("a")
        nc4 = noclingo.Function("a")
        nc5 = noclingo.Supremum

        self.assertTrue(nc1 == nc1)
        self.assertTrue(nc1 <= nc1)
        self.assertTrue(nc1 < nc2)
        self.assertTrue(nc1 < nc3)
        self.assertTrue(nc1 < nc4)
        self.assertTrue(nc1 < nc5)
        self.assertTrue(nc5 > nc1)
        self.assertTrue(nc5 > nc2)
        self.assertTrue(nc5 > nc3)
        self.assertTrue(nc5 > nc4)
        self.assertTrue(nc5 >= nc5)
        self.assertTrue(nc1 != nc2)

        self.assertEqual(str(nc1), str(clingo.Infimum))
        self.assertEqual(str(nc5), str(clingo.Supremum))
        self.assertEqual(nc1.type, noclingo.SymbolType.Infimum)
        self.assertEqual(nc5.type, noclingo.SymbolType.Supremum)


    def test_function(self):
        nc = noclingo.Function("atest")
        c =  clingo.Function("atest")
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.Function)

        nc1 = noclingo.Function("aaaa")
        nc2 = noclingo.String("bbb")
        nc3 = noclingo.Function("ccc",[noclingo.Number(10)])
        c1 = clingo.Function("aaaa")
        c2 = clingo.String("bbb")
        c3 = clingo.Function("ccc",[clingo.Number(10)])

        nc = noclingo.Function("atest",[nc1,nc2,nc3])
        c =  clingo.Function("atest", [c1,c2,c3])

        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.name, c.name)
        self.assertEqual(nc.name, "atest")
        self.assertEqual(len(nc.arguments), len(c.arguments))
        self.assertEqual(nc.arguments[0].name, c.arguments[0].name)
        self.assertEqual(nc.arguments[0].name, "aaaa")
        self.assertEqual(nc.arguments[1].string, c.arguments[1].string)

    def test_tuple(self):
        nc1 = noclingo.Function("aaaa")
        nc2 = noclingo.String("bbb")
        c1 = clingo.Function("aaaa")
        c2 = clingo.String("bbb")
        nc = noclingo.Function("", [nc1,nc2])
        c =  clingo.Function("", [c1,c2])

    def test_hash_and_equality_comparison_ops(self):
        nc1 = noclingo.String("aaaGGDFa")
        nc2 = noclingo.String("aaaGGDFa")
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        nc1 = noclingo.Number(34068390)
        nc2 = noclingo.Number(34068390)
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        nc1 = noclingo.Function("aaaa")
        nc2 = noclingo.Function("aaaa")
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        a1 = noclingo.Function("aaaa")
        a2 = noclingo.Function("aaaa")
        b1 = noclingo.String("bbb")
        b2 = noclingo.String("bbb")
        c1 = noclingo.Number(45)
        c2 = noclingo.Number(45)
        d1 = noclingo.Function("dfdf",[c1])
        d2 = noclingo.Function("dfdf",[c2])
        nc1 = noclingo.Function("ccc",[a1,b1,c1,d1])
        nc2 = noclingo.Function("ccc",[a2,b2,c2,d2])
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

    def test_comparison_ops(self):
        nc1 = noclingo.Number(34)
        nc2 = noclingo.Number(43)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 < nc2)
        self.assertTrue(nc2 >= nc1)
        self.assertTrue(nc2 > nc1)

        nc3 = noclingo.String("abcd")
        nc4 = noclingo.String("bcde")
        self.assertTrue(nc3 <= nc4)
        self.assertTrue(nc3 < nc4)
        self.assertTrue(nc4 >= nc3)
        self.assertTrue(nc4 > nc3)

        nc5 = noclingo.Function("abc",[noclingo.Number(45)])
        nc6 = noclingo.Function("abc",[noclingo.String("45")])
        c5 = clingo.Function("abc",[clingo.Number(45)])
        c6 = clingo.Function("abc",[clingo.String("45")])
        if c5 < c6: self.assertTrue(nc5 < nc6)
        else: self.assertTrue(nc5 > nc6)

        nc7 = noclingo.Function("abc",[noclingo.String("45"), noclingo.Number(5)])
        self.assertTrue(nc6 < nc7)

        if noclingo.SymbolType.Number < noclingo.SymbolType.String:
            self.assertTrue(nc1 < nc3)
        else:
            self.assertTrue(nc1 > nc3)

    def test_clingo_noclingo_difference(self):
        self.assertNotEqual(clingo.String("blah"), noclingo.String("blah"))
        self.assertNotEqual(clingo.Number(5), noclingo.Number(5))

    def test_control(self):
        with self.assertRaises(TypeError) as ctx:
            instance = noclingo.Control()


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
