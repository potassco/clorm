#------------------------------------------------------------------------------
# Unit tests for Clorm ORM SymbolPredicateUnifer and unify function.
#
# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import unittest
from .support import check_errmsg

from clingo import Control, Number, String, Function, SymbolType

# Official Clorm API imports
from clorm.orm import \
    RawField, IntegerField, StringField, ConstantField, SimpleField,  \
    Predicate, ComplexTerm, path, hashable_path, FactBase

# Official Clorm API imports
from clorm.orm import SymbolPredicateUnifier, unify

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'UnifyTestCase'
    ]

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class UnifyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Simple test to make sure that raw terms unify correctly
    #--------------------------------------------------------------------------
    def test_predicate_instance_raw_term(self):

        raw1 = Function("func",[Number(1)])
        raw2 = Function("bob",[String("no")])
        rf1 = RawField()
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

        # Test the ordered option that returns a list of facts that preserves
        # the order of the original symbols.
        g1=unify([Afact1,Afact2,Bfact], raws, ordered=True)
        self.assertEqual(g1, [af1_1,af2_1,bf_1])

    #--------------------------------------------------------------------------
    #  Test unification with unary predicates
    #  --------------------------------------------------------------------------
    def test_unify_unary(self):
        raws = [
            Function("afact",[Number(1),String("test")]),
            Function("unary1",[]),
            Function("unary2",[]),
            Function("afact",[Number(2),String("test")]),
            ]

        class Afact(Predicate):
            anum=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        class Unary1(Predicate):
            class Meta: name = "unary1"

        class Unary2(Predicate):
            class Meta: name = "unary2"

        af_1=Afact(anum=1,astr="test")
        af_2=Afact(anum=2,astr="test")
        u_1=Unary1()
        u_2=Unary2()

        self.assertEqual(list(unify([Unary1],raws)),[u_1])
        self.assertEqual(list(unify([Unary2],raws)),[u_2])
        self.assertEqual(set(unify([Afact,Unary1,Unary2],raws)),
                             set([af_1,af_2,u_1,u_2]))

    #--------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature. There was a bug in the unify() function where only of the
    #   unifying classes was ignored leading to failed unification.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig(self):
        class ATuple(ComplexTerm):
            aconst=ConstantField()
            bint = IntegerField()
            class Meta: is_tuple = True

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
        f1_alt = Fact2(raw=r1)
        self.assertEqual(f1_alt.raw, r1)
        f2 = Fact2(raw=r2)
        self.assertEqual(f2.raw, r2)

        # unify() unifies r1 with Fact1 (f1) and r2 with Fact2 (f2)
        res = unify([Fact1,Fact2],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1 in res)
        self.assertTrue(f2 in res)

        # unify() unifies r1 and r2 with Fact2 (f1_alt and f2)
        res = unify([Fact2,Fact1],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1_alt in res)
        self.assertTrue(f2 in res)

    #--------------------------------------------------------------------------
    # Test unifying with negative facts
    #--------------------------------------------------------------------------
    def test_unify_signed_literals(self):
        class F1(Predicate):
            a = IntegerField
            class Meta:
                name = "f"
                sign = True

        class F2(Predicate):
            a = IntegerField
            class Meta:
                name = "f"
                sign = False

        pos_raw1 = Function("f",[Number(1)])
        pos_raw2 = Function("f",[Number(2)])
        neg_raw1 = Function("f",[Number(1)],False)
        neg_raw2 = Function("f",[Number(2)],False)

        pos1 = F1(a=1)
        pos2 = F1(a=2)
        neg1 = F2(a=1,sign=False)
        neg2 = F2(a=2,sign=False)

        # unify with all raw
        fb = unify([F1,F2], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 4)
        self.assertEqual(set(fb.query(F1).all()), set([pos1,pos2]))
        self.assertEqual(set(fb.query(F2).all()), set([neg1,neg2]))

        fb = unify([F1], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.query(F1).count(), 2)

        fb = unify([F2], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.query(F2).count(), 2)

        with self.assertRaises(ValueError) as ctx:
            bad1 = F1(a=1,sign=False)

    #--------------------------------------------------------------------------
    # Test unify catching exceptions. When failing to convert a symbol to a
    # python object we need to catch some exceptions. But we shouldn't catch all
    # exceptions, otherwise genuine errors (like missing modules) will not be
    # caught. Thanks to Susana Hahn for finding this problem.
    # --------------------------------------------------------------------------
    def test_unify_catch_exceptions(self):

        # Define a class that converts strings but makes bad exceptions for any
        # other input
        class TmpField(RawField):
            def cltopy(raw):
                if raw.type == SymbolType.String:
                    return raw.string
                return blah.blah.error1(raw)
            def pytocl(v):
                if isinstance(v,str): return String(v)
                import blah
                return blah.error2(v)

        # This is good
        self.assertEqual(TmpField.cltopy(String("blah")), "blah")
        self.assertEqual(TmpField.pytocl("blah"), String("blah"))

        # Some things that should throw an exception
        with self.assertRaises(AttributeError) as ctx:
            r=TmpField.cltopy(1)
        check_errmsg("'int' object has no attribute 'type'",ctx)
        with self.assertRaises(NameError) as ctx:
            r=TmpField.cltopy(Number(1))
        check_errmsg("name 'blah' is not defined",ctx)
        with self.assertRaises(ModuleNotFoundError) as ctx:
            r=TmpField.pytocl(1)
        check_errmsg("No module named 'blah'",ctx)

        class F(Predicate):
            v=TmpField

        # Ok
        raw=Function("f",[String("astring")])
        unify([F],[raw])

        # Bad
        with self.assertRaises(NameError) as ctx:
            raw=Function("f",[Number(1)])
            unify([F],[raw])
        check_errmsg("name 'blah' is not defined",ctx)



    #--------------------------------------------------------------------------
    # Test the factbasehelper with double decorators
    #--------------------------------------------------------------------------
    def test_symbolpredicateunifier(self):

        # Using the SymbolPredicateUnifier as a decorator
        spu1 = SymbolPredicateUnifier()
        spu2 = SymbolPredicateUnifier()
        spu3 = SymbolPredicateUnifier(suppress_auto_index=True)

        # decorator both
        @spu3.register
        @spu2.register
        @spu1.register
        class Afact(Predicate):
            num1=IntegerField(index=True)
            num2=IntegerField()
            str1=StringField()

        # decorator without argument
        @spu1.register
        class Bfact(Predicate):
            num1=IntegerField(index=True)
            str1=StringField()

        self.assertEqual(spu1.predicates, (Afact,Bfact))
        self.assertEqual(spu2.predicates, (Afact,))
        self.assertEqual(spu3.predicates, (Afact,))
        self.assertEqual(spu1.indexes, (Afact.num1,Afact.num1))
        self.assertEqual(spu2.indexes, (Afact.num1,))
        self.assertEqual(spu3.indexes, ())

    #--------------------------------------------------------------------------
    # Test the symbolpredicateunifier when there are subfields defined
    #--------------------------------------------------------------------------
    def test_symbolpredicateunifier_with_subfields(self):
        spu = SymbolPredicateUnifier()

        class CT(ComplexTerm):
            a = IntegerField
            b = StringField(index=True)
            c = (IntegerField(index=True),ConstantField)

        @spu.register
        class P(Predicate):
            d = CT.Field(index=True)
            e = CT.Field()

        expected=set([hashable_path(P.d),
                      hashable_path(P.d.b), hashable_path(P.d.c.arg1),
                      hashable_path(P.e.b), hashable_path(P.e.c.arg1)])
        self.assertEqual(spu.predicates, (P,))
        self.assertEqual(set([hashable_path(p) for p in spu.indexes]), set(expected))

        ct_func=Function("ct",[Number(1),String("aaa"),
                               Function("",[Number(1),Function("const",[])])])
        p1=Function("p",[ct_func,ct_func])
        fb=spu.unify(symbols=[p1],raise_on_empty=True)
        self.assertEqual(len(fb),1)
        self.assertEqual(set([hashable_path(p) for p in fb.indexes]), expected)

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_symbolpredicateunifier_symbols(self):

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
        spu = SymbolPredicateUnifier(predicates=[Afact,Bfact,Cfact])

        # Test the different ways that facts can be added
        fb = spu.unify(symbols=raws)
        self.assertFalse(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1,af2,af3]))

        fb = spu.unify(symbols=raws, delayed_init=True)
        self.assertTrue(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add([af1,af2,af3])
####        self.assertEqual(fb.add([af1,af2,af3]),3)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add(af1)
        fb.add(af2)
        fb.add(af3)
####        self.assertEqual(fb.add(af1),1)
####        self.assertEqual(fb.add(af2),1)
####        self.assertEqual(fb.add(af3),1)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1,af2,af3]))

        # Test that adding symbols can handle symbols that don't unify
        fb = spu.unify(symbols=raws)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1,af2,af3]))

        return

        # Test the specification of indexes
        class MyFactBase3(FactBase):
            predicates = [Afact, Bfact]

        spu = SymbolPredicateUnifier(predicates=[Afact,Bfact,Cfact],
                                     indexes=[Afact.num1, Bfact.num1])

        fb = spu.unify(symbols=raws)
        s = fb.query(Afact).where(Afact.num1 == 1)
        self.assertEqual(s.get_unique(), af1)
        s = fb.query(Bfact).where(Bfact.num1 == 1)
        self.assertEqual(s.get_unique(), bf1)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
