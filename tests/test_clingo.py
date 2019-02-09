#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest

import clingo as oclingo
import clorm.clingo as nclingo
#from clorm.clingo import *
from clorm.clingo import Number, String, Function, parse_program, Control

from clorm import Predicate, IntegerField, StringField, FactBase,\
    FactBaseBuilder, ph1_

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class ClingoTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_control_model_integration(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        @fbb.register
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")

        fb1 = FactBase()
        fb1.add([af1,af2,af3,bf1,bf2])

        fb2 = None
        def on_model(model):
            nonlocal fb2
            self.assertTrue(model.contains(af1))
            fb2 = model.facts(fbb, atoms=True)

        # Use the orignal clingo.Control object so that we can test the wrapper call
        ctrlX_ = oclingo.Control()
        ctrl = nclingo.Control(control_ = ctrlX_)
        ctrl.add_facts(fb1)
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model)

        # _control_add_facts works with both a list of facts and a FactBase
        ctrl2 = Control()
        ctrl2.add_facts([af1,af2,af3,bf1,bf2])

        safact1 = fb2.select(Afact).where(Afact.num1 == ph1_)
        safact2 = fb2.select(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(safact1.get_unique(1), af1)
        self.assertEqual(safact1.get_unique(2), af2)
        self.assertEqual(safact1.get_unique(3), af3)
        self.assertEqual(set(list(safact2.get(1))), set([]))
        self.assertEqual(set(list(safact2.get(2))), set([af1]))
        self.assertEqual(set(list(safact2.get(3))), set([af1,af2]))
        self.assertEqual(fb2.select(Bfact).where(Bfact.str1 == "aaa").get_unique(), bf1)
        self.assertEqual(fb2.select(Bfact).where(Bfact.str1 == "bbb").get_unique(), bf2)

        # Now test a select


    #--------------------------------------------------------------------------
    # Test processing clingo Model
    #--------------------------------------------------------------------------
    def test_model_facts(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")

        def on_model1(model):
            fb = model.facts(fbb, atoms=True, raise_on_empty=True)
            self.assertEqual(len(fb.facts()), 3)  # fbb only imports Afact

        ctrl = nclingo.Control()
        ctrl.add_facts([af1,af2,af3,bf1,bf2])
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model1)

        fbb2=FactBaseBuilder()
        def on_model2(model):
            # Note: because of the delayed initialisation you have to do
            # something with the factbase to get it to raise the error.
            with self.assertRaises(ValueError) as ctx:
                fb = model.facts(fbb2, atoms=True, raise_on_empty=True)
                self.assertEqual(len(fb.facts()),0)

        ctrl = nclingo.Control()
        ctrl.add_facts([bf1,bf2])
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model2)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
