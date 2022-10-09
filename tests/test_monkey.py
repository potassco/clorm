# ------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
# ------------------------------------------------------------------------------
import unittest

from clorm import monkey

__all__ = [
    "ClingoPatchTestCase",
]

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class ClingoPatchTestCase(unittest.TestCase):
    def setUp(self):
        monkey.patch()  # must call this before importing clingo

    def tearDown(self):
        monkey.unpatch()
        pass

    # --------------------------------------------------------------------------
    # Test processing clingo Model
    # --------------------------------------------------------------------------
    def test_monkey(self):
        from clingo import Control

        from clorm import FactBase, IntegerField, Predicate, StringField, SymbolPredicateUnifier

        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        @spu.register
        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        af1 = Afact(1, "aaa")
        af2 = Afact(2, "bbb")
        af3 = Afact(3, "aaa")
        bf1 = Bfact(1, "eee")
        bf2 = Bfact(2, "fff")
        bf2 = Bfact(3, "ggg")

        fb2 = None

        def on_model(model):
            nonlocal fb2
            fb2 = model.facts(spu, atoms=True)

        fb1 = FactBase([af1, af2, af3, bf1, bf2])
        ctrl = Control()
        ctrl.add_facts(fb1)
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model)

        s_a_all = fb2.query(Afact)
        self.assertEqual(set([a for a in s_a_all.all()]), set([af1, af2, af3]))


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
