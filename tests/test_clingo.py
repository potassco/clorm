#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest

import clingo as oclingo
import clorm.clingo as cclingo
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
            self.assertTrue(model.contains(af1.raw))
            fb2 = model.facts(fbb, atoms=True)

            # Check that the known attributes behave the same as the real model
            self.assertEqual(model.cost, model._model.cost)
            self.assertEqual(model.number, model._model.number)
            self.assertEqual(model.optimality_proven, model._model.optimality_proven)
            self.assertEqual(model.thread_id, model._model.thread_id)
            self.assertEqual(model.type, model._model.type)

            # Note: the SolveControl object returned is created dynamically on
            # each call so will be different for both calls. So test that the
            # symbolic_atoms property is the same.
            sas1=set(model.context.symbolic_atoms)
            sas2=set(model._model.context.symbolic_atoms)
            self.assertEqual(len(sas1),len(sas2))


        # Use the orignal clingo.Control object so that we can test the wrapper call
        ctrlX_ = oclingo.Control()
        ctrl = cclingo.Control(control_ = ctrlX_)
        ctrl.add_facts(fb1)
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model)

        # Check that the known control attributes behave the same as the real control
        cfg1=ctrl.configuration
        cfg2=ctrl._ctrl.configuration
        self.assertEqual(len(cfg1),len(cfg2))
        self.assertEqual(set(cfg1.keys),set(cfg2.keys))
        sas1=set(ctrl.symbolic_atoms)
        sas2=set(ctrl._ctrl.symbolic_atoms)
        self.assertEqual(len(sas1),len(sas2))
        self.assertEqual(ctrl.is_conflicting, ctrl._ctrl.is_conflicting)
        stat1=ctrl.statistics
        stat2=ctrl._ctrl.statistics
        self.assertEqual(len(stat1),len(stat2))
        tas1=ctrl.theory_atoms
        tas2=ctrl._ctrl.theory_atoms
        self.assertEqual(len(tas1),len(tas2))

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

        ctrl = cclingo.Control()
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

        ctrl = cclingo.Control()
        ctrl.add_facts([bf1,bf2])
        ctrl.ground([("base",[])])
        ctrl.solve(on_model=on_model2)

    #--------------------------------------------------------------------------
    # Test the solvehandle
    #--------------------------------------------------------------------------
    def test_solvehandle_wrapper(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class Fact(Predicate):
            num1=IntegerField()
            class Meta: name="f"

        prgstr = """{ g(N) : f(N) } = 1."""
        f1 = Fact(1) ; f2 = Fact(2) ; f3 = Fact(3)
        ctrl = cclingo.Control(['-n 0'])
        with ctrl.builder() as b:
            oclingo.parse_program(prgstr, lambda stm: b.add(stm))
        ctrl.add_facts([f1,f2,f3])
        ctrl.ground([("base",[])])

        with ctrl.solve(yield_=True) as sh:
            self.assertTrue(isinstance(sh, cclingo.SolveHandle))
            self.assertFalse(isinstance(sh, oclingo.SolveHandle))
            num_models=0
            for m in sh:
                self.assertTrue(isinstance(m, cclingo.Model))
                self.assertFalse(isinstance(m, oclingo.Model))
                num_models+=1
            self.assertEqual(num_models,3)

    #--------------------------------------------------------------------------
    # Test the solvehandle
    #--------------------------------------------------------------------------
    def test_solve_with_assumptions(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class F(Predicate):
            num1=IntegerField()
        @fbb.register
        class G(Predicate):
            num1=IntegerField()

        prgstr = """{ g(N) : f(N) } = 1."""
        f1 = F(1) ; f2 = F(2) ; f3 = F(3)
        g1 = G(1) ; g2 = G(2) ; g3 = G(3)
        ctrl = cclingo.Control(['-n 0'])
        with ctrl.builder() as b:
            oclingo.parse_program(prgstr, lambda stm: b.add(stm))
        ctrl.add_facts([f1,f2,f3])
        ctrl.ground([("base",[])])

        num_models=0
        def on_modelT(m):
            nonlocal num_models
            fb = m.facts(fbb,atoms=True)
            self.assertTrue(g1 in fb)
            num_models += 1

        def on_modelF(m):
            nonlocal num_models
            fb = m.facts(fbb,atoms=True)
            self.assertTrue(g1 not in fb)
            self.assertFalse(g1 in fb)
            num_models += 1

        num_models=0
        ctrl.solve(on_model=on_modelT, assumptions=[(g1,True)])
        self.assertEqual(num_models, 1)
        num_models=0
        ctrl.solve(on_model=on_modelT, assumptions=[(g1.raw,True)])
        self.assertEqual(num_models, 1)
        num_models=0
        ctrl.solve(on_model=on_modelF, assumptions=[(g1,False)])
        self.assertEqual(num_models, 2)

        fb2 = FactBase([g1])
        num_models=0
        ctrl.solve(on_model=on_modelT, assumptions=fb2)
        self.assertEqual(num_models, 1)

    #--------------------------------------------------------------------------
    # Test the solvehandle
    #--------------------------------------------------------------------------
    def test_solve_returning_solvehandle(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class F(Predicate):
            num1=IntegerField()
        f1 = F(1) ; f2 = F(2) ; f3 = F(3)
        infb=FactBase([f1,f2,f3])
        ctrl = cclingo.Control(['-n 0'])
        ctrl.add_facts(infb)
        ctrl.ground([("base",[])])

        done=False
        def on_model(m):
            nonlocal done
            outfb = m.facts(fbb,atoms=True)
            self.assertEqual(infb,outfb)
            self.assertFalse(done)
            done=True

        if oclingo.__version__ > '5.3.1':
            asynckw="async_"
        else:
            asynckw="async"

        # Test the async mode
        kwargs={ "on_model": on_model, asynckw: True }
        done=False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        sh.get()
        self.assertTrue(done)

        # Test the yield mode
        kwargs={ "on_model": on_model, "yield_": True }
        done=False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        count=0
        for m in sh:
            count += 1
            outfb = m.facts(fbb,atoms=True)
            self.assertEqual(infb,outfb)
        self.assertEqual(count,1)
        self.assertTrue(done)

        # Test both async and yield mode
        kwargs={ "on_model": on_model, asynckw: True, "yield_": True }
        done=False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        count=0
        for m in sh:
            count += 1
            outfb = m.facts(fbb,atoms=True)
            self.assertEqual(infb,outfb)
        self.assertEqual(count,1)
        self.assertTrue(done)


    #--------------------------------------------------------------------------
    # Test bad arguments
    #--------------------------------------------------------------------------
    def test_bad_arguments(self):
        fbb=FactBaseBuilder()
        @fbb.register
        class Fact(Predicate):
            num1=IntegerField()
            class Meta: name="f"

        f1 = Fact(1) ; f2 = Fact(2) ; f3 = Fact(3)
        ctrl = cclingo.Control(['-n 0'])
        ctrl.add_facts([f1,f2,f3])
        ctrl.ground([("base",[])])

        with self.assertRaises(ValueError) as ctx:
            ctrl.solve(assump=[f1])

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
