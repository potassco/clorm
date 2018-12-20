#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest

from clorm import monkey; monkey.patch() # must call this before importing clingo

from clingo import Number, String, Function, Control
from clorm import Predicate, IntegerField, StringField, FactBase, ph1_

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class MonkeyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_monkey(self):
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        af1 = Afact(1,"aaa")
        af2 = Afact(2,"bbb")
        af3 = Afact(3,"aaa")
        bf1 = Bfact(1,"eee")
        bf2 = Bfact(2,"fff")
        bf2 = Bfact(3,"ggg")

        class MyFacts(FactBase):
            predicates = [Afact,Bfact]

        fb2 = None
        def on_model(model):
            nonlocal fb2
            fb2 = model.facts(MyFacts, atoms=True)

        fb1 = FactBase(facts=[af1,af2,af3,bf1,bf2])
        ctrl = Control()
        ctrl.add_facts(fb1)
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model)

        s_a_all = fb2.select(Afact)
        self.assertEqual(set([a for a in s_a_all.get()]), set([af1,af2,af3]))


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
