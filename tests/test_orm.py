#------------------------------------------------------------------------------
# Unit tests for the peewee based data model
#------------------------------------------------------------------------------

import unittest
from clingo import Number, String, Function
from asphelper.orm import \
    number_getter, string_getter, simple_getter, \
    number_setter, string_setter, simple_setter, \
    BasePredicate, NumberField, StringField, SimpleField

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class ORMTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Simple test to make sure the default getters and setters are correct
    #--------------------------------------------------------------------------
    def test_default_getters_and_setters(self):
        num1 = 1
        str1 = "string"
        sim1 = "name"
        cnum1 = Number(num1)
        cstr1 = String(str1)
        csim1 = Function(sim1,[])
        self.assertEqual(num1, number_getter(cnum1))
        self.assertEqual(str1, string_getter(cstr1))
        self.assertEqual(sim1, simple_getter(csim1))

        self.assertEqual(cnum1, number_setter(num1))
        self.assertEqual(cstr1, string_setter(str1))
        self.assertEqual(csim1, simple_setter(sim1))

    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_predicate_defn(self):

        # Test declaration of predicate with an implicit name
        class ImplicitlyNamedPredicate(BasePredicate):
            afield = NumberField()

        inp1 = ImplicitlyNamedPredicate(afield=2)
        inp2 = Function("implicitlyNamedPredicate",[Number(2)])
        self.assertEqual(inp1.raw, inp2)

        # Test declaration of a unary predicate
        class UnaryPredicate(BasePredicate):
            class Meta: name = "unary"

        up1 = UnaryPredicate()
        up2 = Function("unary",[])
        self.assertEqual(up1.raw, up2)

        # Test that default fields work and that not specifying a value raises an exception
        class DefaultFieldPredicate(BasePredicate):
            first = NumberField()
            second = NumberField(default=10)
            class Meta: name = "dfp"

        dfp1 = DefaultFieldPredicate(first=15)
        dfp2 = Function("dfp",[Number(15),Number(10)])
        self.assertEqual(dfp1.raw, dfp2)

        with self.assertRaises(ValueError) as ctx:
            dfp3 = DefaultFieldPredicate()

        # Test declaration of predicates with Simple and String fields
        class MultiFieldPredicate(BasePredicate):
            afield1 = StringField()
            afield2 = SimpleField()
            class Meta: name = "mfp"

        mfp1 = MultiFieldPredicate(afield1="astring", afield2="asimple")
        mfp2 = Function("mfp", [String("astring"), Function("asimple",[])])
        self.assertEqual(mfp1.raw, mfp2)

        # Test that the appropriate field properties are set up properly
        self.assertEqual(mfp1.afield1, "astring")
        self.assertEqual(mfp1.afield2, "asimple")

    #--------------------------------------------------------------------------
    # Test asserting predicate instances to clingo and extracting the result
    # --------------------------------------------------------------------------
    def test_predicate_to_clingo(self):
        pass

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
