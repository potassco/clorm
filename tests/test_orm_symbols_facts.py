# ------------------------------------------------------------------------------
# Unit tests for Clorm ORM SymbolPredicateUnifer and unify function.
#
# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import os
import tempfile
import unittest

from clingo import Control, Function, Number, String, SymbolType

# Official Clorm API imports
from clorm import (
    BaseField,
    ComplexTerm,
    ConstantField,
    FactBase,
    FactParserError,
    IntegerField,
    Predicate,
    Raw,
    RawField,
    StringField,
    SymbolMode,
    SymbolPredicateUnifier,
    UnifierNoMatchError,
    control_add_facts,
    define_nested_list_field,
    hashable_path,
    parse_fact_files,
    parse_fact_string,
    set_symbol_mode,
    symbolic_atoms_to_facts,
    unify,
)

from .support import add_program_string, check_errmsg

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = ["UnifyTestCase", "ClingoControlConvTestCase", "ParseTestCase"]

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


def hpaths(paths):
    return [hashable_path(path) for path in paths]


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class UnifyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Simple test to make sure that raw terms unify correctly
    # --------------------------------------------------------------------------
    def test_predicate_instance_raw_term(self):

        raw1 = Function("func", [Number(1)])
        raw2 = Function("bob", [String("no")])
        rf1 = RawField()
        rt1 = Function("tmp", [Number(1), raw1])
        rt2 = Function("tmp", [Number(1), raw2])

        class Tmp(Predicate):
            n1 = IntegerField()
            r1 = RawField()

        self.assertTrue(Tmp._unify(rt1) is not None)
        self.assertTrue(Tmp._unify(rt2) is not None)
        t1 = Tmp(1, Raw(raw1))
        t2 = Tmp(1, Raw(raw2))
        self.assertTrue(Tmp._unify(rt2, rt2.arguments, rt2.name) == t2)

        self.assertEqual(set([f for f in unify([Tmp], [rt1, rt2])]), set([t1, t2]))
        self.assertEqual(t1.r1.symbol, raw1)
        self.assertEqual(t2.r1.symbol, raw2)

    # --------------------------------------------------------------------------
    #  Test a generator that takes n-1 Predicate types and a list of raw symbols
    #  as the last parameter, then tries to unify the raw symbols with the
    #  predicate types.
    #  --------------------------------------------------------------------------

    def test_unify(self):
        raws = [
            Function("afact", [Number(1), String("test")]),
            Function("afact", [Number(2), Number(3), String("test")]),
            Function("afact", [Number(1), Function("fun", [Number(1)])]),
            Function("bfact", [Number(3), String("test")]),
        ]

        class Afact1(Predicate):
            anum = IntegerField()
            astr = StringField()

            class Meta:
                name = "afact"

        class Afact2(Predicate):
            anum1 = IntegerField()
            anum2 = IntegerField()
            astr = StringField()

            class Meta:
                name = "afact"

        class Afact3(Predicate):
            class Fun(ComplexTerm):
                fnum = IntegerField()

            anum = IntegerField()
            afun = Fun.Field()
            #            afun=ComplexField(Fun)
            class Meta:
                name = "afact"

        class Bfact(Predicate):
            anum = IntegerField()
            astr = StringField()

        af1_1 = Afact1(anum=1, astr="test")
        af2_1 = Afact2(anum1=2, anum2=3, astr="test")
        af3_1 = Afact3(anum=1, afun=Afact3.Fun(fnum=1))
        bf_1 = Bfact(anum=3, astr="test")

        g1 = list(unify([Afact1], raws))
        g2 = list(unify([Afact2], raws))
        g3 = list(unify([Afact3], raws))
        g4 = list(unify([Bfact], raws))
        g5 = list(unify([Afact1, Bfact], raws))
        self.assertEqual([af1_1], g1)
        self.assertEqual([af2_1], g2)
        self.assertEqual([af3_1], g3)
        self.assertEqual([bf_1], g4)
        self.assertEqual([af1_1, bf_1], g5)

        # Test the ordered option that returns a list of facts that preserves
        # the order of the original symbols.
        g1 = unify([Afact1, Afact2, Bfact], raws, ordered=True)
        self.assertEqual(g1, [af1_1, af2_1, bf_1])

    # --------------------------------------------------------------------------
    #  Test unification with nullary predicates
    #  --------------------------------------------------------------------------
    def test_unify_nullary(self):
        raws = [
            Function("afact", [Number(1), String("test")]),
            Function("nullary1", []),
            Function("nullary2", []),
            Function("afact", [Number(2), String("test")]),
        ]

        class Afact(Predicate):
            anum = IntegerField()
            astr = StringField()

            class Meta:
                name = "afact"

        class Nullary1(Predicate):
            class Meta:
                name = "nullary1"

        class Nullary2(Predicate):
            class Meta:
                name = "nullary2"

        af_1 = Afact(anum=1, astr="test")
        af_2 = Afact(anum=2, astr="test")
        u_1 = Nullary1()
        u_2 = Nullary2()

        self.assertEqual(list(unify([Nullary1], raws)), [u_1])
        self.assertEqual(list(unify([Nullary2], raws)), [u_2])
        self.assertEqual(
            set(unify([Afact, Nullary1, Nullary2], raws)), set([af_1, af_2, u_1, u_2])
        )

    # --------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature. There was a bug in the unify() function where only of the
    #   unifying classes was ignored leading to failed unification.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig(self):
        class ATuple(ComplexTerm):
            aconst = ConstantField()
            bint = IntegerField()

            class Meta:
                is_tuple = True

        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()

            class Meta:
                name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            atuple = ATuple.Field()

            class Meta:
                name = "fact"

        r1 = Function("fact", [Number(1), Function("bob", [])])
        r2 = Function("fact", [Number(1), Function("", [Function("bob", []), Number(1)])])

        # r1 only unifies with Fact1 and r2 only unifies with Fact2
        f1 = Fact1._unify(r1)
        self.assertEqual(f1.raw, r1)
        self.assertEqual(Fact1._unify(r2), None)
        f2 = Fact2._unify(r2)
        self.assertEqual(f2.raw, r2)
        self.assertEqual(Fact2._unify(r1), None)

        # The unify() function should correctly unify both facts
        res = unify([Fact1, Fact2], [r1, r2])
        self.assertEqual(len(res), 2)

    # --------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature to make sure the order of the predicate classes correctly
    #   corresponds to the order in which the facts are unified.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig2(self):
        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()

            class Meta:
                name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            araw = RawField()

            class Meta:
                name = "fact"

        r1 = Function("fact", [Number(1), Function("bob", [])])
        r2 = Function("fact", [Number(1), Function("", [Function("bob", []), Number(1)])])

        # r1 only unifies with Fact1 but both r1 and r2 unify with Fact2
        f1 = Fact1._unify(r1)
        self.assertEqual(f1.raw, r1)
        self.assertEqual(Fact1._unify(r2), None)
        f1_alt = Fact2._unify(r1)
        self.assertEqual(f1_alt.raw, r1)
        f2 = Fact2._unify(r2)
        self.assertEqual(f2.raw, r2)

        # unify() unifies r1 with Fact1 (f1) and r2 with Fact2 (f2)
        res = unify([Fact1, Fact2], [r1, r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1 in res)
        self.assertTrue(f2 in res)

        # unify() unifies r1 and r2 with Fact2 (f1_alt and f2)
        res = unify([Fact2, Fact1], [r1, r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1_alt in res)
        self.assertTrue(f2 in res)

    # --------------------------------------------------------------------------
    # Test unifying with negative facts
    # --------------------------------------------------------------------------
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

        pos_raw1 = Function("f", [Number(1)])
        pos_raw2 = Function("f", [Number(2)])
        neg_raw1 = Function("f", [Number(1)], False)
        neg_raw2 = Function("f", [Number(2)], False)

        pos1 = F1(a=1)
        pos2 = F1(a=2)
        neg1 = F2(a=1, sign=False)
        neg2 = F2(a=2, sign=False)

        # unify with all raw
        fb = unify([F1, F2], [pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 4)
        self.assertEqual(set(fb.query(F1).all()), set([pos1, pos2]))
        self.assertEqual(set(fb.query(F2).all()), set([neg1, neg2]))

        fb = unify([F1], [pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.query(F1).count(), 2)

        fb = unify([F2], [pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.query(F2).count(), 2)

        with self.assertRaises(ValueError) as ctx:
            bad1 = F1(a=1, sign=False)

    # --------------------------------------------------------------------------
    # Test unify catching exceptions. When failing to convert a symbol to a
    # python object we need to catch some exceptions. But we shouldn't catch all
    # exceptions, otherwise genuine errors (like missing modules) will not be
    # caught. Thanks to Susana Hahn for finding this problem.
    # --------------------------------------------------------------------------
    def test_unify_catch_exceptions(self):

        # Define a class that converts strings but makes bad exceptions for any
        # other input
        class TmpField(BaseField):
            def cltopy(raw):
                if raw.type == SymbolType.String:
                    return raw.string
                raise NameError("name 'blah' is not defined")

            def pytocl(v):
                if isinstance(v, str):
                    return String(v)
                import blah

                return blah.error2(v)

        # This is good
        self.assertEqual(TmpField.cltopy(String("blah")), "blah")
        self.assertEqual(TmpField.pytocl("blah"), String("blah"))

        # Some things that should throw an exception
        with self.assertRaises(AttributeError) as ctx:
            r = TmpField.cltopy(1)
        check_errmsg("'int' object has no attribute 'type'", ctx)
        with self.assertRaises(NameError) as ctx:
            r = TmpField.cltopy(Number(1))
        check_errmsg("name 'blah' is not defined", ctx)
        with self.assertRaises(ModuleNotFoundError) as ctx:
            r = TmpField.pytocl(1)
        check_errmsg("No module named 'blah'", ctx)

        class F(Predicate):
            v = TmpField

        # Ok
        raw = Function("f", [String("astring")])
        unify([F], [raw])

        # Bad
        with self.assertRaises(NameError) as ctx:
            raw = Function("f", [Number(1)])
            unify([F], [raw])
        check_errmsg("name 'blah' is not defined", ctx)

    # --------------------------------------------------------------------------
    # Test the factbasehelper with double decorators
    # --------------------------------------------------------------------------
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
            num1 = IntegerField(index=True)
            num2 = IntegerField()
            str1 = StringField()

        # decorator without argument
        @spu1.register
        class Bfact(Predicate):
            num1 = IntegerField(index=True)
            str1 = StringField()

        self.assertEqual(spu1.predicates, (Afact, Bfact))
        self.assertEqual(spu2.predicates, (Afact,))
        self.assertEqual(spu3.predicates, (Afact,))
        self.assertEqual(set(hpaths(spu1.indexes)), set(hpaths([Afact.num1, Bfact.num1])))
        self.assertEqual(hpaths(spu2.indexes), hpaths([Afact.num1]))
        self.assertEqual(spu3.indexes, ())

    # --------------------------------------------------------------------------
    # Test the symbolpredicateunifier when there are subfields defined
    # --------------------------------------------------------------------------
    def test_symbolpredicateunifier_with_subfields(self):
        spu = SymbolPredicateUnifier()

        class CT(ComplexTerm):
            a = IntegerField
            b = StringField(index=True)
            c = (IntegerField(index=True), ConstantField)

        @spu.register
        class P(Predicate):
            d = CT.Field(index=True)
            e = CT.Field()

        expected = set(
            [
                hashable_path(P.d),
                hashable_path(P.d.b),
                hashable_path(P.d.c.arg1),
                hashable_path(P.e.b),
                hashable_path(P.e.c.arg1),
            ]
        )
        self.assertEqual(spu.predicates, (P,))
        self.assertEqual(set([hashable_path(p) for p in spu.indexes]), set(expected))

        ct_func = Function(
            "ct", [Number(1), String("aaa"), Function("", [Number(1), Function("const", [])])]
        )
        p1 = Function("p", [ct_func, ct_func])
        fb = spu.unify(symbols=[p1], raise_on_empty=True)
        self.assertEqual(len(fb), 1)
        self.assertEqual(set([hashable_path(p) for p in fb.indexes]), expected)

    # --------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    # --------------------------------------------------------------------------

    def test_symbolpredicateunifier_symbols(self):
        class Afact(Predicate):
            num1 = IntegerField()
            num2 = IntegerField()
            str1 = StringField()

        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        class Cfact(Predicate):
            num1 = IntegerField()

        af1 = Afact(1, 10, "bbb")
        af2 = Afact(2, 20, "aaa")
        af3 = Afact(3, 20, "aaa")
        bf1 = Bfact(1, "aaa")
        bf2 = Bfact(2, "bbb")
        cf1 = Cfact(1)

        raws = [
            Function("afact", [Number(1), Number(10), String("bbb")]),
            Function("afact", [Number(2), Number(20), String("aaa")]),
            Function("afact", [Number(3), Number(20), String("aaa")]),
            Function("bfact", [Number(1), String("aaa")]),
            Function("bfact", [Number(2), String("bbb")]),
            Function("cfact", [Number(1)]),
        ]
        spu = SymbolPredicateUnifier(predicates=[Afact, Bfact, Cfact])

        # Test the different ways that facts can be added
        fb = spu.unify(symbols=raws)
        self.assertFalse(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact, Bfact, Cfact]))
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1, af2, af3]))

        fb = spu.unify(symbols=raws, delayed_init=True)
        self.assertTrue(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact, Bfact, Cfact]))
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1, af2, af3]))

        fb = FactBase()
        fb.add([af1, af2, af3])
        ####        self.assertEqual(fb.add([af1,af2,af3]),3)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1, af2, af3]))

        fb = FactBase()
        fb.add(af1)
        fb.add(af2)
        fb.add(af3)
        ####        self.assertEqual(fb.add(af1),1)
        ####        self.assertEqual(fb.add(af2),1)
        ####        self.assertEqual(fb.add(af3),1)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1, af2, af3]))

        # Test that adding symbols can handle symbols that don't unify
        fb = spu.unify(symbols=raws)
        s_af_all = fb.query(Afact)
        self.assertEqual(set(s_af_all.all()), set([af1, af2, af3]))

        return

        # Test the specification of indexes
        class MyFactBase3(FactBase):
            predicates = [Afact, Bfact]

        spu = SymbolPredicateUnifier(
            predicates=[Afact, Bfact, Cfact], indexes=[Afact.num1, Bfact.num1]
        )

        fb = spu.unify(symbols=raws)
        s = fb.query(Afact).where(Afact.num1 == 1)
        self.assertEqual(s.get_unique(), af1)
        s = fb.query(Bfact).where(Bfact.num1 == 1)
        self.assertEqual(s.get_unique(), bf1)


# ------------------------------------------------------------------------------
# Functions that facilitate interactions with clingo.Control. Note: uses
# multiprocessing library to make sure that we avoid the solver not being able
# to release symbols between runs.
# ------------------------------------------------------------------------------

import multiprocessing as mp


class XP(Predicate):
    x = IntegerField


class XQ(Predicate):
    x = IntegerField


class XQ2(Predicate):
    x = StringField

    class Meta:
        name = "xq"


def symbolic_atoms_to_facts_test1(q, facts_only):
    prgstr = """xq(1). xq("a"). 1 { xp(1);xp(2) }2."""
    ctrl = Control()
    add_program_string(ctrl, prgstr)
    ctrl.ground([("base", [])])
    fb = symbolic_atoms_to_facts(ctrl.symbolic_atoms, [XP, XQ, XQ2], facts_only=facts_only)
    q.put(fb)


class ClingoControlConvTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Basic test of adding facts into a control object
    # --------------------------------------------------------------------------
    def test_control_add_facts(self):
        class F(Predicate):
            anum = IntegerField

        f1 = F(1)
        f2 = F(2)
        ctrl = Control()
        control_add_facts(ctrl, [f1, f2])
        ctrl.ground([("base", [])])
        model = None
        with ctrl.solve(yield_=True) as sh:
            for m in sh:
                model = str(m)
        self.assertEqual(model, "{} {}".format(f1, f2))

    # --------------------------------------------------------------------------
    # Test converting Control.symbolic_atoms to a factbase
    # --------------------------------------------------------------------------
    def test_symbolic_atoms_to_facts(self):
        fb1_expected = FactBase([XP(1), XP(2), XQ(1), XQ2("a")])
        fb2_expected = FactBase([XQ(1), XQ2("a")])

        # Return all ground atoms
        q = mp.Queue()
        p = mp.Process(target=symbolic_atoms_to_facts_test1, args=(q, False))
        p.start()
        fb1_result = q.get()
        p.join()
        self.assertEqual(fb1_result, fb1_expected)

        # Return only fact atoms
        q = mp.Queue()
        p = mp.Process(target=symbolic_atoms_to_facts_test1, args=(q, True))
        p.start()
        fb2_result = q.get()
        p.join()
        self.assertEqual(fb2_result, fb2_expected)


# ------------------------------------------------------------------------------
# Test of functions involve with parsing asp ground facts to clorm facts
# ------------------------------------------------------------------------------


class ParseTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_parse_facts(self):
        class P(Predicate):
            """A P predicate"""

            x = IntegerField
            y = StringField

        class Q(Predicate):
            """A Q predicate"""

            x = ConstantField
            y = P.Field

        asp1 = """p(1,"home\\""). -p(-2,"blah").\n"""
        asp2 = asp1 + """q(X,Y) :- p(X,Y)."""

        fb_p = FactBase([P(1, 'home"'), P(-2, "blah", sign=False)])
        fb_in = FactBase(
            [
                P(1, 'home"'),
                Q("abc", P(3, "H ome")),
                Q("z", P(-1, "One more string")),
                P(-2, "blah", sign=False),
            ]
        )

        # Match a basic string with a rule
        fb_out = parse_fact_string(asp2, unifier=[P, Q])
        self.assertEqual(fb_p, fb_out)

        # All inputs and outputs match
        fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P, Q])
        self.assertEqual(fb_in, fb_out)

        # Match only the p/2 facts
        fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P])
        self.assertEqual(fb_p, fb_out)

        # Match with comments
        fb_out = parse_fact_string(fb_in.asp_str(commented=True), unifier=[P, Q])
        self.assertEqual(fb_in, fb_out)

        # Error on ununified facts
        with self.assertRaises(UnifierNoMatchError) as ctx:
            fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P], raise_nomatch=True)
        check_errmsg("Cannot unify symbol 'q(abc", ctx)

        # Error on nonfact
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp2, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 2

        # Try the fact files parser
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = os.path.join(tmpdirname, "asp.lp")
            with open(fname, "w+") as f:
                f.write(fb_in.asp_str(commented=True))
            fb_out = parse_fact_files([fname], unifier=[P, Q])
            self.assertEqual(fb_in, fb_out)

        # Option where a factbase is given
        fb_out = FactBase()
        parse_fact_string(fb_in.asp_str(commented=True), unifier=[P, Q], factbase=fb_out)
        self.assertEqual(fb_in, fb_out)

        # Fact file parser where factbase is given
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = os.path.join(tmpdirname, "asp.lp")
            with open(fname, "w+") as f:
                f.write(fb_in.asp_str(commented=True))
            fb_out = FactBase()
            parse_fact_files([fname], unifier=[P, Q], factbase=fb_out)
            self.assertEqual(fb_in, fb_out)

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_lark_parse_facts(self):
        class P(Predicate):
            """A P predicate"""

            x = IntegerField
            y = StringField

        class Q(Predicate):
            """A Q predicate"""

            x = ConstantField
            y = P.Field

        asp1 = """p(1,"home\\""). -p(-2,"blah").\n"""
        asp2 = asp1 + """q(X,Y) :- p(X,Y)."""

        fb_p = FactBase([P(1, 'home"'), P(-2, "blah", sign=False)])
        fb_in = FactBase(
            [
                P(1, 'home"'),
                Q("abc", P(3, "H ome")),
                Q("z", P(-1, "One more string")),
                P(-2, "blah", sign=False),
            ]
        )

        # Match a basic string with a rule
        fb_out = parse_fact_string(asp2, unifier=[P, Q])
        self.assertEqual(fb_p, fb_out)

        # All inputs and outputs match
        fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P, Q])
        self.assertEqual(fb_in, fb_out)

        # Match only the p/2 facts
        fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P])
        self.assertEqual(fb_p, fb_out)

        # Match with comments
        fb_out = parse_fact_string(fb_in.asp_str(commented=True), unifier=[P, Q])
        self.assertEqual(fb_in, fb_out)

        # Error on ununified facts
        with self.assertRaises(UnifierNoMatchError) as ctx:
            fb_out = parse_fact_string(fb_in.asp_str(), unifier=[P], raise_nomatch=True)
        check_errmsg("Cannot unify symbol 'q(abc", ctx)

        # Error on nonfact
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp2, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 2

        # Try the fact files parser
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = os.path.join(tmpdirname, "asp.lp")
            with open(fname, "w+") as f:
                f.write(fb_in.asp_str(commented=True))
            fb_out = parse_fact_files([fname], unifier=[P, Q])
            self.assertEqual(fb_in, fb_out)

        # Option where a factbase is given
        fb_out = FactBase()
        parse_fact_string(fb_in.asp_str(commented=True), unifier=[P, Q], factbase=fb_out)
        self.assertEqual(fb_in, fb_out)

        # Fact file parser where factbase is given
        with tempfile.TemporaryDirectory() as tmpdirname:
            fname = os.path.join(tmpdirname, "asp.lp")
            with open(fname, "w+") as f:
                f.write(fb_in.asp_str(commented=True))
            fb_out = FactBase()
            parse_fact_files([fname], unifier=[P, Q], factbase=fb_out)
            self.assertEqual(fb_in, fb_out)

    # --------------------------------------------------------------------------
    # Test parsing some nested facts
    # --------------------------------------------------------------------------
    def test_parse_nested_facts(self):
        class P(Predicate):
            x = IntegerField
            y = define_nested_list_field(ConstantField)

        fb_in = FactBase([P(x=1, y=tuple(["a", "b", "c"]))])
        aspstr = fb_in.asp_str()
        fb_out = parse_fact_string(aspstr, unifier=[P], raise_nomatch=True)
        self.assertEqual(fb_in, fb_out)

    # --------------------------------------------------------------------------
    # Test lark parsing some nested facts
    # --------------------------------------------------------------------------
    def test_lark_parse_nested_facts(self):
        class P(Predicate):
            x = IntegerField
            y = define_nested_list_field(ConstantField)

        set_symbol_mode(SymbolMode.NOCLINGO)

        fb_in = FactBase([P(x=1, y=tuple(["a", "b", "c"]))])
        aspstr = fb_in.asp_str()
        fb_out = parse_fact_string(aspstr, unifier=[P], raise_nomatch=True, raise_nonfact=True)
        self.assertEqual(fb_in, fb_out)

        set_symbol_mode(SymbolMode.CLINGO)

    # --------------------------------------------------------------------------
    # Parsing non simple facts to raise FactParserError. Non simple facts include:
    # - a term with @-function call (this needs a Control object for grounding)
    # - a disjunctive fact
    # - a choice rule
    # --------------------------------------------------------------------------
    def test_parse_non_simple_facts(self):
        class P(Predicate):
            """A P predicate"""

            x = IntegerField

        # Using an external function
        asp = """p(@func(1))."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A choice rule
        asp = """{ p(2); p(3) }."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A disjunctive fact
        asp = """p(2); p(3)."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A theory atom - let the general non-fact literal catch this
        asp = """&diff{p(2)}."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

    # --------------------------------------------------------------------------
    # Parsing non simple facts to raise FactParserError with NOCLINGO mode (so
    # using the lark parser).
    # --------------------------------------------------------------------------
    def test_lark_parse_non_simple_facts(self):
        class P(Predicate):
            """A P predicate"""

            x = IntegerField

        set_symbol_mode(SymbolMode.NOCLINGO)

        # Using an external function
        asp = """p(@func(1))."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A choice rule
        asp = """{ p(2); p(3) }."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A disjunctive fact
        asp = """p(2); p(3)."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        # A theory atom - let the general non-fact literal catch this
        asp = """&diff{p(2)}."""
        with self.assertRaises(FactParserError) as ctx:
            fb_out = parse_fact_string(asp, unifier=[P], raise_nonfact=True)
        assert ctx.exception.line == 1

        set_symbol_mode(SymbolMode.CLINGO)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
