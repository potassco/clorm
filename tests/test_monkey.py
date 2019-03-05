#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest
import sys
from clorm import monkey

__all__ = [
    'ClingoPatchTestCase',
    'NoClingoPatchTestCase'
    ]

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class ClingoPatchTestCase(unittest.TestCase):
    def setUp(self):
        monkey.patch() # must call this before importing clingo

    def tearDown(self):
        monkey.unpatch()
        pass

    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_monkey(self):
        from clingo import Control
        from clorm import Predicate, IntegerField, StringField, FactBase, FactBaseBuilder

        fbb = FactBaseBuilder()

        @fbb.register
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()

        @fbb.register
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        af1 = Afact(1,"aaa")
        af2 = Afact(2,"bbb")
        af3 = Afact(3,"aaa")
        bf1 = Bfact(1,"eee")
        bf2 = Bfact(2,"fff")
        bf2 = Bfact(3,"ggg")

        fb2 = None
        def on_model(model):
            nonlocal fb2
            fb2 = model.facts(fbb, atoms=True)

        fb1 = FactBase([af1,af2,af3,bf1,bf2])
        ctrl = Control()
        ctrl.add_facts(fb1)
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model)

        s_a_all = fb2.select(Afact)
        self.assertEqual(set([a for a in s_a_all.get()]), set([af1,af2,af3]))


class NoClingoPatchTestCase(unittest.TestCase):
    def setUp(self):
        monkey.noclingo_patch() # must call this before importing clingo

    def tearDown(self):
        monkey.noclingo_unpatch()
        pass

    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_noclingo(self):
        from clingo import Control
        import clingo
        import clorm.noclingo as noclingo

        self.assertEqual(clingo.String("blah"), noclingo.String("blah"))
        self.assertEqual(clingo.Number(5), noclingo.Number(5))
        with self.assertRaises(TypeError) as ctx:
            instance = Control()
        with self.assertRaises(TypeError) as ctx:
            instance = clingo.Control()


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
