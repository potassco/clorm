#------------------------------------------------------------------------------
# Unit tests for the peewee based data model
#------------------------------------------------------------------------------

import unittest
from clingo import Number, String, Function
from asphelper.orm import \
    _integer_cltopy, _string_cltopy, _constant_cltopy, \
    _integer_pytocl, _string_pytocl, _constant_pytocl, \
    _integer_unifies, _string_unifies, _constant_unifies, \
    BasePredicate, \
    IntegerField, StringField, ConstantField, FunctionField, TupleField, ComplexField, \
    process_facts

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
    def test_pytocl_and_cltopy_and_unifies(self):
        num1 = 1
        str1 = "string"
        sim1 = "name"
        cnum1 = Number(num1)
        cstr1 = String(str1)
        csim1 = Function(sim1,[])
        self.assertEqual(num1, _integer_cltopy(cnum1))
        self.assertEqual(str1, _string_cltopy(cstr1))
        self.assertEqual(sim1, _constant_cltopy(csim1))

        self.assertEqual(cnum1, _integer_pytocl(num1))
        self.assertEqual(cstr1, _string_pytocl(str1))
        self.assertEqual(csim1, _constant_pytocl(sim1))

        self.assertTrue(_integer_unifies(cnum1))
        self.assertTrue(_string_unifies(cstr1))
        self.assertTrue(_constant_unifies(csim1))

        self.assertFalse(_integer_unifies(csim1))
        self.assertFalse(_string_unifies(cnum1))
        self.assertFalse(_constant_unifies(cstr1))

        fint = IntegerField()
        fstr = StringField()
        fconst = ConstantField()

        self.assertTrue(fint.unifies(cnum1))
        self.assertTrue(fstr.unifies(cstr1))
        self.assertTrue(fconst.unifies(csim1))

    #--------------------------------------------------------------------------
    # Test the use of getters and setters are correct
    #--------------------------------------------------------------------------
    def test_field_inout_functions(self):

        # Create an integer field but we want to interface to it using reals
        # with 100 x scaling.
        class Fact(BasePredicate):
            anum = IntegerField(infunc=lambda x: int(x*100),
                                outfunc=lambda x: x/100.0,
                                default=1.5)
        f1=Function("fact",[Number(150)])
        f2=Function("fact",[Number(50)])

        af1=Fact()
        af2=Fact(anum=0.5)
        self.assertEqual(f1, af1._raw)
        self.assertEqual(f2, af2._raw)
        self.assertEqual(af1.anum, 1.5)
        self.assertEqual(af2.anum, 0.5)

    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_predicate_init(self):

        class Fact(BasePredicate):
            anum = IntegerField(default=1)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(astr="test")
        f2=Fact(1,"test")

        self.assertEqual(f1, f2)
        self.assertEqual(f1._raw, func)

    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_simple_predicate_defn(self):

        # Test a bad declaration - the field name starts with an "_"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(BasePredicate):
                _afield = IntegerField()

        # Test declaration of predicate with an implicit name
        class ImplicitlyNamedPredicate(BasePredicate):
            afield = IntegerField()

        inp1 = ImplicitlyNamedPredicate(afield=2)
        inp2 = Function("implicitlyNamedPredicate",[Number(2)])
        self.assertEqual(inp1._raw, inp2)

        # Test declaration of a unary predicate
        class UnaryPredicate(BasePredicate):
            class Meta: name = "unary"

        up1 = UnaryPredicate()
        up2 = Function("unary",[])
        self.assertEqual(up1._raw, up2)

        # Test the class properties; when access from the class and the object.
        self.assertEqual(up1._name, "unary")
        self.assertEqual(UnaryPredicate._name, "unary")
        self.assertEqual(up1._arity, 0)
        self.assertEqual(UnaryPredicate._arity, 0)

        # Test that default fields work and that not specifying a value raises
        # an exception
        class DefaultFieldPredicate(BasePredicate):
            first = IntegerField()
            second = IntegerField(default=10)
            class Meta: name = "dfp"

        dfp1 = DefaultFieldPredicate(first=15)
        dfp2 = Function("dfp",[Number(15),Number(10)])
        self.assertEqual(dfp1._raw, dfp2)

        with self.assertRaises(ValueError) as ctx:
            dfp3 = DefaultFieldPredicate()

        # Test declaration of predicates with Simple and String fields
        class MultiFieldPredicate(BasePredicate):
            afield1 = StringField()
            afield2 = ConstantField()
            class Meta: name = "mfp"

        mfp1 = MultiFieldPredicate(afield1="astring", afield2="asimple")
        mfp2 = Function("mfp", [String("astring"), Function("asimple",[])])
        self.assertEqual(mfp1._raw, mfp2)

        # Test that the appropriate field properties are set up properly
        self.assertEqual(mfp1.afield1, "astring")
        self.assertEqual(mfp1.afield2, "asimple")

    #--------------------------------------------------------------------------
    # Test that we can define predicates with Function and Tuple fields
    # --------------------------------------------------------------------------
    def test_complex_predicate_defn(self):

        class Fun(BasePredicate):
            aint = IntegerField(infunc=lambda x: int(x*100), outfunc=lambda x: x/100.0)
            astr = StringField()

        class MyTuple(BasePredicate):
            aint = IntegerField()
            astr = StringField()
            class Meta: name = ""

        # A fact definition
        class Fact(BasePredicate):
            aint = IntegerField()
            atup = TupleField(fields=[IntegerField(), StringField()],default=(2,"str"))
            afunc = FunctionField(name="fun",
                                  fields=[IntegerField(infunc=lambda x: int(x*100),
                                                       outfunc=lambda x: x/100.0),
                                          StringField()],
                                  default=(2.0,"str"))
        # Alternative fact definition
        class FactAlt(BasePredicate):
            aint = IntegerField()
            atup = ComplexField(defn=MyTuple,default=MyTuple(aint=2,astr="str"))
            afunc = ComplexField(defn=Fun,default=Fun(aint=2.0,astr="str"))
            class Meta: name = "fact"

        af1=Fact(aint=1)
        af2=Fact(aint=2, atup=(4,"XXX"), afunc=(5.5,"YYY"))
        bf1=FactAlt(aint=1)
        bf2=FactAlt(aint=2, atup=MyTuple(aint=4,astr="XXX"), afunc=Fun(aint=5.5,astr="YYY"))

        f1 = Function("fact",[Number(1),
                              Function("",[Number(2),String("str")]),
                              Function("fun",[Number(200),String("str")])])
        f2 = Function("fact",[Number(2),
                              Function("",[Number(4),String("XXX")]),
                              Function("fun",[Number(550),String("YYY")])])

        self.assertEqual(f1, af1._raw)
        self.assertEqual(f2, af2._raw)
        self.assertEqual(af1, bf1)
        self.assertEqual(af2, bf2)

        self.assertEqual(bf2.atup.aint,4)

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_predicate_operator_overloads(self):
        class Fact(BasePredicate):
            anum = IntegerField()

        f1 = Function("fact", [Number(1)])

        af1 = Fact(anum=1)
        af2 = Fact(anum=2)
        af1_c = Fact(anum=1)

        self.assertEqual(f1, af1._raw)
        self.assertEqual(af1, f1)
        self.assertEqual(f1, af1)
        self.assertEqual(af1,af1_c)
        self.assertNotEqual(af1, af2)
        self.assertEqual(str(f1), str(af1))

        f2 = Function("fact", [Number(2)])
        self.assertTrue(af1 <  af2)
        self.assertTrue(af1 <  f2)
        self.assertTrue(af1 <=  af2)
        self.assertTrue(af1 <=  f2)
        self.assertTrue(af2 >  af1)
        self.assertTrue(f2 >  af1)
        self.assertTrue(af2 >=  af1)
        self.assertTrue(f2 >=  af1)

    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_predicate(self):
        class Fact(BasePredicate):
            anum = IntegerField()
            astr = StringField()
            asim = ConstantField()

        gfact1_sym = Function("fact",[Number(1),String("Dave"),Function("ok",[])])
        gfact1_pred = Fact(_symbol=gfact1_sym)
        self.assertEqual(gfact1_pred.anum, 1)
        self.assertEqual(gfact1_pred.astr, "Dave")
        self.assertEqual(gfact1_pred.asim, "ok")

        bfact1_sym = Function("fact",[String("1"),String("Dave"),Function("ok",[])])
        with self.assertRaises(ValueError) as ctx:
            bfact1_pred = Fact(_symbol=bfact1_sym)

    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_complex_predicate(self):

        class Fact(BasePredicate):
            afun = FunctionField(name="fun", fields=[IntegerField(),StringField()])

        class Fun(BasePredicate):
            aint=IntegerField()
            astr=StringField()

        class FactAlt(BasePredicate):
            afun = ComplexField(defn=Fun)
            class Meta: name="fact"

        good_fact_symbol1 = Function("fact",[Function("fun",[Number(1),String("Dave")])])
        good_fact_pred1 = Fact(_symbol=good_fact_symbol1)
        good_factalt_pred1 = FactAlt(_symbol=good_fact_symbol1)
        self.assertEqual(good_fact_pred1.afun, (1,"Dave"))

        bad_fact_symbol1 = Function("fact",[Function("fun",[Number(1)])])
        with self.assertRaises(ValueError) as ctx:
            bad_fact_pred1 = Fact(_symbol=bad_fact_symbol1)


    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------

    def test_process_model(self):
        class Fact(BasePredicate):
            anum = IntegerField()
        class FactAlt(BasePredicate):
            anum = IntegerField()
            astr = StringField()
            class Meta: name = "fact"
        class Fact2(BasePredicate):
            anum = IntegerField()

        f1 = Function("fact", [Number(1)])
        f2 = Function("fact", [Number(2)])
        f3 = Function("fact", [Number(3), String("blah")])
        f4 = Function("fact2", [Number(1)])
        f5 = Function("fact2", [Number(2)])
        f6 = Function("fact3", [Number(1)])

        af1 = Fact(anum=1)
        af2 = Fact(anum=2)
        af3 = FactAlt(anum=3,astr="blah")
        af4 = Fact2(anum=1)
        af5 = Fact2(anum=2)

        results = process_facts([f1,f2,f3,f4,f5,f6], [Fact,FactAlt,Fact2])
        self.assertEqual(len(results), 3)
        self.assertEqual(len(results[Fact]),2)
        self.assertEqual(len(results[FactAlt]),1)
        self.assertEqual(len(results[Fact2]),2)
        self.assertEqual(results[Fact], [af1,af2])
        self.assertEqual(results[FactAlt], [af3])
        self.assertEqual(results[Fact2], [af4,af5])

    #--------------------------------------------------------------------------
    # 
    #--------------------------------------------------------------------------

    def _test_dfdfd(self):
        aspstr = "fact(1). fact(2). fact(3, \"blah\"). fact2(1). fact2(2)."
        ctrl = Control()
        with ctrl.builder() as b:
            clingo.parse_program(aspstr, lambda stmt: b.add(stmt))

        def on_model(model):
            pass

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
