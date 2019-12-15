'''A plugin replacement for the ``clingo`` modules that wraps the key clingo
objects to integrate Clorm ``Predicate`` and ``FactBase`` interfaces. See the
`Clingo API <https://potassco.org/clingo/python-api/current/clingo.html#Model>`_
for more details.

'''

import io
import sys
import functools
import itertools
from collections.abc import Iterable
from .orm import *
#import clorm as orm

# I want to replace the original clingo - re-exporting everything in clingo
# except replacing the class overides with my version: _class_overides = [
# 'Control', 'Model', 'SolveHandle' ]. The following seems to work but I'm not
# sure if this is bad.

#------------------------------------------------------------------------------
# Reference to the original clingo objects so that when we replace them our
# references point to the originals.
#------------------------------------------------------------------------------
import clingo as oclingo
OModel=oclingo.Model
OSolveHandle=oclingo.SolveHandle
OControl=oclingo.Control

from clingo import *
__all__ = list([ k for k in oclingo.__dict__.keys() if k[0] != '_'])
__version__ = oclingo.__version__

# ------------------------------------------------------------------------------
# Determine if an attribute name has the pattern of a magic method (ie. is
# callable and has name of the form __XXX__. Ideally, would like to have a
# system function that tells me the list of magic methods. But this should be
# good enough.
# ------------------------------------------------------------------------------

def _poss_magic_method(name,value):
    if not callable(value): return False
    if not name.startswith("__"): return False
    if not name.endswith("__"): return False
    if len(name) <= 4: return False
    if name[2] == '_': return False
    if name[-3] == '_': return False
    return True

# ------------------------------------------------------------------------------
# Helper function to smartly build a unifier if only a list of predicates have
# been provided.
# ------------------------------------------------------------------------------

def _build_unifier(unifier):
    if not unifier: return None
    if isinstance(unifier, SymbolPredicateUnifier): return unifier
    return SymbolPredicateUnifier(predicates=unifier)

# ------------------------------------------------------------------------------
# Wrap clingo.Model and override some functions
# ------------------------------------------------------------------------------
def _model_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._model, *args, **kwargs)
    return wrapper

def _model_property(name):
    def wrapper(self):
        return self._model.__getattribute__(name)
    return property(wrapper)

class _ModelMetaClass(type):
    def __new__(meta, name, bases, dct):
        ignore=["__init__", "__new__", "contains"]
        for key,value in OModel.__dict__.items():
            if key in ignore: continue
            if key.startswith("_") and not _poss_magic_method(key,value): continue
            if callable(value):
                dct[key]=_model_wrapper(value)
            else:
                dct[key]=_model_property(key)

        return super(_ModelMetaClass, meta).__new__(meta, name, bases, dct)

class Model(object, metaclass=_ModelMetaClass):
    '''Provides access to a model during a solve call.

    Objects mustn't be created manually. Instead they are returned by
    ``clorm.clingo.Control.solve`` callbacks.

    Behaves like ``clingo.Model`` but offers better integration with clorm facts
    and fact bases.

    '''

    def __init__(self, model,unifier=None):
        self._model = model
        self._unifier = _build_unifier(unifier)

    #------------------------------------------------------------------------------
    # Return the underlying model object
    #------------------------------------------------------------------------------
    @property
    def model_(self):
        '''Returns the underlying clingo.Model object.'''
        return self._model

    #------------------------------------------------------------------------------
    # A new function to return a list of facts - similar to symbols
    #------------------------------------------------------------------------------

    def facts(self, unifier=None, atoms=False, terms=False, shown=False,
              raise_on_empty=False):
        '''Returns a FactBase containing the facts in the model that unify with the
        SymbolPredicateUnifier.

        This function provides a wrapper around the ``clingo.Model.symbols``
        functions, but instead of returning a list of symbols it returns a
        FactBase containing the facts represented as ``clorm.Predicate``
        sub-class instances.

        Args:
           unifier(list | SymbolPredicateUnifier): used to unify and instantiate
              FactBase (Default: passed via the constructor if specified in the
              `clorm.clingo.Control` object)
           atoms: select all atoms in the model (Default: False)
           terms: select all terms displayed with #show statements (Default: False)
           shown: select all atoms and terms (Default: False)
           raise_on_empty: raise a ValueError if the resulting FactBase is empty
                           (Default: False)

        '''
        if unifier: unifier=_build_unifier(unifier)
        else: unifier=self._unifier
        if not unifier:
            msg = "Missing a predicate unifier specification in function call " + \
                "(no default was given at model instantiation)"
            raise ValueError(msg)

        return unifier.unify(
            symbols=self._model.symbols(atoms=atoms,terms=terms,shown=shown),
            raise_on_empty=raise_on_empty,
            delayed_init=True)

    #------------------------------------------------------------------------------
    # Overide contains
    #------------------------------------------------------------------------------

    def contains(self, fact):
        '''Return whether the fact or symbol is contained in the model. Extends
        ``clingo.Model.contains`` to allow for clorm facts as well as a clingo
        symbols.

        '''
        if isinstance(fact, Predicate):
            return self._model.contains(fact.raw)
        return self._model.contains(fact)


# ------------------------------------------------------------------------------
# Wrap clingo.SolveHandle and override some functions
# ------------------------------------------------------------------------------
def _solvehandle_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._handle, *args, **kwargs)
    return wrapper

def _solvehandle_property(name):
    def wrapper(self):
        return self._handle.__getattribute__(name)
    return property(wrapper)

class _SolveHandleMetaClass(type):
    def __new__(meta, name, bases, dct):
        ignore=["__init__", "__new__", "__iter__",
                "__next__", "__enter__", "__exit__"]
        for key,value in OSolveHandle.__dict__.items():
            if key in ignore: continue
            if key.startswith("_") and not _poss_magic_method(key,value): continue
            if callable(value):
                dct[key]=_solvehandle_wrapper(value)
            else:
                dct[key]=_solvehandle_property(key)

        return super(_SolveHandleMetaClass, meta).__new__(meta, name, bases, dct)

class SolveHandle(object, metaclass=_SolveHandleMetaClass):
    '''Handle for solve calls.

    Objects mustn't be created manually. Instead they are returned by
    ``clorm.clingo.Control.solve``.

    Behaves like ``clingo.SolveHandle`` but iterates over ``clorm.clingo.Model``
    objects.

    '''


    def __init__(self, handle,unifier=None):
        self._handle = handle
        self._unifier = _build_unifier(unifier)

    #------------------------------------------------------------------------------
    # Return the underlying solvehandle object
    #------------------------------------------------------------------------------
    @property
    def solvehandle_(self):
        '''Access the underlying clingo.SolveHandle object.'''
        return self._handle

    #------------------------------------------------------------------------------
    # Overrides
    #------------------------------------------------------------------------------

    def __iter__(self):
        return self

    def __next__(self):
        if self._unifier: return Model(self._handle.__next__(),unifier=self._unifier)
        else: return Model(self._handle.__next__())

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._handle.__exit__(exception_type,exception_value,traceback)

# ------------------------------------------------------------------------------
# Wrap clingo.Control and override some functions
# ------------------------------------------------------------------------------
def _control_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._ctrl, *args, **kwargs)
    return wrapper

def _control_property(name):
    def wrapper(self):
        return self._ctrl.__getattribute__(name)
    return property(wrapper)

class _ControlMetaClass(type):
    def __new__(meta, name, bases, dct):
        ignore=["__init__", "__new__", "assign_external", "release_external", "solve"]
        for key,value in OControl.__dict__.items():
            if key in ignore: continue
            if key.startswith("_") and not _poss_magic_method(key,value): continue
            if callable(value):
                dct[key]=_control_wrapper(value)
            else:
                dct[key]=_control_property(key)

        return super(_ControlMetaClass, meta).__new__(meta, name, bases, dct)

# ------------------------------------------------------------------------------
# Helper functions to expand the assumptions list as part of a solve() call
# ------------------------------------------------------------------------------
def _expand_assumptions(assumptions):
    pos_assump = set()
    neg_assump = set()

    def _add_fact(fact,bval):
        nonlocal pos_assump, neg_assump
        if isinstance(fact, Predicate): raw = fact.raw
        else: raw = fact
        if bval: pos_assump.add(raw)
        else: neg_assump.add(raw)

    try:
        for (arg,bval) in assumptions:
            if isinstance(arg, Iterable):
                for f in arg: _add_fact(f,bval)
            else:
                _add_fact(arg,bval)
    except (TypeError, ValueError) as e:
        raise TypeError(("Invalid solve assumptions. Expecting list of arg-bool "
                         "pairs (arg is a raw-symbol/predicate or a collection "
                         "of raw-symbols/predicates). Got: {}").format(assumptions))

    # Now returned a list of raw assumptions combining pos and neg
    pos = [ (raw,True) for raw in pos_assump ]
    neg = [ (raw,False) for raw in neg_assump ]
    return list(itertools.chain(pos,neg))

# ------------------------------------------------------------------------------
# Control class
# ------------------------------------------------------------------------------

class Control(object, metaclass=_ControlMetaClass):
    '''Control object for the grounding/solving process.

    Behaves like ``clingo.Control`` but with modifications to deal with Clorm
    facts and fact bases.

    Adds an additional parameter ``unifier`` to specify how any generated clingo
    models will be unified with the clorm Predicate definitions. The unifier can
    be specified as a list of predicates or as a SymbolPredicateUnifier object.

    An existing ``clingo.Control`` object can be passed using the ``control_``
    parameter.

    '''

    def __init__(self, *args, **kwargs):
        self._unifier = None
        if "unifier" in kwargs: self._unifier = _build_unifier(kwargs["unifier"])

        # Do we need to build a clingo.Control object or use an existing one
        if len(args) == 0 and "control_" in kwargs:
            self._ctrl = kwargs["control_"]
        else:
            kwargs2 = dict(kwargs)
            if "unifier" in kwargs2: del kwargs2["unifier"]
            self._ctrl = OControl(*args, **kwargs2)

    #------------------------------------------------------------------------------
    # Return the underlying control object
    #------------------------------------------------------------------------------
    @property
    def control_(self):
        '''Returns the underlying clingo.Control object.'''
        return self._ctrl

    #------------------------------------------------------------------------------
    # Make the unifier a property with a getter and setter
    #------------------------------------------------------------------------------
    @property
    def unifier(self):
        """Get/set the unifier.

        Unifier can be specified as a SymbolPredicateUnifier or a collection of
        Predicates. Always returns a SymbolPredicateUnifier (or None).

        """
        return self._unifier

    @unifier.setter
    def unifier(self,unifier):
        self._unifier = _build_unifier(unifier)

    #------------------------------------------------------------------------------
    # A new function to add facts from a factbase or a list of facts
    #------------------------------------------------------------------------------
    def add_facts(self, facts):
        '''Add facts to the control object. Note: facts must be added before grounding.

        Args:
          facts: a collection of ``clorm.Predicate`` instances (include a ``clorm.FactBase``)
        '''

        # Facts are added by manually generating Abstract Syntax Tree (AST)
        # elements for each fact and calling Control.add().
        line = 1
        with self._ctrl.builder() as bldr:
            for f in facts:
                floc = { "filename" : "<input>", "line" : line , "column" : 1 }
                location = { "begin" : floc, "end" : floc }
                r = ast.Rule(location,
                             ast.Literal(location, ast.Sign.NoSign,
                                         ast.SymbolicAtom(ast.Symbol(location,f.raw))),
                             [])
                bldr.add(r)
                line += 1
        return

#        # DON'T USE BACKEND - COULD CAUSE UNEXPECTED INTERACTION BETWEEN GROUNDER AND SOLVER
#        with self._ctrl.backend() as bknd:
#            for f in facts:
#                atm = bknd.add_atom(f.raw)
#                bknd.add_rule([atm])
#        return

    #------------------------------------------------------------------------------
    # Overide assign_external to deal with Predicate object and a Clingo Symbol
    #------------------------------------------------------------------------------
    def assign_external(self, external, truth):
        '''Assign a truth value to an external fact (or collection of facts)

        A fact can be a raw clingo.Symbol object, a clorm.Predicate instance, or
        a program literal (an int). If the external is a collection then the
        truth value is assigned to all elements in the collection.

        This function extends ``clingo.Control.release_external``.

        '''
        def _assign_fact(fact):
            if isinstance(fact, Predicate):
                self._ctrl.assign_external(fact.raw, truth)
            else:
                self._ctrl.assign_external(fact, truth)

        if isinstance(external, Iterable):
            for f in external: _assign_fact(f)
        else:
            _assign_fact(external)

    #------------------------------------------------------------------------------
    # Overide release_external to deal with Predicate object and a Clingo Symbol
    #------------------------------------------------------------------------------
    def release_external(self, external):
        '''Release an external fact (or collection of facts)

        A fact can be a raw clingo.Symbol object, a clorm.Predicate instance, or
        a program literal (an int). If the external is a collection then the
        truth value is assigned to all elements in the collection.

        This function extends ``clingo.Control.release_external``.

        '''
        def _release_fact(fact):
            if isinstance(fact, Predicate):
                self._ctrl.release_external(fact.raw)
            else:
                self._ctrl.release_external(fact)

        if isinstance(external, Iterable):
            for f in external: _release_fact(f)
        else:
            _release_fact(external)

    #---------------------------------------------------------------------------
    # Overide solve and if necessary replace on_model with a wrapper that
    # returns a clorm.Model object. Also because of the issue with using the
    # keyword "async" as a parameter in Python 3.7 (which means that newer
    # clingo version use "async_") we use a more complicated way to determine
    # the function parameters.
    #---------------------------------------------------------------------------
    def solve(self, **kwargs):
        '''Run the clingo solver.

        This function extends ``clingo.Control.solve()`` in two ways:

        1) The ``assumptions`` argument is generalised so that in the list of
        argument-boolean pairs the argument can be be a clingo symbol, or clorm
        predicate instance, or a collection of clingo symbols or clorm
        predicates.

        2) It returns either a ``clorm.clingo.SolveHandle`` wrapper object or a
        ``clorm.clingo.Model`` wrapper objects as appropriate (depending on the
        ``yield_`` and ``on_model`` parameters).

        '''

        # Build the list of valid arguments and their default values. We use
        # "async" or "async_" depending on clingo version. Note: "async" is a
        # keyword for Python 3.7+.
        validargs = { "assumptions": [], "on_model" : None,
                        "on_finish": None, "yield_" : False }
        async_keyword="async"
        if oclingo.__version__ > '5.3.1': async_keyword="async_"
        validargs[async_keyword] = False

        # validate the arguments and assign any missing default values
        keys = set(kwargs.keys())
        validkeys = set(validargs.keys())
        if not keys.issubset(validkeys):
            diff = keys - validkeys
            msg = "solve() got an unexpected keyword argument '{}'".format(next(iter(diff)))
            raise ValueError(msg)
        for k,v in validargs.items():
            if k not in kwargs: kwargs[k]=v

        # generate a new assumptions list if necesary
        if "assumptions" in kwargs and not kwargs["assumptions"] is None:
            kwargs["assumptions"] = _expand_assumptions(kwargs["assumptions"])

        # generate a new on_model function if necessary
        on_model=kwargs["on_model"]
        @functools.wraps(on_model)
        def on_model_wrapper(model):
            if self._unifier: return on_model(Model(model, self._unifier))
            else: return on_model(Model(model))
        if on_model: kwargs["on_model"] =  on_model_wrapper

        result = self._ctrl.solve(**kwargs)
        if kwargs["yield_"] or kwargs[async_keyword]:
            if self._unifier: return SolveHandle(result,unifier=self._unifier)
            else: return SolveHandle(result)
        else:
            return result


#------------------------------------------------------------------------------
# This is probably bad practice... Modify the original clingo docstrings so that
# when I generate the autodoc with clingo being mocked it installs a reference
# to the original clingo docs.
#
# UPDATE: I'm confused what the autodoc mocking is doing (or not doing). I'm
# sure I had it working but now seems to be failing. Adding more hacks :(
# ------------------------------------------------------------------------------

if not OControl or not OModel or not OSolveHandle:
    class OControl(object):
        '''For more details see the Clingo API for `Control <https://potassco.org/clingo/python-api/current/clingo.html#Control>`_'''

        def assign_external(self):
            '''For more details see the Clingo API for `Control <https://potassco.org/clingo/python-api/current/clingo.html#Control>`_'''
            pass
        def release_external(self):
            '''For more details see the Clingo API for `Control <https://potassco.org/clingo/python-api/current/clingo.html#Control>`_'''
            pass
        def solve(self):
            '''For more details see the Clingo API for `Control <https://potassco.org/clingo/python-api/current/clingo.html#Control>`_'''
            pass

    class OModel(object):
        '''For more details see the Clingo API for `Model <https://potassco.org/clingo/python-api/current/clingo.html#Model>`_'''

        def contains(self):
            '''For more details see the Clingo API for `Model <https://potassco.org/clingo/python-api/current/clingo.html#Model>`_'''
            pass

    class OSolveHandle(object):
        '''For more details see the Clingo API for `SolveHandle <https://potassco.org/clingo/python-api/current/clingo.html#SolveHandle>`_'''
        pass

if OModel.__doc__ != "Used by autodoc_mock_imports.":
    Control.__doc__ += OControl.__doc__
    Control.assign_external.__doc__ += OControl.assign_external.__doc__
    Control.release_external.__doc__ += OControl.release_external.__doc__
    Control.solve.__doc__ += OControl.solve.__doc__
    Model.__doc__ += OModel.__doc__
    Model.contains.__doc__ += OModel.contains.__doc__
    SolveHandle.__doc__ += OSolveHandle.__doc__
else:
    Control.__doc__ += "\n" + \
        "    For more details see the Clingo API for " + \
        '''`Control <https://potassco.org/clingo/python-api/current/clingo.html#Control>`_'''

    Model.__doc__ += "\n" + \
        "    For more details see the Clingo API for " + \
        '''`Model <https://potassco.org/clingo/python-api/current/clingo.html#Model>`_'''
    SolveHandle.__doc__ += "\n" + \
        "    For more details see the Clingo API for " + \
        '''`SolveHandle <https://potassco.org/clingo/python-api/current/clingo.html#SolveHandle>`_'''

#print("MODEL DOCS:\n\n{}\n\n".format(Model.__doc__))
#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

