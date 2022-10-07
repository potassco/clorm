# ------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
# ------------------------------------------------------------------------------

import json
import unittest

import clingo

import clorm.json as cjson
from clorm import ComplexTerm, FactBase, IntegerField, Predicate, StringField

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = ["JSONSymbolTestCase", "JSONPredicateTestCase"]

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class JSONSymbolTestCase(unittest.TestCase):
    def setUp(self):
        self.inf = clingo.Infimum
        self.sup = clingo.Supremum
        self.s1 = clingo.String("aaaa")
        self.s2 = clingo.String("bbbb")
        self.n1 = clingo.Number(24)
        self.n2 = clingo.Number(60)
        self.f1 = clingo.Function("", [self.s1, self.s2])
        self.f2 = clingo.Function("func1", [self.n1])
        self.f3 = clingo.Function("func2", [self.n2, self.f1])
        self.f4 = clingo.Function("func1", [], False)
        self.alls = [
            self.inf,
            self.sup,
            self.s1,
            self.s2,
            self.n1,
            self.n2,
            self.f1,
            self.f2,
            self.f3,
            self.f4,
        ]

        self.str_inf = '{"clingo.SymbolType": "Infimum"}'
        self.str_sup = '{"clingo.SymbolType": "Supremum"}'
        self.str_s1 = '{"clingo.SymbolType": "String", "string": "aaaa"}'
        self.str_s2 = '{"clingo.SymbolType": "String", "string": "bbbb"}'
        self.str_n1 = '{"clingo.SymbolType": "Number", "number": 24}'
        self.str_n2 = '{"clingo.SymbolType": "Number", "number": 60}'
        self.str_f1 = (
            '{"clingo.SymbolType": "Function", "name": "", "arguments": ['
            + self.str_s1
            + ", "
            + self.str_s2
            + '], "positive": true}'
        )
        self.str_f2 = (
            '{"clingo.SymbolType": "Function", "name": "func1", "arguments": ['
            + self.str_n1
            + '], "positive": true}'
        )
        self.str_f3 = (
            '{"clingo.SymbolType": "Function", "name": "func2", "arguments": ['
            + self.str_n2
            + ", "
            + self.str_f1
            + '], "positive": true}'
        )
        self.str_f4 = (
            '{"clingo.SymbolType": "Function", "name": "func1", "arguments": []'
            + ', "positive": false}'
        )
        self.str_alls = (
            "["
            + self.str_inf
            + ", "
            + self.str_sup
            + ", "
            + self.str_s1
            + ", "
            + self.str_s2
            + ", "
            + self.str_n1
            + ", "
            + self.str_n2
            + ", "
            + self.str_f1
            + ", "
            + self.str_f2
            + ", "
            + self.str_f3
            + ", "
            + self.str_f4
            + "]"
        )

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_symbol_encoder(self):
        inf = self.inf
        sup = self.sup
        s1 = self.s1
        s2 = self.s2
        n1 = self.n1
        n2 = self.n2
        f1 = self.f1
        f2 = self.f2
        f3 = self.f3
        alls = self.alls

        str_inf = self.str_inf
        str_sup = self.str_sup
        str_s1 = self.str_s1
        str_s2 = self.str_s2
        str_n1 = self.str_n1
        str_n2 = self.str_n2
        str_f1 = self.str_f1
        str_f2 = self.str_f2
        str_f3 = self.str_f3
        str_alls = self.str_alls

        encoder = cjson.symbol_encoder
        js_inf = json.dumps(inf, default=encoder)
        js_sup = json.dumps(sup, default=encoder)
        js_s1 = json.dumps(s1, default=encoder)
        js_s2 = json.dumps(s2, default=encoder)
        js_n1 = json.dumps(n1, default=encoder)
        js_n2 = json.dumps(n2, default=encoder)
        js_f1 = json.dumps(f1, default=encoder)
        js_f2 = json.dumps(f2, default=encoder)
        js_f3 = json.dumps(f3, default=encoder)
        js_alls = json.dumps(alls, default=encoder)

        self.assertEqual(js_inf, str_inf)
        self.assertEqual(js_sup, str_sup)
        self.assertEqual(js_s1, str_s1)
        self.assertEqual(js_s2, str_s2)
        self.assertEqual(js_n1, str_n1)
        self.assertEqual(js_n2, str_n2)

        self.assertEqual(js_f1, str_f1)
        self.assertEqual(js_f2, str_f2)
        self.assertEqual(js_f3, str_f3)
        self.assertEqual(js_alls, str_alls)

    def test_symbol_decoder(self):
        inf = self.inf
        sup = self.sup
        s1 = self.s1
        s2 = self.s2
        n1 = self.n1
        n2 = self.n2
        f1 = self.f1
        f2 = self.f2
        f3 = self.f3
        alls = self.alls

        str_inf = self.str_inf
        str_sup = self.str_sup
        str_s1 = self.str_s1
        str_s2 = self.str_s2
        str_n1 = self.str_n1
        str_n2 = self.str_n2
        str_f1 = self.str_f1
        str_f2 = self.str_f2
        str_f3 = self.str_f3
        str_alls = self.str_alls

        decoder = cjson.symbol_decoder
        self.assertEqual(json.loads(str_inf, object_hook=decoder), inf)
        self.assertEqual(json.loads(str_sup, object_hook=decoder), sup)
        self.assertEqual(json.loads(str_s1, object_hook=decoder), s1)
        self.assertEqual(json.loads(str_s2, object_hook=decoder), s2)
        self.assertEqual(json.loads(str_n1, object_hook=decoder), n1)
        self.assertEqual(json.loads(str_n2, object_hook=decoder), n2)
        self.assertEqual(json.loads(str_f1, object_hook=decoder), f1)
        self.assertEqual(json.loads(str_f2, object_hook=decoder), f2)
        self.assertEqual(json.loads(str_f3, object_hook=decoder), f3)
        self.assertEqual(json.loads(str_alls, object_hook=decoder), alls)


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class JSONPredicateTestCase(unittest.TestCase):
    def setUp(self):
        class Fun(ComplexTerm):
            aint = IntegerField()
            astr = StringField()

        class Tup(ComplexTerm):
            aint = IntegerField()
            astr = StringField()

            class Meta:
                is_tuple = True

        class Afact(Predicate):
            aint = IntegerField()
            afun = Fun.Field()

        class Bfact(Predicate):
            astr = StringField()
            atup = Tup.Field()

        class Cfact(ComplexTerm):
            aint = IntegerField()
            astr = StringField()

        afact1 = Afact(aint=10, afun=Fun(aint=1, astr="a"))
        afact2 = Afact(aint=20, afun=Fun(aint=2, astr="b"))
        bfact1 = Bfact(astr="aa", atup=Tup(aint=1, astr="a"))
        bfact2 = Bfact(astr="bb", atup=Tup(aint=2, astr="b"))
        self.allf = [afact1, bfact1, afact2, bfact2]

        self.Fun = Fun
        self.Tup = Tup
        self.Afact = Afact
        self.Bfact = Bfact
        self.Cfact = Cfact

        self.n1 = clingo.Number(60)
        self.s1 = clingo.String("aaaa")
        self.f1 = clingo.Function("", [self.n1, self.s1])
        self.p1 = Cfact(aint=60, astr="aaaa")
        self.fb1 = FactBase(facts=[self.p1])

        self.str_n1 = '{"clingo.SymbolType": "Number", "number": 60}'
        self.str_s1 = '{"clingo.SymbolType": "String", "string": "aaaa"}'
        self.str_f1 = (
            '{"clingo.SymbolType": "Function", "name": "cfact", '
            + '"arguments": ['
            + self.str_n1
            + ", "
            + self.str_s1
            + "]"
            + ', "positive": true}'
        )
        self.str_p1 = '{"clorm.Predicate": "Cfact", "raw": ' + self.str_f1 + "}"
        self.str_fb1 = '{"clorm.FactBase": [], "facts": [' + self.str_p1 + "]}"

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_predicate_coder(self):
        pc1 = cjson.FactBaseCoder()
        Afact = pc1.register(self.Afact)
        Bfact = pc1.register(self.Bfact)
        Cfact = pc1.register(self.Cfact)
        allf = self.allf
        p1 = self.p1
        str_p1 = self.str_p1

        pc2 = cjson.FactBaseCoder([Afact, Bfact, Cfact])
        json_str1 = pc1.dumps(allf)
        json_str2 = pc2.dumps(allf)
        result1 = pc1.loads(json_str2)
        result2 = pc2.loads(json_str1)
        self.assertEqual(allf, result1)
        self.assertEqual(allf, result2)

        json_p1 = pc2.dumps(p1)
        self.assertEqual(json_p1, str_p1)

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_factbase_coder(self):
        pc = cjson.FactBaseCoder()
        allf = self.allf
        fb1 = self.fb1
        str_fb1 = self.str_fb1
        Afact = pc.register(self.Afact)
        Bfact = pc.register(self.Bfact)
        Cfact = pc.register(self.Cfact)

        json_fb1 = pc.dumps(fb1)
        self.assertEqual(json_fb1, str_fb1)

        fb_in = FactBase(facts=allf, indexes=[Afact.aint, Bfact.astr])
        json_str = pc.dumps(fb_in, indent=4, sort_keys=True)
        fb_out = pc.loads(json_str)
        self.assertEqual(fb_in.indexes, fb_out.indexes)
        self.assertEqual(set(fb_in), set(fb_out))
        self.assertEqual(fb_in, fb_out)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
