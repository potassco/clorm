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
from clorm.orm.noclingo import clingo_to_noclingo, noclingo_to_clingo, \
    SymbolMode, get_symbol_generator, _get_symboltype, \
    is_Number, is_String, is_Function, is_Supremum, is_Infimum

clingo_version = clingo.__version__

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

        # Note: ordering comparision between SymbolTypes is not supported in 5.5.0+
        if clingo_version >= "5.5.0": return

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
        self.assertEqual(nc.string, c.string)
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

        nc4 = noclingo.Function("ccc",[noclingo.Number(10)],False)
        c4 = clingo.Function("ccc",[clingo.Number(10)],False)
        self.assertEqual(str(nc4), str(c4))
        self.assertEqual(nc4.positive, c4.positive)
        self.assertEqual(nc4.negative, c4.negative)

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

        nc1 = noclingo.Function("aaaa",[],False)
        nc2 = noclingo.Function("aaaa",[],False)
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


    def test_clingo_to_noclingo(self):

        # Converting the Infimum and Supremum
        cli = clingo.Infimum
        ncli = noclingo.Infimum
        cls = clingo.Supremum
        ncls = noclingo.Supremum

        self.assertEqual(clingo_to_noclingo(cli),ncli)
        self.assertEqual(clingo_to_noclingo(cls),ncls)
        self.assertEqual(noclingo_to_clingo(ncli),cli)
        self.assertEqual(noclingo_to_clingo(ncls),cls)

        # Converting simple structures
        cl1 = clingo.Function("const")
        ncl1 = noclingo.Function("const")
        cl2 = clingo.Number(3)
        ncl2 = noclingo.Number(3)
        cl3 = clingo.String("No")
        ncl3 = noclingo.String("No")

        self.assertEqual(clingo_to_noclingo(cl1),ncl1)
        self.assertEqual(clingo_to_noclingo(cl2),ncl2)
        self.assertEqual(clingo_to_noclingo(cl3),ncl3)
        self.assertEqual(noclingo_to_clingo(ncl1),cl1)
        self.assertEqual(noclingo_to_clingo(ncl2),cl2)
        self.assertEqual(noclingo_to_clingo(ncl3),cl3)


        # More complex function structures
        cl4 = clingo.Function("",[cl1,cl2])
        ncl4 = noclingo.Function("",[ncl1,ncl2])
        self.assertEqual(clingo_to_noclingo(cl4),ncl4)
        self.assertEqual(noclingo_to_clingo(ncl4),cl4)

        cl5 = clingo.Function("f",[cl3,cl4,cl1],False)
        ncl5 = noclingo.Function("f",[ncl3,ncl4,ncl1],False)
        self.assertEqual(clingo_to_noclingo(cl5),ncl5)
        self.assertEqual(noclingo_to_clingo(ncl5),cl5)


    def test_get_symboltype(self):
        cli = clingo.Infimum
        cls = clingo.Supremum
        cl1 = clingo.Function("const")
        cl2 = clingo.Number(3)
        cl3 = clingo.String("No")
        cl4 = clingo.Function("",[cl1,cl2])

        ncli = noclingo.Infimum
        ncls = noclingo.Supremum
        ncl1 = noclingo.Function("const")
        ncl2 = noclingo.Number(3)
        ncl3 = noclingo.String("No")
        ncl4 = noclingo.Function("",[ncl1,ncl2])

        self.assertEqual(_get_symboltype(cli),noclingo.SymbolType.Infimum)
        self.assertEqual(_get_symboltype(cls),noclingo.SymbolType.Supremum)
        self.assertEqual(_get_symboltype(cl1),noclingo.SymbolType.Function)
        self.assertEqual(_get_symboltype(cl2),noclingo.SymbolType.Number)
        self.assertEqual(_get_symboltype(cl3),noclingo.SymbolType.String)
        self.assertEqual(_get_symboltype(cl4),noclingo.SymbolType.Function)

        self.assertEqual(_get_symboltype(ncli),noclingo.SymbolType.Infimum)
        self.assertEqual(_get_symboltype(ncls),noclingo.SymbolType.Supremum)
        self.assertEqual(_get_symboltype(ncl1),noclingo.SymbolType.Function)
        self.assertEqual(_get_symboltype(ncl2),noclingo.SymbolType.Number)
        self.assertEqual(_get_symboltype(ncl3),noclingo.SymbolType.String)
        self.assertEqual(_get_symboltype(ncl4),noclingo.SymbolType.Function)

        self.assertNotEqual(_get_symboltype(cls),noclingo.SymbolType.Infimum)
        self.assertNotEqual(_get_symboltype(cli),noclingo.SymbolType.Supremum)
        self.assertNotEqual(_get_symboltype(cl2),noclingo.SymbolType.Function)
        self.assertNotEqual(_get_symboltype(cl4),noclingo.SymbolType.Number)
        self.assertNotEqual(_get_symboltype(cl4),noclingo.SymbolType.String)
        self.assertNotEqual(_get_symboltype(cl3),noclingo.SymbolType.Function)

        with self.assertRaises(TypeError) as ctx:
            x=_get_symboltype(4)

    def test_is_functions(self):
        cli = clingo.Infimum
        cls = clingo.Supremum
        cl1 = clingo.Function("const")
        cl2 = clingo.Number(3)
        cl3 = clingo.String("No")
        cl4 = clingo.Function("",[cl1,cl2])

        ncli = noclingo.Infimum
        ncls = noclingo.Supremum
        ncl1 = noclingo.Function("const")
        ncl2 = noclingo.Number(3)
        ncl3 = noclingo.String("No")
        ncl4 = noclingo.Function("",[ncl1,ncl2])

        self.assertTrue(is_Infimum(cli))
        self.assertTrue(is_Infimum(ncli))

        self.assertTrue(is_Supremum(cls))
        self.assertTrue(is_Supremum(ncls))

        self.assertTrue(is_Number(cl2))
        self.assertTrue(is_Number(ncl2))

        self.assertTrue(is_String(cl3))
        self.assertTrue(is_String(ncl3))

        self.assertTrue(is_Function(cl4))
        self.assertTrue(is_Function(ncl4))

        self.assertFalse(is_Infimum(cls))
        self.assertFalse(is_Supremum(cli))
        self.assertFalse(is_Function(cli))
        self.assertFalse(is_Number(cli))
        self.assertFalse(is_String(cli))
        self.assertFalse(is_Supremum(4))



    def test_symbol_generator(self):
        csg = get_symbol_generator(SymbolMode.CLINGO)
        ncsg = get_symbol_generator(SymbolMode.NOCLINGO)

        self.assertEqual(csg.mode,SymbolMode.CLINGO)
        self.assertEqual(ncsg.mode,SymbolMode.NOCLINGO)

        cli = clingo.Infimum
        cls = clingo.Supremum
        cl1 = clingo.Function("const")
        cl2 = clingo.Number(3)
        cl3 = clingo.String("No")
        cl4 = clingo.Function("",[cl1,cl2])
        cl5 = clingo.Function("f",[cl3,cl4,cl1],False)

        ncli = noclingo.Infimum
        ncls = noclingo.Supremum
        ncl1 = noclingo.Function("const")
        ncl2 = noclingo.Number(3)
        ncl3 = noclingo.String("No")
        ncl4 = noclingo.Function("",[ncl1,ncl2])
        ncl5 = noclingo.Function("f",[ncl3,ncl4,ncl1],False)

        csg_cli = csg.Infimum
        csg_cls = csg.Supremum
        csg_cl1 = csg.Function("const")
        csg_cl2 = csg.Number(3)
        csg_cl3 = csg.String("No")
        csg_cl4 = csg.Function("",[cl1,cl2])
        csg_cl5 = csg.Function("f",[cl3,cl4,cl1],False)

        ncsg_ncli = ncsg.Infimum
        ncsg_ncls = ncsg.Supremum
        ncsg_ncl1 = ncsg.Function("const")
        ncsg_ncl2 = ncsg.Number(3)
        ncsg_ncl3 = ncsg.String("No")
        ncsg_ncl4 = ncsg.Function("",[ncsg_ncl1,ncsg_ncl2])
        ncsg_ncl5 = ncsg.Function("f",[ncsg_ncl3,ncsg_ncl4,ncsg_ncl1],False)

        self.assertEqual(cli,csg_cli)
        self.assertEqual(cls,csg_cls)
        self.assertEqual(cl1,csg_cl1)
        self.assertEqual(cl2,csg_cl2)
        self.assertEqual(cl3,csg_cl3)
        self.assertEqual(cl4,csg_cl4)
        self.assertEqual(cl5,csg_cl5)

        self.assertEqual(ncli,ncsg_ncli)
        self.assertEqual(ncls,ncsg_ncls)
        self.assertEqual(ncl1,ncsg_ncl1)
        self.assertEqual(ncl2,ncsg_ncl2)
        self.assertEqual(ncl3,ncsg_ncl3)
        self.assertEqual(ncl4,ncsg_ncl4)
        self.assertEqual(ncl5,ncsg_ncl5)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
