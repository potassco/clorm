#------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
#------------------------------------------------------------------------------

import inspect
import unittest
import datetime
import calendar
import operator
from clingo import Number, String, Function,  __version__ as clingo_version
from clingo import Control
from clorm.orm import \
    NonLogicalSymbol, Predicate, ComplexTerm, \
    IntegerField, StringField, ConstantField, RawField, \
    define_field_restriction, \
    not_, and_, or_, _StaticComparator, _get_term_comparators, \
    ph_, ph1_, ph2_, \
    _FactIndex, _FactMap, \
    unify, desc, FactBase, FactBaseBuilder, \
    TypeCastSignature, make_function_asp_callable, make_method_asp_callable

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'ORMTestCase',
    'FactIndexTestCase',
    'FactMapTestCase',
    'FactBaseTestCase',
    'SelectTestCase',
    'TypeCastSignatureTestCase'
    ]

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
    def test_simpleterms(self):


        symstr = String("SYM")
        self.assertEqual(type(StringField.cltopy(symstr)), str)
        self.assertEqual(StringField.cltopy(symstr), "SYM")
        self.assertEqual(StringField.pytocl("SYM"), symstr)

        symstr = Function("const")
        self.assertEqual(type(ConstantField.cltopy(symstr)), str)
        self.assertEqual(ConstantField.cltopy(symstr), "const")
        self.assertEqual(ConstantField.pytocl("const"), symstr)

        symstr = Number(1)
        self.assertEqual(type(IntegerField.cltopy(symstr)), int)
        self.assertEqual(IntegerField.cltopy(symstr), 1)
        self.assertEqual(IntegerField.pytocl(1), symstr)


        with self.assertRaises(TypeError) as ctx:
            class DateField(StringField, StringField):
                pass

        class DateField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

        symstr = String("20180101")
        dt = datetime.date(2018,1,1)
        self.assertEqual(DateField.cltopy(symstr), dt)
        self.assertEqual(DateField.pytocl(dt), symstr)

        class PartialField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")

        with self.assertRaises(NotImplementedError) as ctx:
            symstr = String("20180101")
            dt = datetime.date(2018,1,1)
            self.assertEqual(PartialField.cltopy(symstr), dt)

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
        self.assertEqual(num1, IntegerField.cltopy(cnum1))
        self.assertEqual(str1, StringField.cltopy(cstr1))
        self.assertEqual(sim1, ConstantField.cltopy(csim1))

        self.assertEqual(cnum1, IntegerField.pytocl(num1))
        self.assertEqual(cstr1, StringField.pytocl(str1))
        self.assertEqual(csim1, ConstantField.pytocl(sim1))

        self.assertTrue(IntegerField.unifies(cnum1))
        self.assertTrue(StringField.unifies(cstr1))
        self.assertTrue(ConstantField.unifies(csim1))

        self.assertFalse(IntegerField.unifies(csim1))
        self.assertFalse(StringField.unifies(cnum1))
        self.assertFalse(ConstantField.unifies(cstr1))

        fint = IntegerField()
        fstr = StringField()
        fconst = ConstantField()

        self.assertTrue(fint.unifies(cnum1))
        self.assertTrue(fstr.unifies(cstr1))
        self.assertTrue(fconst.unifies(csim1))

    #--------------------------------------------------------------------------
    # Simple test to make sure the default getters and setters are correct
    #--------------------------------------------------------------------------
    def test_raw_term(self):

        raw1 = Function("func",[Number(1)])
        raw2 = Function("bob",[String("no")])
        rf1 = RawField()
        rf2 = RawField(default=raw1)
        rt1 = Function("tmp", [Number(1), raw1])
        rt2 = Function("tmp", [Number(1), raw2])
        self.assertTrue(rf1.unifies(raw1))

        class Tmp(Predicate):
            n1 = IntegerField()
            r1 = RawField()

        self.assertTrue(Tmp._unifies(rt1))
        self.assertTrue(Tmp._unifies(rt2))
        t1 = Tmp(1,raw1)
        t2 = Tmp(1,raw2)

        self.assertEqual(set([f for f in unify([Tmp], [rt1,rt2])]),set([t1,t2]))
        self.assertEqual(t1.r1, raw1)
        self.assertEqual(t2.r1, raw2)

    #--------------------------------------------------------------------------
    # Simple test to make sure the default getters and setters are correct
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Test setting index for a term
    #--------------------------------------------------------------------------
    def test_term_index(self):
        fint1 = IntegerField()
        fstr1 = StringField()
        fconst1 = ConstantField()
        fint2 = IntegerField(index=True)
        fstr2 = StringField(index=True)
        fconst2 = ConstantField(index=True)

        self.assertFalse(fint1.index)
        self.assertFalse(fstr1.index)
        self.assertFalse(fconst1.index)
        self.assertTrue(fint2.index)
        self.assertTrue(fstr2.index)
        self.assertTrue(fconst2.index)

    #--------------------------------------------------------------------------
    # Test catching invalid default values for a field
    #--------------------------------------------------------------------------
    def test_catch_bad_field_defaults(self):
        with self.assertRaises(TypeError) as ctx:
            fld = IntegerField(default="bad")

    #--------------------------------------------------------------------------
    # Test making a restriction of a field
    #--------------------------------------------------------------------------
    def test_define_field_restriction(self):
        dfr = define_field_restriction

        # Some bad calls
        with self.assertRaises(TypeError) as ctx:
            class Something(object):
                def __init__(self): self._a = 1

            fld = dfr("fld", Something, ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = dfr("fld", "notaclass", ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = dfr("fld", IntegerField, ["a"])

        # A good restriction
        ABCField = dfr("ABCField", ConstantField, ["a","b","c"])

        # Make sure it works
        r_a = Function("a",[])
        r_b = Function("b",[])
        r_c = Function("c",[])
        r_d = Function("d",[])
        r_1 = Number(1)

        # Test the pytocl direction
        self.assertEqual(ABCField.pytocl("a"), r_a)
        self.assertEqual(ABCField.pytocl("b"), r_b)
        self.assertEqual(ABCField.pytocl("c"), r_c)

        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl("d")

        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl(1)

        # Test the cltopy direction
        self.assertEqual(ABCField.cltopy(r_a), "a")
        self.assertEqual(ABCField.cltopy(r_b), "b")
        self.assertEqual(ABCField.cltopy(r_c), "c")
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_d)
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_1)

        self.assertTrue(ABCField.unifies(r_a))
        self.assertTrue(ABCField.unifies(r_b))
        self.assertTrue(ABCField.unifies(r_c))
        self.assertFalse(ABCField.unifies(r_d))
        self.assertFalse(ABCField.unifies(r_1))

        # Test a version with no class name
        ABCField2 = dfr(ConstantField, ["a","b","c"])
        self.assertEqual(ABCField2.pytocl("a"), r_a)

        # But only 2 and 3 arguments are valid
        with self.assertRaises(TypeError) as ctx:
            ABCField3 = dfr(["a","b","c"])
        with self.assertRaises(TypeError) as ctx:
            ABCField4 = dfr("ABCField", ConstantField, ["a","b","c"], 1)



    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_predicate_init(self):

        class Fact(Predicate):
            anum = IntegerField(default=1)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(astr="test")
        f2=Fact(1,"test")

        self.assertEqual(f1, f2)
        self.assertEqual(f1.raw, func)

    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_simple_predicate_defn(self):

        # Test bad declaration - the term name starts with an "_"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                _aterm = IntegerField()

        # Test bad declaration - the term name is "meta"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                meta = IntegerField()

        # Test bad declaration - the term name is "raw"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                raw = IntegerField()

        # Test declaration of predicate with an implicit name
        class ImplicitlyNamedPredicate(Predicate):
            aterm = IntegerField()

        inp1 = ImplicitlyNamedPredicate(aterm=2)
        inp2 = Function("implicitlyNamedPredicate",[Number(2)])
        self.assertEqual(inp1.raw, inp2)

        # Test declaration of a unary predicate
        class UnaryPredicate(Predicate):
            class Meta: name = "unary"

        up1 = UnaryPredicate()
        up2 = Function("unary",[])
        self.assertEqual(up1.raw, up2)

        # Test the class properties; when access from the class and the object.
        self.assertEqual(up1.meta.name, "unary")
        self.assertEqual(UnaryPredicate.meta.name, "unary")
        self.assertEqual(up1.meta.arity, 0)
        self.assertEqual(UnaryPredicate.meta.arity, 0)

        # Test that default terms work and that not specifying a value raises
        # an exception
        class DefaultFieldPredicate(Predicate):
            first = IntegerField()
            second = IntegerField(default=10)
            class Meta: name = "dfp"

        dfp1 = DefaultFieldPredicate(first=15)
        dfp2 = Function("dfp",[Number(15),Number(10)])
        self.assertEqual(dfp1.raw, dfp2)

        with self.assertRaises(ValueError) as ctx:
            dfp3 = DefaultFieldPredicate()

        # Test declaration of predicates with Simple and String terms
        class MultiFieldPredicate(Predicate):
            aterm1 = StringField()
            aterm2 = ConstantField()
            class Meta: name = "mfp"

        mfp1 = MultiFieldPredicate(aterm1="astring", aterm2="asimple")
        mfp2 = Function("mfp", [String("astring"), Function("asimple",[])])
        self.assertEqual(mfp1.raw, mfp2)

        # Test that the appropriate term properties are set up properly
        self.assertEqual(mfp1.aterm1, "astring")
        self.assertEqual(mfp1.aterm2, "asimple")

    #--------------------------------------------------------------------------
    # Test that we can define predicates with Function and Tuple terms
    # --------------------------------------------------------------------------
    def test_complex_predicate_defn(self):

        class FloatApproxField(IntegerField):
            pytocl = lambda x: int(x*100)
            cltopy = outfunc=lambda x: x/100.0

        class Fun(ComplexTerm):
            aint = FloatApproxField()
            astr = StringField()

        class MyTuple(ComplexTerm):
            aint = IntegerField()
            astr = StringField()
            class Meta: istuple = True

        # Check the automatically generated term definition class
        mtd = MyTuple.Field
        self.assertTrue(inspect.isclass(mtd))
        self.assertEqual(mtd.__name__, "MyTupleField")

        # Alternative fact definition
        class Fact(Predicate):
            aint = IntegerField()
            # note: don't need to specify defn keyword
            atup = MyTuple.Field(default=MyTuple(aint=2,astr="str"))
            afunc = Fun.Field(default=Fun(aint=2.0,astr="str"))
#            atup = ComplexField(MyTuple,default=MyTuple(aint=2,astr="str"))
#            afunc = ComplexField(defn=Fun,default=Fun(aint=2.0,astr="str"))

        af1=Fact(aint=1)
        af2=Fact(aint=2, atup=MyTuple(aint=4,astr="XXX"), afunc=Fun(aint=5.5,astr="YYY"))

        f1 = Function("fact",[Number(1),
                              Function("",[Number(2),String("str")]),
                              Function("fun",[Number(200),String("str")])])
        f2 = Function("fact",[Number(2),
                              Function("",[Number(4),String("XXX")]),
                              Function("fun",[Number(550),String("YYY")])])

        self.assertEqual(f1, af1.raw)
        self.assertEqual(f2, af2.raw)
        self.assertEqual(af2.atup.aint,4)

    #--------------------------------------------------------------------------
    # Test that the Predicate meta class only allows a single sub-class derived
    # from Predicate.
    # --------------------------------------------------------------------------
    def test_subclassing_nonlogicalsymbol(self):

        class Ok1(Predicate):
            astr = StringField()

        class Ok2(Predicate):
            aint = IntegerField()

        # Test that you cannot instantiate NonLogicalSymbol
        with self.assertRaises(TypeError) as ctx:
            a = NonLogicalSymbol()

        with self.assertRaises(TypeError):
            class Bad1(Ok1,Ok2):
                pass

        with self.assertRaises(TypeError):
            class Bad2(Ok1,Predicate):
                pass


    #--------------------------------------------------------------------------
    # Test the clone operator
    # --------------------------------------------------------------------------
    def test_clone(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()

        f1 = Fact(anum=1,astr="astr")
        f2 = f1.clone(anum=2)

        self.assertNotEqual(f1,f2)
        self.assertEqual(f1.astr, f2.astr)
        self.assertEqual(f1.anum, 1)
        self.assertEqual(f2.anum, 2)

        with self.assertRaises(ValueError) as ctx:
            f3 = f1.clone(anum=3,anot=4)

    #--------------------------------------------------------------------------
    # Test accessing values by index
    # --------------------------------------------------------------------------
    def test_predicate_value_by_index(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()

        f = Fact(1,"fun")
        self.assertEqual(f.anum, 1)
        self.assertEqual(f[0], 1)
#        f[0]=2
#        self.assertEqual(f.anum, 2)

        (anum,astr) = f
#        self.assertEqual(anum, 2)
        self.assertEqual(astr, "fun")

#        with self.assertRaises(IndexError) as ctx: f[3] = 4
#        with self.assertRaises(TypeError) as ctx: f['bob'] = 4

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_predicate_comparison_operator_overloads(self):

        f1 = Function("fact", [Number(1)])
        f2 = Function("fact", [Number(2)])

        class Fact(Predicate):
            anum = IntegerField()

        af1 = Fact(anum=1)
        af2 = Fact(anum=2)
        af1_c = Fact(anum=1)

        self.assertEqual(f1, af1.raw)
        self.assertEqual(af1, af1_c)
        self.assertNotEqual(af1, af2)
        self.assertEqual(str(f1), str(af1))

        # comparing predicates of different types or to a raw should return
        # false even if the underlying raw symbol is identical
        class Fact2(Predicate):
            anum = IntegerField()
            class Meta: name = "fact"
        ag1 = Fact2(anum=1)

        self.assertEqual(f1, af1.raw)
        self.assertEqual(af1.raw, f1)
        self.assertEqual(af1.raw, ag1.raw)
        self.assertNotEqual(af1, ag1)
        self.assertNotEqual(af1, f1)
        self.assertNotEqual(f1, af1)

        self.assertTrue(af1 <  af2)
        self.assertTrue(af1 <=  af2)
        self.assertTrue(af2 >  af1)
        self.assertTrue(af2 >=  af1)

        # clingo.Symbol currently does not implement NotImplemented for
        # comparison between Symbol and some unknown type so the following
        # assertions will fail. This may change in later versions of clingo
        # (maybe 5.3.2 ?).
        test_clingo_symbol_comparison = False
        if test_clingo_symbol_comparison:
            self.assertEqual(af1, f1)
            self.assertEqual(f1, af1)
            self.assertTrue(f2 >  af1)
            self.assertTrue(af1 <  f2)
            self.assertTrue(af1 <=  f2)
            self.assertTrue(f2 >=  af1)

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_comparison_operator_overloads_complex(self):

        class SwapField(IntegerField):
            pytocl = lambda x: 100 - x
            cltopy = lambda x: 100 - x

        class AComplex(ComplexTerm):
            swap=SwapField()
            norm=IntegerField()

        f1 = AComplex(swap=99,norm=1)
        f2 = AComplex(swap=98,norm=2)
        f3 = AComplex(swap=97,norm=3)
        f4 = AComplex(swap=97,norm=3)

        rf1 = f1.raw
        rf2 = f2.raw
        rf3 = f3.raw
        for rf in [rf1,rf2,rf3]:
            self.assertEqual(rf.arguments[0],rf.arguments[1])

        # Test the the comparison operator for the complex term is using the
        # swapped values so that the comparison is opposite to what the raw
        # field says.
        self.assertTrue(rf1 < rf2)
        self.assertTrue(rf2 < rf3)
        self.assertTrue(f1 > f2)
        self.assertTrue(f2 > f3)
        self.assertTrue(f2 < f1)
        self.assertTrue(f3 < f2)
        self.assertEqual(f3,f4)
    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_predicate(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()
            asim = ConstantField()

        gfact1_sym = Function("fact",[Number(1),String("Dave"),Function("ok",[])])
        gfact1_pred = Fact._unify(gfact1_sym)
        self.assertEqual(gfact1_pred.anum, 1)
        self.assertEqual(gfact1_pred.astr, "Dave")
        self.assertEqual(gfact1_pred.asim, "ok")

        bfact1_sym = Function("fact",[String("1"),String("Dave"),Function("ok",[])])
        with self.assertRaises(ValueError) as ctx:
            bfact1_pred = Fact._unify(bfact1_sym)

    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_complex_predicate(self):

        class Fact(Predicate):
            class Fun(ComplexTerm):
                aint=IntegerField()
                astr=StringField()

#            afun = ComplexField(defn=Fun)
            afun = Fun.Field()

        good_fact_symbol1 = Function("fact",[Function("fun",[Number(1),String("Dave")])])
        good_fact_symbol2 = Function("fact",[Function("fun",[Number(3),String("Dave")])])
        good_fact_symbol3 = Function("fact",[Function("fun",[Number(4),String("Bob")])])
        good_fact_pred1 = Fact._unify(good_fact_symbol1)
        self.assertEqual(good_fact_pred1.afun, Fact.Fun(1,"Dave"))

        bad_fact_symbol1 = Function("fact",[Function("fun",[Number(1)])])
        with self.assertRaises(ValueError) as ctx:
            bad_fact_pred1 = Fact._unify(bad_fact_symbol1)

        # A field value can only be set at construction
        with self.assertRaises(AttributeError) as ctx:
            good_fact_pred1.afun.aint = 3



    #--------------------------------------------------------------------------
    #  Test a generator that takes n-1 Predicate types and a list of raw symbols
    #  as the last parameter, then tries to unify the raw symbols with the
    #  predicate types.
    #  --------------------------------------------------------------------------

    def test_unify(self):
        raws = [
            Function("afact",[Number(1),String("test")]),
            Function("afact",[Number(2),Number(3),String("test")]),
            Function("afact",[Number(1),Function("fun",[Number(1)])]),
            Function("bfact",[Number(3),String("test")])
            ]

        class Afact1(Predicate):
            anum=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        class Afact2(Predicate):
            anum1=IntegerField()
            anum2=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        class Afact3(Predicate):
            class Fun(ComplexTerm):
                fnum=IntegerField()

            anum=IntegerField()
            afun=Fun.Field()
#            afun=ComplexField(Fun)
            class Meta: name = "afact"

        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1_1=Afact1(anum=1,astr="test")
        af2_1=Afact2(anum1=2,anum2=3,astr="test")
        af3_1=Afact3(anum=1,afun=Afact3.Fun(fnum=1))
        bf_1=Bfact(anum=3,astr="test")

        g1=list(unify([Afact1],raws))
        g2=list(unify([Afact2],raws))
        g3=list(unify([Afact3],raws))
        g4=list(unify([Bfact],raws))
        g5=list(unify([Afact1,Bfact],raws))
        self.assertEqual([af1_1], g1)
        self.assertEqual([af2_1], g2)
        self.assertEqual([af3_1], g3)
        self.assertEqual([bf_1], g4)
        self.assertEqual([af1_1,bf_1], g5)

    #--------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature. There was a bug in the unify() function where only of the
    #   unifying classes was ignored leading to failed unification.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig(self):
        class ATuple(ComplexTerm):
            aconst=ConstantField()
            bint = IntegerField()
            class Meta: istuple = True

        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()
            class Meta: name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            atuple = ATuple.Field()
            class Meta: name = "fact"

        r1 = Function("fact",[Number(1), Function("bob",[])])
        r2 = Function("fact",[Number(1), Function("", [Function("bob",[]),Number(1)])])

        # r1 only unifies with Fact1 and r2 only unifies with Fact2
        f1 = Fact1(raw=r1)
        self.assertEqual(f1.raw, r1)
        with self.assertRaises(ValueError) as ctx:
            f2 = Fact1(raw=r2)
        f2 = Fact2(raw=r2)
        self.assertEqual(f2.raw, r2)
        with self.assertRaises(ValueError) as ctx:
            f1 = Fact2(raw=r1)

        # The unify() function should correctly unify both facts
        res = unify([Fact1,Fact2],[r1,r2])
        self.assertEqual(len(res), 2)

    #--------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature to make sure the order of the predicate classes correctly
    #   corresponds to the order in which the facts are unified.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig2(self):

        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()
            class Meta: name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            araw = RawField()
            class Meta: name = "fact"

        r1 = Function("fact",[Number(1), Function("bob",[])])
        r2 = Function("fact",[Number(1), Function("", [Function("bob",[]),Number(1)])])

        # r1 only unifies with Fact1 but both r1 and r2 unify with Fact2
        f1 = Fact1(raw=r1)
        self.assertEqual(f1.raw, r1)
        with self.assertRaises(ValueError) as ctx:
            f2 = Fact1(raw=r2)
        f1 = Fact2(raw=r1)
        self.assertEqual(f1.raw, r1)
        f2 = Fact2(raw=r2)
        self.assertEqual(f2.raw, r2)

        # unify() should unify r1 with Fact1 and r2 with Fact2
        res = unify([Fact1,Fact2],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0],Fact1))
        self.assertTrue(isinstance(res[1],Fact2))

        # unify() should unify r1 and r2 with Fact2
        res = unify([Fact2,Fact1],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0],Fact2))
        self.assertTrue(isinstance(res[1],Fact2))

    #--------------------------------------------------------------------------
    #  Test that the fact comparators work
    #--------------------------------------------------------------------------

    def test_comparators(self):

        def is_static(fc):
            return isinstance(fc, _StaticComparator)

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
        e4 = Bfact.astr == "aaa"

        self.assertEqual(e1, _get_term_comparators(e1)[0])
        self.assertEqual(e2, _get_term_comparators(e2)[0])
        self.assertEqual(e3, _get_term_comparators(e3)[0])
        self.assertEqual([], _get_term_comparators(e3.simplified()))

        self.assertFalse(is_static(e1.simplified()))
        self.assertFalse(is_static(e2.simplified()))
        self.assertTrue(is_static(e3.simplified()))
        self.assertFalse(is_static(e4.simplified()))

        self.assertFalse(e1(af1))
        self.assertTrue(e1(af2))

        # Testing the FieldComparator on the wrong fact type
        with self.assertRaises(TypeError) as ctx:
            self.assertFalse(e1(bf1))

        self.assertTrue(e2(af1))
        self.assertFalse(e2(af2))
#        self.assertFalse(e2(bf1))

        self.assertTrue(e3(af1))
        self.assertTrue(e3(af2))
#        self.assertTrue(e3(bf1))

#        self.assertFalse(e4(af1))
#        self.assertFalse(e4(af2))

        self.assertTrue(e4(bf1))

        es1 = [Afact.anum1 == 2, Afact.anum2 == 3]

        ac = and_(*es1)

        self.assertFalse(is_static(ac.simplified()))
        self.assertFalse(ac(af1))
        self.assertTrue(ac(af2))
#        self.assertFalse(ac(bf1))

        nc = not_(ac)
        self.assertFalse(is_static(nc.simplified()))
        self.assertTrue(nc(af1))
        self.assertFalse(nc(af2))
 #       self.assertTrue(nc(bf1))

        oc = or_(*es1)
        self.assertFalse(is_static(oc.simplified()))
        self.assertFalse(oc(af1))
        self.assertTrue(oc(af2))
        self.assertTrue(oc(af3))
  #      self.assertFalse(oc(bf1))

        es2 = [Afact.anum1 == Afact.anum1, True]
        ac2 = and_(*es2)
        self.assertTrue(is_static(ac2.simplified()))

        es3 = [Afact.anum1 == 1, Afact.anum2 == 1, Bfact.anum == 2, True]
        ac3 = and_(*es3)
        self.assertFalse(is_static(ac3.simplified()))

        self.assertEqual(str(Afact.anum1), "Afact.anum1")
        self.assertEqual(str(Afact.anum1 == 1), "Afact.anum1 == 1")

        # This cannot be simplified
        es4 = [Afact.anum1 == Afact.anum1, lambda x: False]
        ac4 = and_(*es4)
        self.assertFalse(is_static(ac4.simplified()))


    #--------------------------------------------------------------------------
    # Test the factbasehelper with double decorators
    #--------------------------------------------------------------------------
    def test_factbasebuilder(self):

        # Using the FactBaseBuilder as a decorator
        fbb1 = FactBaseBuilder()
        fbb2 = FactBaseBuilder()
        fbb3 = FactBaseBuilder(suppress_auto_index=True)

        # decorator both
        @fbb3.register
        @fbb2.register
        @fbb1.register
        class Afact(Predicate):
            num1=IntegerField(index=True)
            num2=IntegerField()
            str1=StringField()

        # decorator without argument
        @fbb1.register
        class Bfact(Predicate):
            num1=IntegerField(index=True)
            str1=StringField()

        self.assertEqual(fbb1.predicates, [Afact,Bfact])
        self.assertEqual(fbb2.predicates, [Afact])
        self.assertEqual(fbb3.predicates, [Afact])
        self.assertEqual(fbb1.indexes, [Afact.num1,Afact.num1])
        self.assertEqual(fbb2.indexes, [Afact.num1])
        self.assertEqual(fbb3.indexes, [])

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_factbasebuilder_symbols(self):

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

        raws = [
            Function("afact",[Number(1), Number(10), String("bbb")]),
            Function("afact",[Number(2), Number(20), String("aaa")]),
            Function("afact",[Number(3), Number(20), String("aaa")]),
            Function("bfact",[Number(1),String("aaa")]),
            Function("bfact",[Number(2),String("bbb")]),
            Function("cfact",[Number(1)])
            ]
        fbb = FactBaseBuilder(predicates=[Afact,Bfact,Cfact])

        # Test the different ways that facts can be added
        fb = fbb.new(symbols=raws)
        self.assertFalse(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = fbb.new(symbols=raws, delayed_init=True)
        self.assertTrue(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add([af1,af2,af3])
####        self.assertEqual(fb.add([af1,af2,af3]),3)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add(af1)
        fb.add(af2)
        fb.add(af3)
####        self.assertEqual(fb.add(af1),1)
####        self.assertEqual(fb.add(af2),1)
####        self.assertEqual(fb.add(af3),1)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        # Test that adding symbols can handle symbols that don't unify
        fb = fbb.new(symbols=raws)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        return

        # Test the specification of indexes
        class MyFactBase3(FactBase):
            predicates = [Afact, Bfact]

        fbb = FactBaseBuilder(predicates=[Afact,Bfact,Cfact],
                              indexes=[Afact.num1, Bfact.num1])

        fb = fbb.new(symbols=raws)
        s = fb.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(s.get_unique(), af1)
        s = fb.select(Bfact).where(Bfact.num1 == 1)
        self.assertEqual(s.get_unique(), bf1)


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

        self.assertEqual(fi.find(operator.eq, 1), set([af1a]))
        self.assertEqual(fi.find(operator.eq, 2), set([af2a, af2b]))
        self.assertEqual(fi.find(operator.ne, 5), set(allfacts))
        self.assertEqual(fi.find(operator.eq, 5), set([]))
        self.assertEqual(fi.find(operator.lt, 1), set([]))
        self.assertEqual(fi.find(operator.lt, 2), set([af1a]))
        self.assertEqual(fi.find(operator.le, 2), set([af1a, af2a, af2b]))
        self.assertEqual(fi.find(operator.gt, 2), set([af3a, af3b]))
        self.assertEqual(fi.find(operator.ge, 3), set([af3a, af3b]))
        self.assertEqual(fi.find(operator.gt, 3), set([]))

    def test_clear(self):
        Afact = self.Afact
        fi = _FactIndex(Afact.num1)
        fi.add(Afact(num1=1, str1="a"))
        fi.clear()
        self.assertEqual(fi.keys,[])

#------------------------------------------------------------------------------
# Test the _FactMap and _Select _Delete class
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
        self.assertEqual(fm1.indexes, [])

        fm1 = _FactMap(Afact, [Afact.num1, Afact.str1])
        self.assertEqual(fm1.indexes, [Afact.num1, Afact.str1])

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
        bf1 = Bfact(1,"aaa")
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
        bf1 = Bfact(1,"aaa")
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

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_comparison_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        bf1 = Bfact(num1=1, str1="1", str2="a")

        delayed_init=lambda: [af1,af2]

        fb1 = FactBase([af1,af2])
        fb2 = FactBase([af1,af2,bf1])
        fb3 = FactBase([af1,af2,bf1])
        fb4 = FactBase(facts=delayed_init)

        self.assertTrue(fb1 != fb2)
        self.assertTrue(fb1 == fb4)
        self.assertTrue(fb2 == fb3)

#------------------------------------------------------------------------------
# Test the _Select class
#------------------------------------------------------------------------------

class SelectTestCase(unittest.TestCase):
    def setUp(self):
        pass

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
        s1_ph2 = fm1.select().where(Afact1.str1 == ph_("str1","42"), Afact1.num1 == ph_("num1"))
        self.assertEqual(set(s1_ph1.get(num1=4)), set([f4,f42]))
        self.assertEqual(set(list(s1_ph1.get(num1=3))), set([f3]))
        self.assertEqual(set(list(s1_ph1.get(num1=2))), set([]))
        self.assertEqual(s1_ph2.get_unique(num1=4), f42)
        self.assertEqual(s1_ph2.get_unique(str1="42",num1=4), f42)

        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph1.get_unique(num1=4))  # fails because of multiple values
        with self.assertRaises(TypeError) as ctx:
            tmp = list(s1_ph2.get(num2=5))         # fails because of no values
        with self.assertRaises(TypeError) as ctx:
            tmp = list(s1_ph2.get(str1="42"))

    #--------------------------------------------------------------------------
    # Test basic insert and selection of facts in a factbase
    #--------------------------------------------------------------------------

    def test_select_over_factbase(self):

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

        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(set(list(s5.get(1))), set([]))

        # Test that the fact base index
        fb = FactBase(indexes=[Afact.num2, Bfact.str1])
        self.assertEqual(set(fb.indexes), set([Afact.num2, Bfact.str1]))

    #--------------------------------------------------------------------------
    #   Test that we can use the same placeholder multiple times
    #--------------------------------------------------------------------------
    def test_select_multi_placeholder(self):
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
    def test_select_order_by(self):
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

        q = fb.select(Afact).order_by(Afact.num1.asc())
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(Afact.num1.desc())
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(Afact.str2)
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(Afact.str2.desc())
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(Afact.str1.desc(), Afact.num1)
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
    def test_select_order_by_complex_term(self):

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
    #   Test that the indexing works
    #--------------------------------------------------------------------------
    def test_select_indexing(self):
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

        fm1.add(f1) ; fm1.add(f2) ; fm1.add(f3) ; fm1.add(f4) ; fm1.add(f5) ; fm1.add(f6)

        # Use an function to track the facts that are visited. This will show
        # that the first operator slects only the appropriate terms.
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

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class TypeCastSignatureTestCase(unittest.TestCase):
    def setUp(self):
        class DateField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

        class DowField(ConstantField):
            pytocl = lambda dt: calendar.day_name[dt.weekday()].lower()

        class EDate(ComplexTerm):
            idx = IntegerField()
            date = DateField()
            class Meta: name="edate"

        self.DateField = DateField
        self.DowField = DowField
        self.EDate = EDate

    #--------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_signature(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        sig1 = TypeCastSignature(DateField)     # returns a single date
        sig2 = TypeCastSignature([DateField])   # returns a list of dates
        sig3 = TypeCastSignature(DateField, DowField)  # takes a date and returns the day or week

        sig4 = TypeCastSignature(EDate.Field,EDate.Field)    # takes an EDate and returns an EDate

        # Some bad declarations
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(int)
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, int)
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [int])
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [DateField, DateField])

        date1 = datetime.date(2018,1,1)
        date2 = datetime.date(2019,2,2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        # Test simple output and list output

        def getdate1() : return date1
        def getdates() : return [date1, date2]

        cl_getdate1 = sig1.wrap_function(getdate1)
        cl_getdates = sig2.wrap_function(getdates)
        self.assertEqual(cl_getdate1(), String("20180101"))
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Use decoractor mode

        @sig3.wrap_function
        def getdow(dt) : return dt
        result = getdow(String("20180101"))
        self.assertEqual(result, Function("monday",[]))

        # Test a ComplexTerm input and output
        @sig4.wrap_function
        def getedate(indate): return indate
        self.assertEqual(getedate(edate1.raw), edate1.raw)
        self.assertEqual(getedate(edate2.raw), edate2.raw)

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self,x,y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = sig2.wrap_method(get_pair)

        t = Tmp(date1,date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])

    #--------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_make_function_asp_callable(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        date1 = datetime.date(2018,1,1)
        date2 = datetime.date(2019,2,2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        def getdate1() : return date1
        def getdates() : return [date1, date2]

        # Test wrapper as a normal function and specifying a signature
        cl_getdate1 = make_function_asp_callable(DateField, getdate1)
        self.assertEqual(cl_getdate1(), String("20180101"))

        cl_getdates = make_function_asp_callable([DateField], getdates)
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Test wrapper as a decorator and specifying a signature
        @make_function_asp_callable(DateField)
        def getdate1() : return date1
        self.assertEqual(getdate1(), String("20180101"))

        @make_function_asp_callable([DateField])
        def getdates() : return [date1, date2]
        self.assertEqual(getdates(), [String("20180101"), String("20190202")])

        @make_function_asp_callable
        def getdates2(x: DateField, y : EDate.Field) -> [DateField]:
            '''GETDATES2'''
            return [date1,date2]
        self.assertEqual(getdates2(String("20180101"), edate1.raw),
                         [String("20180101"), String("20190202")])
        self.assertEqual(getdates2.__doc__, '''GETDATES2''')

        with self.assertRaises(TypeError) as ctx:
            @make_function_asp_callable
            def getdates3(x,y): return [date1,date2]

        with self.assertRaises(TypeError) as ctx:
            @make_function_asp_callable
            def getdates4(x : DateField, y : DateField): return [date1,date2]

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self,x,y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = make_method_asp_callable([DateField], get_pair)

            @make_method_asp_callable
            def get_pair2(self) -> [DateField]:
                return [self._x, self._y]

        t = Tmp(date1,date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])
        self.assertEqual(t.get_pair2(), [String("20180101"), String("20190202")])


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
