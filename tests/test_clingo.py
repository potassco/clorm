# ------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
# ------------------------------------------------------------------------------
import unittest

import clingo as oclingo

import clorm.clingo as cclingo
from clorm import FactBase, IntegerField, Predicate, StringField, SymbolPredicateUnifier, ph1_
from clorm.clingo import Control, _expand_assumptions

from .support import add_program_string, check_errmsg

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = ["ClingoTestCase"]

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


class ClingoTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Basic test of connecting to clingo without any wrapping
    # --------------------------------------------------------------------------
    def test_basic_clingo_connection(self):
        class F(Predicate):
            anum = IntegerField

        f1 = F(1)
        f2 = F(2)
        prgstr = "{}.\n{}.\n".format(f1, f2)
        ctrl = oclingo.Control()
        add_program_string(ctrl, prgstr)

        ctrl.ground([("base", [])])
        model = None
        with ctrl.solve(yield_=True) as sh:
            for m in sh:
                model = str(m)
        self.assertEqual(model, "{} {}".format(f1, f2))

    # --------------------------------------------------------------------------
    # Test processing clingo Model
    # --------------------------------------------------------------------------
    def test_control_model_integration(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()
            num2 = IntegerField()
            str1 = StringField()

        @spu.register
        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        af1 = Afact(1, 10, "bbb")
        af2 = Afact(2, 20, "aaa")
        af3 = Afact(3, 20, "aaa")
        bf1 = Bfact(1, "aaa")
        bf2 = Bfact(2, "bbb")

        fb1 = FactBase()
        fb1.add([af1, af2, af3, bf1, bf2])

        fb2 = None

        def on_model(model):
            nonlocal fb2
            self.assertTrue(model.contains(af1))
            self.assertTrue(model.contains(af1.raw))
            self.assertTrue(model.model_.contains(af1.raw))
            fb2 = model.facts(spu, atoms=True)

            # Check that the known attributes behave the same as the real model
            self.assertEqual(model.cost, model.model_.cost)
            self.assertEqual(model.number, model.model_.number)
            self.assertEqual(model.optimality_proven, model.model_.optimality_proven)
            self.assertEqual(model.thread_id, model.model_.thread_id)
            self.assertEqual(model.type, model.model_.type)

            # Note: the SolveControl object returned is created dynamically on
            # each call so will be different for both calls. So test that the
            # symbolic_atoms property is the same.
            sas1 = set(model.context.symbolic_atoms)
            sas2 = set(model.model_.context.symbolic_atoms)
            self.assertEqual(len(sas1), len(sas2))

            # Test that clorm.clingo.Model produces the correct string
            self.assertEqual(str(model), str(model.model_))

            if oclingo.__version__ < "5.5.0":
                self.assertEqual(repr(model), repr(model.model_))

        # Use the orignal clingo.Control object so that we can test the wrapper call
        ctrlX_ = oclingo.Control()
        ctrl = cclingo.Control(control_=ctrlX_)

        ctrl.add_facts(fb1)
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model)

        # Check that the known control attributes behave the same as the real control
        cfg1 = ctrl.configuration
        cfg2 = ctrl.control_.configuration

        self.assertEqual(len(cfg1), len(cfg2))
        self.assertEqual(set(cfg1.keys), set(cfg2.keys))
        sas1 = set(ctrl.symbolic_atoms)
        sas2 = set(ctrl.control_.symbolic_atoms)
        self.assertEqual(len(sas1), len(sas2))
        self.assertEqual(ctrl.is_conflicting, ctrl.control_.is_conflicting)
        stat1 = ctrl.statistics
        stat2 = ctrl.control_.statistics
        self.assertEqual(len(stat1), len(stat2))
        tas1 = ctrl.theory_atoms
        tas2 = ctrl.control_.theory_atoms
        self.assertEqual(len(list(tas1)), len(list(tas2)))

        # _control_add_facts works with both a list of facts (either
        # clorm.Predicate or clingo.Symbol instances) and a FactBase
        ctrl2 = Control()
        ctrl2.add_facts([af1, af2, af3.raw, bf1.raw, bf2])

        safact1 = fb2.query(Afact).where(Afact.num1 == ph1_)
        safact2 = fb2.query(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(safact1.bind(1).singleton(), af1)
        self.assertEqual(safact1.bind(2).singleton(), af2)
        self.assertEqual(safact1.bind(3).singleton(), af3)
        self.assertEqual(set(list(safact2.bind(1).all())), set([]))
        self.assertEqual(set(list(safact2.bind(2).all())), set([af1]))
        self.assertEqual(set(list(safact2.bind(3).all())), set([af1, af2]))
        self.assertEqual(fb2.query(Bfact).where(Bfact.str1 == "aaa").singleton(), bf1)
        self.assertEqual(fb2.query(Bfact).where(Bfact.str1 == "bbb").singleton(), bf2)

    # --------------------------------------------------------------------------
    # Test the wrapping of control objects
    # --------------------------------------------------------------------------
    def test_control_and_model_wrapper(self):

        # Test a control wrapper of a wrapper
        ctrl0 = oclingo.Control()
        ctrl1 = cclingo.Control(control_=ctrl0)
        ctrl2 = cclingo.Control(control_=ctrl1)
        ctrl2.ground([("base", [])])

        with ctrl2.solve(yield_=True) as sh:
            tmp = [m.facts(unifier=[], atoms=True) for m in sh]
            self.assertEqual(len(tmp), 1)
            self.assertEqual(len(tmp[0]), 0)

        # Test a model wrapper
        ctrl = oclingo.Control()
        ctrl.ground([("base", [])])
        with ctrl.solve(yield_=True) as sh:
            for n, m_ in enumerate(sh):
                self.assertEqual(n, 0)
                m = cclingo.Model(model=m_, unifier=[])
                self.assertEqual(len(m.facts()), 0)

        # Test wrapping a bad object - missing attributes and functions

        # Missing ground function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def solve(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg("'Bad' object has no attribute 'ground'", ctx)

        # Missing solve function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def ground(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg("'Bad' object has no attribute 'solve'", ctx)

        # Ground is an attribute but not a function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.ground = 4

                def solve(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'ground()'").format(
                type(bad)
            ),
            ctx,
        )

        # Solve is an attribute but not a function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.solve = 4

                def ground(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'solve()'").format(
                type(bad)
            ),
            ctx,
        )

        # Model wrapper with no "symbols" function or attribute
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.symbols = 2

            bad = Bad()
            m = cclingo.Model(model=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'symbols()'").format(
                type(bad)
            ),
            ctx,
        )

        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    pass

            bad = Bad()
            m = cclingo.Model(model=bad)
        check_errmsg("'Bad' object has no attribute 'symbols'", ctx)

    def test_class_defs_are_equal(self):
        from clorm.clingo import (
            ClormControl,
            ClormModel,
            ClormSolveHandle,
            Control,
            Model,
            SolveHandle,
        )

        self.assertEqual(Control, ClormControl)
        self.assertEqual(Model, ClormModel)
        self.assertEqual(SolveHandle, ClormSolveHandle)


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class Clingo54TestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Test the wrapping of control objects
    # --------------------------------------------------------------------------
    def test_control_and_model_wrapper(self):

        # Test a control wrapper of a wrapper
        ctrl0 = oclingo.Control()
        ctrl1 = cclingo.Control(control_=ctrl0)
        ctrl2 = cclingo.Control(control_=ctrl1)
        ctrl2.ground([("base", [])])
        with ctrl2.solve(yield_=True) as sh:
            tmp = [m.facts(unifier=[], atoms=True) for m in sh]
            self.assertEqual(len(tmp), 1)
            self.assertEqual(len(tmp[0]), 0)

        # Test a model wrapper
        ctrl = oclingo.Control()
        ctrl.ground([("base", [])])
        with ctrl.solve(yield_=True) as sh:
            for n, m_ in enumerate(sh):
                self.assertEqual(n, 0)
                m = cclingo.Model(model=m_, unifier=[])
                self.assertEqual(len(m.facts()), 0)

        # Test wrapping a bad object - missing attributes and functions

        # Missing ground function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def solve(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg("'Bad' object has no attribute 'ground'", ctx)

        # Missing solve function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def ground(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg("'Bad' object has no attribute 'solve'", ctx)

        # Ground is an attribute but not a function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.ground = 4

                def solve(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'ground()'").format(
                type(bad)
            ),
            ctx,
        )

        # Solve is an attribute but not a function
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.solve = 4

                def ground(self):
                    pass

            bad = Bad()
            ctrl = cclingo.Control(control_=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'solve()'").format(
                type(bad)
            ),
            ctx,
        )

        # Model wrapper with no "symbols" function or attribute
        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    self.symbols = 2

            bad = Bad()
            m = cclingo.Model(model=bad)
        check_errmsg(
            ("Wrapped object of type '{}' does not have a " "function 'symbols()'").format(
                type(bad)
            ),
            ctx,
        )

        with self.assertRaises(AttributeError) as ctx:

            class Bad(object):
                def __init__(self):
                    pass

            bad = Bad()
            m = cclingo.Model(model=bad)
        check_errmsg("'Bad' object has no attribute 'symbols'", ctx)

    # --------------------------------------------------------------------------
    # Test processing clingo Model
    # --------------------------------------------------------------------------
    def test_control_model_integration(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()
            num2 = IntegerField()
            str1 = StringField()

        @spu.register
        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        af1 = Afact(1, 10, "bbb")
        af2 = Afact(2, 20, "aaa")
        af3 = Afact(3, 20, "aaa")
        bf1 = Bfact(1, "aaa")
        bf2 = Bfact(2, "bbb")

        fb1 = FactBase()
        fb1.add([af1, af2, af3, bf1, bf2])

        fb2 = None

        def on_model(model):
            nonlocal fb2
            self.assertTrue(model.contains(af1))
            self.assertTrue(model.contains(af1.raw))
            self.assertTrue(model.model_.contains(af1.raw))
            fb2 = model.facts(spu, atoms=True)

            # Check that the known attributes behave the same as the real model
            self.assertEqual(model.cost, model.model_.cost)
            self.assertEqual(model.number, model.model_.number)
            self.assertEqual(model.optimality_proven, model.model_.optimality_proven)
            self.assertEqual(model.thread_id, model.model_.thread_id)
            self.assertEqual(model.type, model.model_.type)

            # Note: the SolveControl object returned is created dynamically on
            # each call so will be different for both calls. So test that the
            # symbolic_atoms property is the same.
            sas1 = set(model.context.symbolic_atoms)
            sas2 = set(model.model_.context.symbolic_atoms)
            self.assertEqual(len(sas1), len(sas2))

            # Test that clorm.clingo.Model produces the correct string
            self.assertEqual(str(model), str(model.model_))
            if oclingo.__version__ < "5.5.0":
                self.assertEqual(repr(model), repr(model.model_))

        # Use the orignal clingo.Control object so that we can test the wrapper call
        ctrlX_ = oclingo.Control()
        ctrl = cclingo.Control(control_=ctrlX_)
        ctrl.add_facts(fb1)
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model)

        # Check that the known control attributes behave the same as the real control
        cfg1 = ctrl.configuration
        cfg2 = ctrl.control_.configuration
        self.assertEqual(len(cfg1), len(cfg2))
        self.assertEqual(set(cfg1.keys), set(cfg2.keys))
        sas1 = set(ctrl.symbolic_atoms)
        sas2 = set(ctrl.control_.symbolic_atoms)
        self.assertEqual(len(sas1), len(sas2))
        self.assertEqual(ctrl.is_conflicting, ctrl.control_.is_conflicting)
        stat1 = ctrl.statistics
        stat2 = ctrl.control_.statistics
        self.assertEqual(len(stat1), len(stat2))
        tas1 = ctrl.theory_atoms
        tas2 = ctrl.control_.theory_atoms
        self.assertEqual(len(list(tas1)), len(list(tas2)))

        # _control_add_facts works with both a list of facts (either
        # clorm.Predicate or clingo.Symbol instances) and a FactBase
        ctrl2 = Control()
        ctrl2.add_facts([af1, af2, af3.raw, bf1.raw, bf2])

        safact1 = fb2.query(Afact).where(Afact.num1 == ph1_)
        safact2 = fb2.query(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(safact1.bind(1).singleton(), af1)
        self.assertEqual(safact1.bind(2).singleton(), af2)
        self.assertEqual(safact1.bind(3).singleton(), af3)
        self.assertEqual(set(list(safact2.bind(1).all())), set([]))
        self.assertEqual(set(list(safact2.bind(2).all())), set([af1]))
        self.assertEqual(set(list(safact2.bind(3).all())), set([af1, af2]))
        self.assertEqual(fb2.query(Bfact).where(Bfact.str1 == "aaa").singleton(), bf1)
        self.assertEqual(fb2.query(Bfact).where(Bfact.str1 == "bbb").singleton(), bf2)

        # Now test a select

    # --------------------------------------------------------------------------
    # Test processing clingo Model
    # --------------------------------------------------------------------------
    def test_clingo_to_clorm_model_integration(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()

        af1 = Afact(1)
        af2 = Afact(2)

        fb1 = FactBase()
        fb1.add([af1, af2])

        def on_model(model):
            cmodel = cclingo.Model(model=model)
            self.assertTrue(cmodel.contains(af1))
            self.assertTrue(model.contains(af1.raw))

        # Use the orignal clingo.Control object so that we can test the model wrapper
        ctrl = cclingo.Control()
        ctrl.add_facts(fb1)
        octrl = ctrl.control_
        octrl.ground([("base", [])])
        octrl.solve(on_model=on_model)

    # --------------------------------------------------------------------------
    # Test passing a SymbolPredicateUnifier to the model constructors
    # --------------------------------------------------------------------------
    def test_model_default_spu(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()

        af1 = Afact(1)
        af2 = Afact(2)

        # Test that the function works correctly when an spu is passed to the
        # Model constructor
        def on_model1(model):
            cmodel = cclingo.Model(model=model, unifier=spu)
            fb = cmodel.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.control_.solve(on_model=on_model1)

        # Test that the function works correctly when a unifier list is passed
        # to the Model constructor
        def on_model1(model):
            cmodel = cclingo.Model(model=model, unifier=[Afact])
            fb = cmodel.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.control_.solve(on_model=on_model1)

        # Test that an empty unifier list is valid (even if not useful)
        def on_model2(model):
            cmodel = cclingo.Model(model=model, unifier=[])
            fb = cmodel.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 0)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.control_.solve(on_model=on_model2)

        # Test that it fails correctly when no unifier is passed
        def on_model3(model):
            cmodel = cclingo.Model(model=model)
            with self.assertRaises(ValueError) as ctx:
                fb = cmodel.facts(atoms=True)

        ctrl.control_.solve(on_model=on_model3)

    # --------------------------------------------------------------------------
    # Test passing a SymbolPredicateUnifier to the control constructors and using the
    # on_model callback for solving
    # --------------------------------------------------------------------------
    def test_control_on_model_default_spu(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()

        af1 = Afact(1)
        af2 = Afact(2)

        # Test that the function works correctly when an spu is passed via the
        # clorm.clingo.Control constructor and using the on_model callback
        def on_model1(model):
            fb = model.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control(unifier=spu)
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model1)

        # Test that the function works correctly when a unifier list is passed
        # via the clorm.clingo.Control constructor and using the on_model
        # callback
        def on_model1(model):
            fb = model.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control(unifier=[Afact])
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model1)

        # Test that an empty unifier list is still valid (even if not useful)
        def on_model2(model):
            fb = model.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 0)

        ctrl = cclingo.Control(unifier=[])
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model2)

        # Test that it fails correctly when no spu is passed
        def on_model3(model):
            with self.assertRaises(ValueError) as ctx:
                fb = model.facts(atoms=True)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model3)

        # Now set the unifier and (checking the getter and setter) then re-run
        # the solver to show that it works
        ctrl.unifier = [Afact]
        spu = ctrl.unifier
        self.assertTrue(type(spu), SymbolPredicateUnifier)
        self.assertEqual(spu.predicates, (Afact,))
        self.assertEqual(spu.indexes, ())
        ctrl.solve(on_model=on_model1)

    # --------------------------------------------------------------------------
    # Test passing a SymbolPredicateUnifier to the control constructors and using a
    # solvehandle for solving
    # --------------------------------------------------------------------------
    def test_control_solvehandle_default_spu(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()

        af1 = Afact(1)
        af2 = Afact(2)

        # Test that the function works correctly when an spu is passed via the
        # clorm.clingo.Control constructor and using the solvehandle
        def on_model1(model):
            fb = model.facts(atoms=True)
            self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control(unifier=spu)
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        with ctrl.solve(yield_=True) as sh:
            for m in sh:
                fb = m.facts(atoms=True)
                self.assertEqual(len(fb.facts()), 2)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        with ctrl.solve(yield_=True) as sh:
            for m in sh:
                with self.assertRaises(ValueError) as ctx:
                    fb = m.facts(atoms=True)

    # --------------------------------------------------------------------------
    # Test the different argument combinations for clingo Model.facts()
    # --------------------------------------------------------------------------
    def test_model_facts_arguments(self):
        class Af(Predicate):
            num1 = IntegerField()

        af1 = Af(1)
        af2 = Af(2)

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2])
        ctrl.ground([("base", [])])
        with ctrl.solve(yield_=True) as sh:
            m = next(iter(sh))
            fb = m.facts(unifier=[Af], atoms=True, raise_on_empty=True)
            self.assertEqual(len(fb.facts()), 2)
            fb = m.facts([Af], True, True, True, raise_on_empty=True)
            self.assertEqual(len(fb.facts()), 2)

            with self.assertRaises(TypeError) as ctx:
                fb = m.facts([Af], unifier=[Af])
            check_errmsg("facts() got multiple values for argument 'unifier'", ctx)

            with self.assertRaises(TypeError) as ctx:
                fb = m.facts([Af], True, True, True, True, True, True, raise_on_empty=True)
            check_errmsg("facts() got multiple values for argument 'raise_on_empty'", ctx)

    # --------------------------------------------------------------------------
    # Test processing clingo Model
    # --------------------------------------------------------------------------
    def test_model_facts(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Afact(Predicate):
            num1 = IntegerField()
            num2 = IntegerField()
            str1 = StringField()

        class Bfact(Predicate):
            num1 = IntegerField()
            str1 = StringField()

        af1 = Afact(1, 10, "bbb")
        af2 = Afact(2, 20, "aaa")
        af3 = Afact(3, 20, "aaa")
        bf1 = Bfact(1, "aaa")
        bf2 = Bfact(2, "bbb")

        def on_model1(model):
            fb = model.facts(spu, atoms=True, raise_on_empty=True)
            self.assertEqual(len(fb.facts()), 3)  # spu only imports Afact

        ctrl = cclingo.Control()
        ctrl.add_facts([af1, af2, af3, bf1, bf2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model1)

        spu2 = SymbolPredicateUnifier()

        def on_model2(model):
            # Note: because of the delayed initialisation you have to do
            # something with the factbase to get it to raise the error.
            with self.assertRaises(ValueError) as ctx:
                fb = model.facts(spu2, atoms=True, raise_on_empty=True)
                self.assertEqual(len(fb.facts()), 0)

        ctrl = cclingo.Control()
        ctrl.add_facts([bf1, bf2])
        ctrl.ground([("base", [])])
        ctrl.solve(on_model=on_model2)

    # --------------------------------------------------------------------------
    # Test the solvehandle
    # --------------------------------------------------------------------------
    def test_solvehandle_wrapper(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Fact(Predicate):
            num1 = IntegerField()

            class Meta:
                name = "f"

        prgstr = """{ g(N) : f(N) } = 1."""
        f1 = Fact(1)
        f2 = Fact(2)
        f3 = Fact(3)
        ctrl = cclingo.Control(["-n 0"])
        add_program_string(ctrl, prgstr)
        ctrl.add_facts([f1, f2, f3])
        ctrl.ground([("base", [])])

        with ctrl.solve(yield_=True) as sh:
            self.assertTrue(isinstance(sh, cclingo.SolveHandle))
            self.assertFalse(isinstance(sh, oclingo.SolveHandle))
            self.assertTrue(sh.solvehandle_)
            num_models = 0
            for m in sh:
                self.assertTrue(isinstance(m, cclingo.Model))
                self.assertFalse(isinstance(m, oclingo.Model))
                num_models += 1
            self.assertEqual(num_models, 3)

    # ----------------------------------------------------------------------------------------
    # Test expanding the assumptions - note: the order matters so for an input list of
    # predicates or symbols the output list is the corresponding symbols in the same order.
    # ----------------------------------------------------------------------------------------
    def test_expand_assumptions(self):
        class F(Predicate):
            num1 = IntegerField()

        class G(Predicate):
            num1 = IntegerField()

        f1 = F(1)
        f2 = F(2)
        g1 = G(1)

        r = _expand_assumptions([(f1, True), (g1, False)])
        self.assertEqual(r, [(f1.raw, True), (g1.raw, False)])

        r = _expand_assumptions([(FactBase([f1, f2]), True), (set([g1]), False)])
        self.assertEqual(r, [(f1.raw, True), (f2.raw, True), (g1.raw, False)])

        with self.assertRaises(TypeError) as ctx:
            _expand_assumptions([g1])
        with self.assertRaises(TypeError) as ctx:
            _expand_assumptions(g1)

    # ----------------------------------------------------------------------------------------
    # Test the solvehandle
    # ----------------------------------------------------------------------------------------
    def test_solve_with_assumptions_simple(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class F(Predicate):
            num1 = IntegerField()

        @spu.register
        class G(Predicate):
            num1 = IntegerField()

        prgstr = """{ g(N) : f(N) } = 1."""
        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        g1 = G(1)
        g2 = G(2)
        g3 = G(3)
        ctrl = cclingo.Control(["-n 0"])
        add_program_string(ctrl, prgstr)
        ctrl.add_facts([f1, f2, f3])
        ctrl.ground([("base", [])])

        num_models = 0

        def on_modelT(m):
            nonlocal num_models
            fb = m.facts(spu, atoms=True)
            self.assertTrue(g1 in fb)
            num_models += 1

        def on_modelF(m):
            nonlocal num_models
            fb = m.facts(spu, atoms=True)
            self.assertTrue(g1 not in fb)
            self.assertFalse(g1 in fb)
            num_models += 1

        num_models = 0
        ctrl.solve(on_model=on_modelT, assumptions=[(g1, True)])
        self.assertEqual(num_models, 1)
        num_models = 0
        ctrl.solve(on_model=on_modelT, assumptions=[(g1.raw, True)])
        self.assertEqual(num_models, 1)
        num_models = 0
        ctrl.solve(on_model=on_modelF, assumptions=[(g1, False)])
        self.assertEqual(num_models, 2)
        fb2 = FactBase([g1])
        num_models = 0
        ctrl.solve(on_model=on_modelT, assumptions=[(fb2, True)])
        self.assertEqual(num_models, 1)

    # --------------------------------------------------------------------------
    # Test the solvehandle
    # --------------------------------------------------------------------------
    def test_solve_with_assumptions_complex(self):
        class F(Predicate):
            num1 = IntegerField()

        class G(Predicate):
            num1 = IntegerField()

        prgstr = """ 1 { g(N) : f(N) } 2."""
        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        g1 = G(1)
        g2 = G(2)
        g3 = G(3)
        ctrl = cclingo.Control(["-n 0"], unifier=[G])
        add_program_string(ctrl, prgstr)
        ctrl.add_facts([f1, f2, f3])
        ctrl.ground([("base", [])])

        num_models = 0

        def on_model(m):
            nonlocal num_models
            fb = m.facts(atoms=True)
            self.assertTrue(len(fb) <= 2)
            self.assertTrue(len(fb) >= 1)
            num_models += 1

        num_models = 0
        if oclingo.__version__ >= "5.5.0":
            ctrl.solve(on_model=on_model, assumptions=[])
        else:
            ctrl.solve(on_model=on_model, assumptions=None)
        self.assertEqual(num_models, 6)
        num_models = 0
        ctrl.solve(on_model=on_model)
        self.assertEqual(num_models, 6)

        num_models = 0
        ctrl.solve(on_model=on_model, assumptions=[(g1, True)])
        self.assertEqual(num_models, 3)

        # Mixing raw symbol and predicate in a set
        num_models = 0
        ctrl.solve(on_model=on_model, assumptions=[(set([g1.raw, g2]), True)])
        self.assertEqual(num_models, 1)
        num_models = 0
        ctrl.solve(on_model=on_model, assumptions=[(FactBase([g1, g2]), True)])
        self.assertEqual(num_models, 1)
        num_models = 0
        ctrl.solve(on_model=on_model, assumptions=[(FactBase([g1]), True), (set([g2]), False)])
        self.assertEqual(num_models, 2)

        num_models = 0
        ctrl.solve(on_model=on_model, assumptions=[(FactBase([g1]), True), (set([g2]), False)])
        self.assertEqual(num_models, 2)

    # --------------------------------------------------------------------------
    # Test the solve
    # --------------------------------------------------------------------------
    def test_solve_with_on_finish(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class F(Predicate):
            num1 = IntegerField()

        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        infb = FactBase([f1, f2, f2])
        ctrl = cclingo.Control(["-n 0"])
        ctrl.add_facts(infb)
        ctrl.ground([("base", [])])

        called = False

        def on_model(m):
            nonlocal called
            outfb = m.facts(spu, atoms=True)
            self.assertEqual(infb, outfb)
            self.assertFalse(called)
            called = True

        def on_finish(sr):
            self.assertTrue(sr.satisfiable)
            self.assertFalse(sr.unsatisfiable)

        sr = ctrl.solve(on_model=on_model, on_finish=on_finish)
        self.assertTrue(sr.satisfiable)
        self.assertFalse(sr.unsatisfiable)

    # --------------------------------------------------------------------------
    # Test the solve
    # --------------------------------------------------------------------------
    def test_solve_with_on_statistics(self):
        class F(Predicate):
            num1 = IntegerField()

        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        infb = FactBase([f1, f2, f2])
        ctrl = cclingo.Control(["-n 0"])
        ctrl.add_facts(infb)
        ctrl.ground([("base", [])])

        def on_model(model):
            nonlocal om_called
            om_called = True

        def on_statistics(stp, acc):
            nonlocal os_called
            self.assertEqual(type(stp), oclingo.StatisticsMap)
            os_called = True

        # Calling using positional arguments
        om_called = False
        os_called = False
        if oclingo.__version__ < "5.5.0":
            sr = ctrl.solve([], on_model, on_statistics)
        else:
            sr = ctrl.solve([], on_model, None, on_statistics)
        self.assertTrue(om_called)
        self.assertTrue(os_called)

        # Calling using keyword arguments
        om_called = False
        os_called = False
        sr = ctrl.solve(on_statistics=on_statistics)
        self.assertFalse(om_called)
        self.assertTrue(os_called)

    # --------------------------------------------------------------------------
    # Test the solve with on_unsat
    # --------------------------------------------------------------------------
    def test_solve_with_on_unsat(self):
        # There is no on_unsat or on_core functions for older versions.
        if oclingo.__version__ < "5.5.0":
            return

        # Program to test optimisation for on_unsat callback - note: setting the appropriate
        # optimisation strategy is important to trigger the callback.
        prgstr = """
1 { p(X); q(X) } 1 :- X=1..3.
#minimize { 1,p,X: p(X); 1,q,X: q(X) }.
        """

        ctrl = cclingo.Control()
        conf = ctrl.configuration
        conf.solver.opt_strategy = "usc,oll,0"
        add_program_string(ctrl, prgstr)
        ctrl.ground([("base", [])])

        def on_unsat(ints):
            nonlocal ou_called
            ou_called = True

        # Calling using positional arguments
        ou_called = False
        sr = ctrl.solve([], None, on_unsat)
        self.assertTrue(ou_called)

        # Caling using keyword arguments
        ou_called = False
        sr = ctrl.solve(on_unsat=on_unsat)
        self.assertTrue(ou_called)

    # --------------------------------------------------------------------------
    # Test the solve with on_core
    # --------------------------------------------------------------------------
    def test_solve_with_on_core(self):
        # There is no on_unsat or on_core functions for older versions.
        if oclingo.__version__ < "5.5.0":
            return

        class F(Predicate):
            num1 = IntegerField()

        # Program to test unsatisfiable cores
        prgstr = """
2 {f(1..3)} 2.
"""
        all_facts = FactBase([F(1), F(2), F(3)])
        ctrl = cclingo.Control(unifier=[F])
        add_program_string(ctrl, prgstr)
        ctrl.ground([("base", [])])
        all_literals = [ctrl.symbolic_atoms[f.raw].literal for f in all_facts]

        def on_core(ints):
            nonlocal oc_called
            assert set(all_literals) == set(ints)
            oc_called = True

        # Calling using positional arguments
        oc_called = False  #
        sr = ctrl.solve([(all_facts, True)], None, None, None, None, on_core)
        self.assertTrue(oc_called)

        # Calling using keyword arguments
        oc_called = False
        sr = ctrl.solve(assumptions=[(all_facts, True)], on_core=on_core)
        self.assertTrue(oc_called)

    # --------------------------------------------------------------------------
    # Test accessing some other control variables that are not explcitly wrapped
    # --------------------------------------------------------------------------
    def test_control_access_others(self):
        class F(Predicate):
            num1 = IntegerField()

        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        infb = FactBase([f1, f2])
        ctrl = cclingo.Control(["-n 0"])
        ctrl.add_facts(infb)
        ctrl.ground([("base", [])])
        self.assertTrue(ctrl.symbolic_atoms[f1.raw])

    # --------------------------------------------------------------------------
    # Test the solvehandle
    # --------------------------------------------------------------------------
    def test_solve_returning_solvehandle(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class F(Predicate):
            num1 = IntegerField()

        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        infb = FactBase([f1, f2, f3])
        ctrl = cclingo.Control(["-n 0"])
        ctrl.add_facts(infb)
        ctrl.ground([("base", [])])

        done = False

        def on_model(m):
            nonlocal done
            outfb = m.facts(spu, atoms=True)
            self.assertEqual(infb, outfb)
            self.assertFalse(done)
            done = True

        if oclingo.__version__ > "5.3.1":
            asynckw = "async_"
        else:
            asynckw = "async"

        # Test the async mode
        kwargs = {"on_model": on_model, asynckw: True}
        done = False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        sh.get()
        self.assertTrue(done)

        # Test the yield mode
        kwargs = {"on_model": on_model, "yield_": True}
        done = False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        count = 0
        for m in sh:
            count += 1
            outfb = m.facts(spu, atoms=True)
            self.assertEqual(infb, outfb)
        self.assertEqual(count, 1)
        self.assertTrue(done)

        # Test both async and yield mode
        kwargs = {"on_model": on_model, asynckw: True, "yield_": True}
        done = False
        sh = ctrl.solve(**kwargs)
        self.assertTrue(isinstance(sh, cclingo.SolveHandle))
        count = 0
        for m in sh:
            count += 1
            outfb = m.facts(spu, atoms=True)
            self.assertEqual(infb, outfb)
        self.assertEqual(count, 1)
        self.assertTrue(done)

    # --------------------------------------------------------------------------
    # Test bad arguments
    # --------------------------------------------------------------------------
    def test_bad_solve_arguments(self):
        spu = SymbolPredicateUnifier()

        @spu.register
        class Fact(Predicate):
            num1 = IntegerField()

            class Meta:
                name = "f"

        f1 = Fact(1)
        f2 = Fact(2)
        f3 = Fact(3)
        ctrl = cclingo.Control(["-n 0"])
        ctrl.add_facts([f1, f2, f3])
        ctrl.ground([("base", [])])

        with self.assertRaises(TypeError) as ctx:
            ctrl.solve(assump=[f1])

        with self.assertRaises(TypeError) as ctx:
            ctrl.solve([f1], assumptions=[f1])

        with self.assertRaises(TypeError) as ctx:
            ctrl.solve([f1])

    # --------------------------------------------------------------------------
    # Test assign external
    # --------------------------------------------------------------------------
    def test_assign_and_release_external(self):
        class F(Predicate):
            num1 = IntegerField()

        class G(Predicate):
            num1 = IntegerField()

        prgstr = """
#external f(1..3).
g(N) :- f(N)."""

        f1 = F(1)
        f2 = F(2)
        f3 = F(3)
        g1 = G(1)
        g2 = G(2)
        g3 = G(3)
        ctrl = cclingo.Control(unifier=[F, G])
        add_program_string(ctrl, prgstr)
        ctrl.ground([("base", [])])

        # Assign external for a factbase
        ctrl.assign_external(FactBase([f1, f2, f3]), True)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f1, f2, f3, g1, g2, g3]))

        # Assign external for a single clorm fact
        ctrl.assign_external(f1, False)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f2, f3, g2, g3]))

        # Assign external for a single clingo symbol
        ctrl.assign_external(f2.raw, False)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f3, g3]))

        # Back to all true so we can test release_external
        # Assign external for a factbase
        ctrl.assign_external(FactBase([f1, f2, f3]), True)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f1, f2, f3, g1, g2, g3]))

        # Release external for a FactBase
        ctrl.release_external(FactBase([f1]))
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f2, f3, g2, g3]))

        # Release external for a single clorm fact
        ctrl.release_external(f2)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase([f3, g3]))

        # Release external for a single clingo symbol
        ctrl.release_external(f3.raw)
        with ctrl.solve(yield_=True) as sh:
            m = list(sh)[0]
            fb = m.facts(atoms=True)
            self.assertEqual(fb, FactBase())


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
