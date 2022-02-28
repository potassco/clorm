#------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
#------------------------------------------------------------------------------

import inspect
import unittest
import datetime
import calendar
import operator
import clingo
import clorm.orm.noclingo as noclingo
from clorm.orm.noclingo import ( SymbolType, Symbol, Function, String, Number,
                                 get_Infimum, get_Supremum, clingo_to_noclingo,
                                 noclingo_to_clingo, SymbolMode,
                                 get_symbol_mode, set_symbol_mode )

clingo_version = clingo.__version__

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'NoClingoTestCase',
    'NoClingoEnabledTestCase'
    ]

#------------------------------------------------------------------------------
# Tests that don't require that NOCLINGO is enabled
#------------------------------------------------------------------------------

class NoClingoTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_invalid_values(self):

        # The symbol type needs to be valid
        with self.assertRaises(TypeError) as ctx:
            noclingo.NoSymbol(6, 4)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_string(self):
        nc = noclingo.NoString("atest")
        c =  clingo.String("atest")
        self.assertEqual(nc.string, c.string)
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.String)

    def test_number(self):
        nc = noclingo.NoNumber(1)
        c =  clingo.Number(1)
        self.assertEqual(nc.number, c.number)
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.Number)

    def test_infimum_supremum(self):
        nc1 = noclingo.NoInfimum
        nc2 = noclingo.NoNumber(1)
        nc3 = noclingo.NoString("a")
        nc4 = noclingo.NoFunction("a")
        nc5 = noclingo.NoSupremum

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
        nc = noclingo.NoFunction("atest")
        c =  clingo.Function("atest")
        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.type, noclingo.SymbolType.Function)

        nc1 = noclingo.NoFunction("aaaa")
        nc2 = noclingo.NoString("bbb")
        nc3 = noclingo.NoFunction("ccc",[noclingo.NoNumber(10)])
        c1 = clingo.Function("aaaa")
        c2 = clingo.String("bbb")
        c3 = clingo.Function("ccc",[clingo.Number(10)])

        nc = noclingo.NoFunction("atest",[nc1,nc2,nc3])
        c =  clingo.Function("atest", [c1,c2,c3])

        self.assertEqual(str(nc), str(c))
        self.assertEqual(nc.name, c.name)
        self.assertEqual(nc.name, "atest")
        self.assertEqual(len(nc.arguments), len(c.arguments))
        self.assertEqual(nc.arguments[0].name, c.arguments[0].name)
        self.assertEqual(nc.arguments[0].name, "aaaa")
        self.assertEqual(nc.arguments[1].string, c.arguments[1].string)

        nc4 = noclingo.NoFunction("ccc",[noclingo.NoNumber(10)],False)
        c4 = clingo.Function("ccc",[clingo.Number(10)],False)
        self.assertEqual(str(nc4), str(c4))
        self.assertEqual(nc4.positive, c4.positive)
        self.assertEqual(nc4.negative, c4.negative)

    def test_tuple(self):
        nc1 = noclingo.NoFunction("aaaa")
        nc2 = noclingo.NoString("bbb")
        c1 = clingo.Function("aaaa")
        c2 = clingo.String("bbb")
        nc = noclingo.NoFunction("", [nc1,nc2])
        c =  clingo.Function("", [c1,c2])

        self.assertEqual(str(nc), str(c))

        # Check that a tuple with a single element is represented correctly
        nc_one_tuple = noclingo.NoFunction("", [nc2])
        c_one_tuple = clingo.Function("", [c2])
        self.assertEqual(str(nc_one_tuple), str(c_one_tuple))

        # Check using the convenience Tuple_() function
        self.assertEqual(noclingo.NoTuple_([nc2]), nc_one_tuple)
        self.assertEqual(noclingo.NoTuple_([nc1,nc2]), nc)

    def test_hash_and_equality_comparison_ops(self):
        nc1 = noclingo.NoString("aaaGGDFa")
        nc2 = noclingo.NoString("aaaGGDFa")
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        nc1 = noclingo.NoNumber(34068390)
        nc2 = noclingo.NoNumber(34068390)
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        nc1 = noclingo.NoFunction("aaaa")
        nc2 = noclingo.NoFunction("aaaa")
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        nc1 = noclingo.NoFunction("aaaa",[],False)
        nc2 = noclingo.NoFunction("aaaa",[],False)
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

        a1 = noclingo.NoFunction("aaaa")
        a2 = noclingo.NoFunction("aaaa")
        b1 = noclingo.NoString("bbb")
        b2 = noclingo.NoString("bbb")
        c1 = noclingo.NoNumber(45)
        c2 = noclingo.NoNumber(45)
        d1 = noclingo.NoFunction("dfdf",[c1])
        d2 = noclingo.NoFunction("dfdf",[c2])
        nc1 = noclingo.NoFunction("ccc",[a1,b1,c1,d1])
        nc2 = noclingo.NoFunction("ccc",[a2,b2,c2,d2])
        self.assertEqual(hash(nc1),hash(nc2))
        self.assertTrue(nc1 == nc2)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 >= nc2)

    def test_comparison_ops(self):
        nc1 = noclingo.NoNumber(34)
        nc2 = noclingo.NoNumber(43)
        self.assertTrue(nc1 <= nc2)
        self.assertTrue(nc1 < nc2)
        self.assertTrue(nc2 >= nc1)
        self.assertTrue(nc2 > nc1)

        nc3 = noclingo.NoString("abcd")
        nc4 = noclingo.NoString("bcde")
        self.assertTrue(nc3 <= nc4)
        self.assertTrue(nc3 < nc4)
        self.assertTrue(nc4 >= nc3)
        self.assertTrue(nc4 > nc3)

        nc5 = noclingo.NoFunction("abc",[noclingo.NoNumber(45)])
        nc6 = noclingo.NoFunction("abc",[noclingo.NoString("45")])
        c5 = clingo.Function("abc",[clingo.Number(45)])
        c6 = clingo.Function("abc",[clingo.String("45")])
        if c5 < c6: self.assertTrue(nc5 < nc6)
        else: self.assertTrue(nc5 > nc6)

        nc7 = noclingo.NoFunction("abc",[noclingo.NoString("45"), noclingo.NoNumber(5)])
        self.assertTrue(nc6 < nc7)

        def compare_ordering(a, b):
            if noclingo_to_clingo(a) < noclingo_to_clingo(b):
                self.assertTrue(a < b)
            elif noclingo_to_clingo(b) < noclingo_to_clingo(a):
                self.assertTrue(b < a)
            else:
                self.assertEqual(a, b)

        compare_ordering(noclingo.NoString("1"), noclingo.NoNumber(2))
        compare_ordering(noclingo.NoNumber(1), noclingo.NoString("2"))
        compare_ordering(noclingo.NoString("1"), noclingo.NoFunction("2"))
        compare_ordering(noclingo.NoFunction("2"), noclingo.NoString("1"))
        compare_ordering(noclingo.NoNumber(1), noclingo.NoFunction("2"))
        compare_ordering(noclingo.NoFunction("1"), noclingo.NoNumber(2))
        compare_ordering(noclingo.NoInfimum, noclingo.NoSupremum)
        compare_ordering(noclingo.NoSupremum, noclingo.NoInfimum)
        compare_ordering(noclingo.NoInfimum, noclingo.NoNumber(2))
        compare_ordering(noclingo.NoInfimum, noclingo.NoString("2"))
        compare_ordering(noclingo.NoInfimum, noclingo.NoFunction("2"))
        compare_ordering(noclingo.NoSupremum, noclingo.NoFunction("2"))
        compare_ordering(noclingo.NoSupremum, noclingo.NoString("2"))
        compare_ordering(noclingo.NoSupremum, noclingo.NoNumber(2))



    # NOTE: I think in clingo 5.5 the comparison operators correctly return
    # NotImplemented so that we can implement the comparison between Symbol and
    # NoSymbol objects.
    def _clingo_pre5_5_test_clingo_noclingo_difference(self):
        self.assertNotEqual(clingo.String("blah"), noclingo.NoString("blah"))
        self.assertNotEqual(clingo.Number(5), noclingo.NoNumber(5))


    def test_clingo_to_noclingo(self):

        # Converting the Infimum and Supremum
        cli = clingo.Infimum
        ncli = noclingo.NoInfimum
        cls = clingo.Supremum
        ncls = noclingo.NoSupremum

        self.assertEqual(clingo_to_noclingo(cli), ncli)
        self.assertEqual(clingo_to_noclingo(cls), ncls)
        self.assertEqual(noclingo_to_clingo(ncli), cli)
        self.assertEqual(noclingo_to_clingo(ncls), cls)

        # Converting simple structures
        cl1 = clingo.Function("const")
        ncl1 = noclingo.NoFunction("const")
        cl2 = clingo.Number(3)
        ncl2 = noclingo.NoNumber(3)
        cl3 = clingo.String("No")
        ncl3 = noclingo.NoString("No")

        self.assertEqual(clingo_to_noclingo(cl1),ncl1)
        self.assertEqual(clingo_to_noclingo(cl2),ncl2)
        self.assertEqual(clingo_to_noclingo(cl3),ncl3)
        self.assertEqual(noclingo_to_clingo(ncl1),cl1)
        self.assertEqual(noclingo_to_clingo(ncl2),cl2)
        self.assertEqual(noclingo_to_clingo(ncl3),cl3)

        # More complex function structures
        cl4 = clingo.Function("",[cl1,cl2])
        ncl4 = noclingo.NoFunction("",[ncl1,ncl2])
        self.assertEqual(clingo_to_noclingo(cl4),ncl4)
        self.assertEqual(noclingo_to_clingo(ncl4),cl4)

        cl5 = clingo.Function("f",[cl3,cl4,cl1],False)
        ncl5 = noclingo.NoFunction("f",[ncl3,ncl4,ncl1],False)
        self.assertEqual(clingo_to_noclingo(cl5),ncl5)
        self.assertEqual(noclingo_to_clingo(ncl5),cl5)

        # If it is already the correct symbol type then no conversion required
        self.assertEqual(clingo_to_noclingo(ncl1), ncl1)
        self.assertEqual(noclingo_to_clingo(cl1), cl1)
        self.assertTrue(clingo_to_noclingo(ncl1) is ncl1)
        self.assertTrue(noclingo_to_clingo(cl1) is cl1)


    def test_comparison_nosymbol_and_symbol(self):
        cl_infimum = clingo.Infimum
        ncl_infimum = noclingo.NoInfimum
        cl_supremum = clingo.Supremum
        ncl_supremum = noclingo.NoSupremum
        cl_constant1 = clingo.Function("const1")
        ncl_constant1 = noclingo.NoFunction("const1")
        cl_constant2 = clingo.Function("const2")
        ncl_constant2 = noclingo.NoFunction("const2")
        cl_number1 = clingo.Number(1)
        ncl_number1 = noclingo.NoNumber(1)
        cl_number2 = clingo.Number(2)
        ncl_number2 = noclingo.NoNumber(2)
        cl_string1 = clingo.String("No1")
        ncl_string1 = noclingo.NoString("No1")
        cl_string1 = clingo.String("No2")
        ncl_string1 = noclingo.NoString("No2")

        return

        self.assertTrue(ncl_infimum == cl_infimum)
        self.assertTrue(cl_infimum == ncl_infimum)
        self.assertTrue(ncl_constant1 == cl_constant1)
        self.assertTrue(cl_constant1 == ncl_constant1)
        self.assertTrue(ncl_constant1 == cl_constant1)

        x = clingo.Function("b", positive=False)
        y = clingo.Function("a", positive=True)

        print("HERE")
        self.assertTrue(x > y)
        return
        

        
    def XXX_test_set_symbol_mode_when_noclingo_disabled(self):

        with self.assertRaises(RuntimeError) as ctx:
            set_symbol_mode(SymbolMode.CLINGO)

        check_errmsg("NOCLINGO mode is disabled.",ctx)


#------------------------------------------------------------------------------
# Tests that require NOCLINGO is enabled and run from a new process
#------------------------------------------------------------------------------


class NoClingoEnabledTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    def test_symbol_generator(self):
        # By default CLINGO mode
        self.assertEqual(get_symbol_mode(), SymbolMode.CLINGO)

        cli = clingo.Infimum
        cls = clingo.Supremum
        cl1 = clingo.Function("const")
        cl2 = clingo.Number(3)
        cl3 = clingo.String("No")
        cl4 = clingo.Function("",[cl1,cl2])
        cl5 = clingo.Function("f",[cl3,cl4,cl1],False)

        ncli = noclingo.NoInfimum
        ncls = noclingo.NoSupremum
        ncl1 = noclingo.NoFunction("const")
        ncl2 = noclingo.NoNumber(3)
        ncl3 = noclingo.NoString("No")
        ncl4 = noclingo.NoFunction("",[ncl1,ncl2])
        ncl5 = noclingo.NoFunction("f",[ncl3,ncl4,ncl1],False)

        set_symbol_mode(SymbolMode.CLINGO)
        self.assertEqual(get_symbol_mode(), SymbolMode.CLINGO)

        expect_cli = get_Infimum()
        expect_cls = get_Supremum()
        expect_cl1 = Function("const")
        expect_cl2 = Number(3)
        expect_cl3 = String("No")
        expect_cl4 = Function("",[expect_cl1, expect_cl2])
        expect_cl5 = Function("f",[expect_cl3,expect_cl4,expect_cl1], False)

        set_symbol_mode(SymbolMode.NOCLINGO)
        self.assertEqual(get_symbol_mode(), SymbolMode.NOCLINGO)

        expect_ncli = get_Infimum()
        expect_ncls = get_Supremum()
        expect_ncl1 = Function("const")
        expect_ncl2 = Number(3)
        expect_ncl3 = String("No")
        expect_ncl4 = Function("",[expect_ncl1, expect_ncl2])
        expect_ncl5 = Function("f",[expect_ncl3, expect_ncl4, expect_ncl1], False)

        # Set back to the default
        set_symbol_mode(SymbolMode.CLINGO)

        self.assertEqual(cli, expect_cli)
        self.assertEqual(cls, expect_cls)
        self.assertEqual(cl1, expect_cl1)
        self.assertEqual(cl2, expect_cl2)
        self.assertEqual(cl3, expect_cl3)
        self.assertEqual(cl4, expect_cl4)
        self.assertEqual(cl5, expect_cl5)

        self.assertEqual(ncli, expect_ncli)
        self.assertEqual(ncls, expect_ncls)
        self.assertEqual(ncl1, expect_ncl1)
        self.assertEqual(ncl2, expect_ncl2)
        self.assertEqual(ncl3, expect_ncl3)
        self.assertEqual(ncl4, expect_ncl4)
        self.assertEqual(ncl5, expect_ncl5)



#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
