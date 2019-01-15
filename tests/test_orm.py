#------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
#------------------------------------------------------------------------------

import unittest
from clingo import Number, String, Function,  __version__ as clingo_version
from clingo import Control
from clorm.orm import \
    integer_cltopy, string_cltopy, constant_cltopy, \
    integer_pytocl, string_pytocl, constant_pytocl, \
    integer_unifies, string_unifies, constant_unifies, \
    NonLogicalSymbol, Predicate, ComplexTerm, \
    IntegerField, StringField, ConstantField, ComplexField, RawField, \
    not_, and_, or_, _StaticComparator, _get_field_comparators, \
    ph_, ph1_, ph2_, \
    _MultiMap, _FactMap, \
    fact_generator, FactBase, FactBaseHelper, \
    control_add_facts, model_facts, model_contains

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
        self.assertEqual(num1, integer_cltopy(cnum1))
        self.assertEqual(str1, string_cltopy(cstr1))
        self.assertEqual(sim1, constant_cltopy(csim1))

        self.assertEqual(cnum1, integer_pytocl(num1))
        self.assertEqual(cstr1, string_pytocl(str1))
        self.assertEqual(csim1, constant_pytocl(sim1))

        self.assertTrue(integer_unifies(cnum1))
        self.assertTrue(string_unifies(cstr1))
        self.assertTrue(constant_unifies(csim1))

        self.assertFalse(integer_unifies(csim1))
        self.assertFalse(string_unifies(cnum1))
        self.assertFalse(constant_unifies(cstr1))

        fint = IntegerField()
        fstr = StringField()
        fconst = ConstantField()

        self.assertTrue(fint.unifies(cnum1))
        self.assertTrue(fstr.unifies(cstr1))
        self.assertTrue(fconst.unifies(csim1))

    #--------------------------------------------------------------------------
    # Simple test to make sure the default getters and setters are correct
    #--------------------------------------------------------------------------
    def test_raw_field(self):

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

        self.assertEqual(set([f for f in fact_generator([Tmp], [rt1,rt2])]),set([t1,t2]))
        self.assertEqual(t1.r1, raw1)
        self.assertEqual(t2.r1, raw2)

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
        self.assertEqual(num1, integer_cltopy(cnum1))
        self.assertEqual(str1, string_cltopy(cstr1))
        self.assertEqual(sim1, constant_cltopy(csim1))

        self.assertEqual(cnum1, integer_pytocl(num1))
        self.assertEqual(cstr1, string_pytocl(str1))
        self.assertEqual(csim1, constant_pytocl(sim1))

        self.assertTrue(integer_unifies(cnum1))
        self.assertTrue(string_unifies(cstr1))
        self.assertTrue(constant_unifies(csim1))

        self.assertFalse(integer_unifies(csim1))
        self.assertFalse(string_unifies(cnum1))
        self.assertFalse(constant_unifies(cstr1))

        fint = IntegerField()
        fstr = StringField()
        fconst = ConstantField()

        self.assertTrue(fint.unifies(cnum1))
        self.assertTrue(fstr.unifies(cstr1))
        self.assertTrue(fconst.unifies(csim1))


    #--------------------------------------------------------------------------
    # Test setting index for a field
    #--------------------------------------------------------------------------
    def test_field_index(self):
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

        # Test bad declaration - the field name starts with an "_"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                _afield = IntegerField()

        # Test bad declaration - the field name is "meta"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                meta = IntegerField()

        # Test bad declaration - the field name is "raw"
        with self.assertRaises(ValueError) as ctx:
            class BadPredicate(Predicate):
                raw = IntegerField()

        # Test declaration of predicate with an implicit name
        class ImplicitlyNamedPredicate(Predicate):
            afield = IntegerField()

        inp1 = ImplicitlyNamedPredicate(afield=2)
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

        # Test that default fields work and that not specifying a value raises
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

        # Test declaration of predicates with Simple and String fields
        class MultiFieldPredicate(Predicate):
            afield1 = StringField()
            afield2 = ConstantField()
            class Meta: name = "mfp"

        mfp1 = MultiFieldPredicate(afield1="astring", afield2="asimple")
        mfp2 = Function("mfp", [String("astring"), Function("asimple",[])])
        self.assertEqual(mfp1.raw, mfp2)

        # Test that the appropriate field properties are set up properly
        self.assertEqual(mfp1.afield1, "astring")
        self.assertEqual(mfp1.afield2, "asimple")

    #--------------------------------------------------------------------------
    # Test that we can define predicates with Function and Tuple fields
    # --------------------------------------------------------------------------
    def test_complex_predicate_defn(self):

        class Fun(ComplexTerm):
            aint = IntegerField(infunc=lambda x: int(x*100), outfunc=lambda x: x/100.0)
            astr = StringField()

        class MyTuple(ComplexTerm):
            aint = IntegerField()
            astr = StringField()
            class Meta: istuple = True

        # Alternative fact definition
        class Fact(Predicate):
            aint = IntegerField()
            # note: don't need to specify defn keyword
            atup = ComplexField(MyTuple,default=MyTuple(aint=2,astr="str"))
            afunc = ComplexField(defn=Fun,default=Fun(aint=2.0,astr="str"))

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
    def test_comparison_operator_overloads(self):

        f1 = Function("fact", [Number(1)])
        f2 = Function("fact", [Number(2)])

        class Fact(Predicate):
            anum = IntegerField()

        af1 = Fact(anum=1)
        af2 = Fact(anum=2)
        af1_c = Fact(anum=1)

        self.assertEqual(f1, af1.raw)
        self.assertEqual(af1,af1_c)
        self.assertNotEqual(af1, af2)
        self.assertEqual(str(f1), str(af1))

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

            afun = ComplexField(defn=Fun)

        good_fact_symbol1 = Function("fact",[Function("fun",[Number(1),String("Dave")])])
        good_fact_symbol2 = Function("fact",[Function("fun",[Number(3),String("Dave")])])
        good_fact_symbol3 = Function("fact",[Function("fun",[Number(4),String("Bob")])])
        good_fact_pred1 = Fact._unify(good_fact_symbol1)
        self.assertEqual(good_fact_pred1.afun, Fact.Fun(1,"Dave"))

        bad_fact_symbol1 = Function("fact",[Function("fun",[Number(1)])])
        with self.assertRaises(ValueError) as ctx:
            bad_fact_pred1 = Fact._unify(bad_fact_symbol1)

        good_fact_pred1.afun.aint = 3
        self.assertEqual(good_fact_pred1.raw, good_fact_symbol2)

#        ct = Fact.Fun(4,"Bob")
#        good_fact_pred1.afun = ct
#        self.assertEqual(good_fact_pred1.raw, good_fact_symbol3)


    #--------------------------------------------------------------------------
    #  Test a generator that takes n-1 Predicate types and a list of raw symbols
    #  as the last parameter, then tries to unify the raw symbols with the
    #  predicate types.
    #  --------------------------------------------------------------------------

    def test_fact_generator(self):
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
            afun=ComplexField(Fun)
            class Meta: name = "afact"

        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1_1=Afact1(anum=1,astr="test")
        af2_1=Afact2(anum1=2,anum2=3,astr="test")
        af3_1=Afact3(anum=1,afun=Afact3.Fun(fnum=1))
        bf_1=Bfact(anum=3,astr="test")

        g1=list(fact_generator([Afact1],raws))
        g2=list(fact_generator([Afact2],raws))
        g3=list(fact_generator([Afact3],raws))
        g4=list(fact_generator([Bfact],raws))
        g5=list(fact_generator([Afact1,Bfact],raws))
        self.assertEqual([af1_1], g1)
        self.assertEqual([af2_1], g2)
        self.assertEqual([af3_1], g3)
        self.assertEqual([bf_1], g4)
        self.assertEqual([af1_1,bf_1], g5)

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

        self.assertEqual(e1, _get_field_comparators(e1)[0])
        self.assertEqual(e2, _get_field_comparators(e2)[0])
        self.assertEqual(e3, _get_field_comparators(e3)[0])
        self.assertEqual([], _get_field_comparators(e3.simplified()))

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
    #  Test that the fact comparators work
    #--------------------------------------------------------------------------

    def test_factmultimap(self):
        class Afact1(Predicate):
            anum=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        mymm = _MultiMap()
        mymm[4] = Afact1(4,"4")
        mymm[4] = Afact1(4,"42")
        mymm[3] = Afact1(3,"3")
        mymm[1] = Afact1(1,"1")
        mymm[10] = Afact1(10,"10")

        self.assertEqual(set([Afact1(4,"4"), Afact1(4,"42")]), set(mymm[4]))
        self.assertEqual(set([Afact1(10,"10")]), set(mymm[10]))
        self.assertEqual(set([Afact1(1,"1")]), set(mymm[1]))
        self.assertEqual(mymm.keys(), [1,3,4,10])
        self.assertEqual(mymm.keys_lt(4), [1,3])
        self.assertEqual(mymm.keys_le(4), [1,3,4])
        self.assertEqual(mymm.keys_gt(3), [4,10])
        self.assertEqual(mymm.keys_ge(3), [3,4,10])
        self.assertEqual(mymm.keys_ge(2), [3,4,10])
        self.assertEqual(mymm.keys_lt(1), [])
        self.assertEqual(mymm.keys_le(0), [])
        self.assertEqual(mymm.keys_gt(10), [])
        self.assertEqual(mymm.keys_ge(11), [])

        del mymm[10]
        self.assertEqual(mymm.keys(), [1,3,4])

        with self.assertRaises(KeyError) as ctx:
            tmp = mymm[10]
        with self.assertRaises(KeyError) as ctx:
            del mymm[10]

        mymm.clear()
        self.assertEqual(mymm.keys(), [])

    #--------------------------------------------------------------------------
    #   Test that the select works
    #--------------------------------------------------------------------------
    def test_select_over_factmap(self):
        class Afact1(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()
            class Meta: name = "afact"

        fm1 = _FactMap([Afact1.num1,Afact1.str1])
        fm2 = _FactMap()
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
        self.assertEqual(set(list(s1_ph1.get(num1=4))), set([f4,f42]))
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
    #   Test that we can use the same placeholder multiple times
    #--------------------------------------------------------------------------
    def test_select_multi_placeholder(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap([Afact.num1])
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

    #--------------------------------------------------------------------------
    #   Test that the indexing works
    #--------------------------------------------------------------------------
    def test_select_indexing(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap([Afact.num1])
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

        fm1 = _FactMap([Afact.num1,Afact.str1])
        fm2 = _FactMap()
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

        class FB(FactBase) :
            predicates = [Afact]
            indexes = [Afact.num1, Afact.num2]

        fb1 = FB(facts=[f1,f3, f4,f42,f10])
        d1_num1 = fb1.delete(Afact).where(Afact.num1 == ph1_)
        s1_num1 = fb1.select(Afact).where(Afact.num1 == ph1_)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.execute(4), 2)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([]))

    #--------------------------------------------------------------------------
    # Test basic insert and selection of facts in a factbase
    #--------------------------------------------------------------------------

    def test_factbase(self):

        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Cfact(Predicate):
            num1=IntegerField()

        class FactSet(FactBase):
            predicates = [Afact,Bfact,Cfact]

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")
        cf1 = Cfact(1)

#        fb = FactBase([Afact.num1, Afact.num2, Afact.str1])
        fb = FactSet()
        facts=[af1,af2,af3,bf1,bf2,cf1]
        fb.add(facts=facts)

        self.assertEqual(set(fb.facts()), set(facts))
        self.assertEqual(fb.predicate_types(), set([Afact,Bfact,Cfact]))

        s_af_all = fb.select(Afact)
        s_af_num1_eq_1 = fb.select(Afact).where(Afact.num1 == 1)
        s_af_num1_le_2 = fb.select(Afact).where(Afact.num1 <= 2)
        s_af_num2_eq_20 = fb.select(Afact).where(Afact.num2 == 20)
        s_bf_str1_eq_aaa = fb.select(Bfact).where(Bfact.str1 == "aaa")
        s_bf_str1_eq_ccc = fb.select(Bfact).where(Bfact.str1 == "ccc")
        s_cf_num1_eq_1 = fb.select(Cfact).where(Cfact.num1 == 1)

        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))
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
        fb2 = FactSet()
        s2 = fb2.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(set(s2.get()), set())
        fb2.add(facts=[af1,af2])
        self.assertEqual(set(s2.get()), set([af1]))

        # Test select with placeholders
#        fb3 = FactBase([Afact.num1])
        fb3 = FactSet()
        fb3.add(facts=[af1,af2,af3])
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

    #--------------------------------------------------------------------------
    # Test that a factbase only imports from the specified predicates
    #--------------------------------------------------------------------------

    def test_factbase_import(self):

        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Cfact(Predicate):
            num1=IntegerField()

        class FactSet(FactBase):
            predicates = [Afact,Bfact]

        af1 = Afact(1,10,"bbb")
        bf1 = Bfact(1,"aaa")
        cf1 = Cfact(1)

        fs1 = FactSet()
#        self.assertEqual(fs1.add(facts=[af1,bf1,cf1]), 2)
#        self.assertEqual(fs1.select(Afact).get_unique(), af1)
#        self.assertEqual(fs1.select(Bfact).get_unique(), bf1)


    #--------------------------------------------------------------------------
    # Test the FactBaseHelper
    #--------------------------------------------------------------------------
    def test_factbasehelper(self):

        # Using the FactBaseHelper as a decorator
        fbh1 = FactBaseHelper()

        # decorator with argument to specify an index
        @fbh1.register("num1","num2")
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()

        # decorator without argument
        @fbh1.register
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        self.assertEqual(fbh1.predicates, [Afact,Bfact])
        self.assertEqual(fbh1.indexes, [Afact.num1,Afact.num2])

        # Test that when registering an index we only allow a field whose parent
        # predicate is already registered.
        with self.assertRaises(TypeError) as ctx:
            class Tmp(Predicate):
                num1=IntegerField()
            fbh1.register_index(Tmp.num1)

        # Using the FactBaseHelper as a ContextManager and using delayed index
        # registration.
        with FactBaseHelper() as fbh2:

            class Cfact(Predicate):
                num1=IntegerField()

            class Dfact(Predicate):
                num1=IntegerField()
            fbh2.register_index(Dfact.num1)

        self.assertEqual(fbh2.predicates, [Cfact,Dfact])
        self.assertEqual(fbh2.indexes, [Dfact.num1])

        # Test the field.index
        with FactBaseHelper() as fbh3:

            class Mess(ComplexTerm):
                str1=StringField()
                str2=StringField()

            class Efact(Predicate):
                num1=IntegerField(index=True)
                num3=IntegerField()
                mess=ComplexField(Mess)

        self.assertEqual(fbh3.predicates, [Efact])
        self.assertEqual(fbh3.indexes, [Efact.num1])

        FactDB = fbh3.create_class("FactDB")
        self.assertTrue(issubclass(FactDB, FactBase))
        self.assertEqual(FactDB.predicates, [Efact])
        self.assertEqual(FactDB.indexes, [Efact.num1])
        fdb = FactDB()
        ef = Efact(1,1,Mess("str1","str2"))
        self.assertEqual(fdb.add(ef), 1)

        # Test with field.index suppressed
        fbh4 = FactBaseHelper(suppress_auto_index=True)  # alternative syntax
        with fbh4:

            class Ffact(Predicate):
                num1=IntegerField(index=True)
                num3=IntegerField()

        self.assertEqual(fbh4.predicates, [Ffact])
        self.assertEqual(fbh4.indexes, [])

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_factbase_subclasses(self):

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

        class MyFactBase(FactBase):
            predicates = [Afact, Bfact,Cfact]

        # Test the different ways that facts can be added
        fb = MyFactBase(symbols=raws)
        self.assertFalse(fb._delayed_init)
        self.assertEqual(fb.predicate_types(), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = MyFactBase(symbols=raws, delayed_init=True)
        self.assertTrue(fb._delayed_init)
        self.assertEqual(fb.predicate_types(), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = MyFactBase()
        fb.add(symbols=raws)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = MyFactBase()
        fb.add(facts=[af1,af2, af3])
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = MyFactBase()
        fb.add(af1); fb.add(af2); fb.add(af3);
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        # Test that adding symbols can handle symbols that don't unify
        class MyFactBase2(FactBase):
            predicates = [Afact]

        fb = MyFactBase2(symbols=raws)
        self.assertEqual(fb.predicate_types(), set([Afact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        # Change of behaviour - this should fail because Cfact is not part of
        # MyFactBase2
        with self.assertRaises(KeyError) as ctx:
            s_cf_num1_eq_1 = fb.select(Cfact).where(Cfact.num1 == 1)
            self.assertEqual(set(s_cf_num1_eq_1.get()), set([]))

        # Test badly specified FactBase subclasses
        with self.assertRaises(TypeError) as ctx:
            class BadFactBase(FactBase):
                pass
        with self.assertRaises(TypeError) as ctx:
            class BadFactBase(FactBase):
                predicates = [Afact]
                indexes = [Afact.num1, Bfact.num1]

        with self.assertRaises(TypeError) as ctx:
            class BadFactBase(FactBase):
                predicates = None

        with self.assertRaises(TypeError) as ctx:
            class BadFactBase(FactBase):
                predicates = [Afact]
                indexes = None


        # Test the specification of indexes
        class MyFactBase3(FactBase):
            predicates = [Afact, Bfact]
            indexes = [Afact.num1, Bfact.num1]

        fb = MyFactBase3()
        fb.add(symbols=raws)

        s = fb.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(s.get_unique(), af1)
        s = fb.select(Bfact).where(Bfact.num1 == 1)
        self.assertEqual(s.get_unique(), bf1)

    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_control_model_integration(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        class MyFacts(FactBase):
            predicates = [Afact,Bfact]

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")

        fb1 = MyFacts()
        fb1.add(facts= [af1,af2,af3,bf1,bf2])

        fb2 = None
        def on_model(model):
            nonlocal fb2
            self.assertTrue(model_contains(model, af1))
            fb2 = model_facts(model, MyFacts, atoms=True)

        ctrl = Control()
        control_add_facts(ctrl,fb1)
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model)

        # control_add_facts works with both a list of facts and a FactBase
        ctrl2 = Control()
        control_add_facts(ctrl2,[af1,af2,af3,bf1,bf2])

        safact1 = fb2.select(Afact).where(Afact.num1 == ph_("num1"))
        safact2 = fb2.select(Afact).where(Afact.num1 < ph_("num1"))
        self.assertEqual(safact1.get_unique(num1=1), af1)
        self.assertEqual(safact1.get_unique(num1=2), af2)
        self.assertEqual(safact1.get_unique(num1=3), af3)
        self.assertEqual(set(list(safact2.get(num1=1))), set([]))
        self.assertEqual(set(list(safact2.get(num1=2))), set([af1]))
        self.assertEqual(set(list(safact2.get(num1=3))), set([af1,af2]))
        self.assertEqual(fb2.select(Bfact).where(Bfact.str1 == "aaa").get_unique(), bf1)
        self.assertEqual(fb2.select(Bfact).where(Bfact.str1 == "bbb").get_unique(), bf2)

        # Now test a select

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_factbase_subsubclasses(self):

        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        af1 = Afact(1,"bbb")
        af2 = Afact(2,"aaa")
        bf1 = Bfact(1,"bbb")
        bf2 = Bfact(2,"aaa")

        facts = [af1,af2,bf1,bf2]
        raws = [
            Function("afact",[Number(1), String("bbb")]),
            Function("afact",[Number(2), String("aaa")]),
            Function("bfact",[Number(1),String("bbb")]),
            Function("bfact",[Number(2),String("aaa")]),
            ]

        class FBA(FactBase):
            predicates = [Afact]

        class FBB(FactBase):
            predicates = [Bfact]

        self.assertEqual(FBA.predicates, [Afact])
        self.assertEqual(FBB.predicates, [Bfact])
        self.assertEqual(FBA.indexes,[])
        self.assertEqual(FBB.indexes,[])

        # NOTE: I don't think there is a good reason for multiple inheritence
        # but still test that it does actually work as expected.
        class FBAB(FBA,FBB):
            pass

        self.assertEqual(FBAB.predicates, [Afact,Bfact])
        self.assertEqual(FBAB.indexes,[])

        class FBAIdx(FBA):
            indexes=[Afact.num1]

        self.assertEqual(FBAIdx.predicates, [Afact])
        self.assertEqual(FBAIdx.indexes,[Afact.num1])

        class FBBIdx(FBB):
            indexes=[Bfact.num1]

        self.assertEqual(FBBIdx.predicates, [Bfact])
        self.assertEqual(FBBIdx.indexes,[Bfact.num1])

        class FBABIdx(FBAIdx,FBBIdx):
            pass

        self.assertEqual(FBABIdx.predicates, [Afact,Bfact])
        self.assertEqual(FBABIdx.indexes,[Afact.num1,Bfact.num1])


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
