'''A plugin replacement for the ``clingo`` modules that wraps the key clingo
objects to integrate Clorm ``Predicate`` and ``FactBase`` interfaces. See the
`Clingo API <https://potassco.org/clingo/python-api/current/clingo.html#Model>`_
for more details.

'''

import io
import sys
import functools
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
        ignore=["contains"]
        for key,value in OModel.__dict__.items():
            if key in ignore: continue
            if key.startswith("_"): continue
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
        self._unifier = unifier

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
        FactBaseBuilder.

        This function provides a wrapper around the ``clingo.Model.symbols``
        functions, but instead of returning a list of symbols it returns a
        FactBase containing the facts represented as ``clorm.Predicate``
        sub-class instances.

        Args:
           unifier(FactBaseBuilder): used to unify and instantiate FactBase (Default: passed
              via the constructor if specified in the `clorm.clingo.Control` object)
           atoms: select all atoms in the model (Default: False)
           terms: select all terms displayed with #show statements (Default: False)
           shown: select all atoms and terms (Default: False)
           raise_on_empty: raise a ValueError if the resulting FactBase is empty
                           (Default: False)

        '''
        if not unifier: unifier=self._unifier
        if not unifier:
            msg = "Missing FactBaseBuilder unifier specification in function call " + \
                "(no default was given at model instantiation)"
            raise ValueError(msg)

        return unifier.new(
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
        if isinstance(fact, NonLogicalSymbol):
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
        ignore=[]
        for key,value in OSolveHandle.__dict__.items():
            if key in ignore: continue
            if key.startswith("_"): continue
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
        self._unifier = unifier

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
        ignore=["assign_external", "release_external", "solve"]
        for key,value in OControl.__dict__.items():
            if key in ignore: continue
            if key.startswith("_"): continue
            if callable(value):
                dct[key]=_control_wrapper(value)
            else:
                dct[key]=_control_property(key)

        return super(_ControlMetaClass, meta).__new__(meta, name, bases, dct)


class Control(object, metaclass=_ControlMetaClass):
    '''Control object for the grounding/solving process.

    Behaves like ``clingo.Control`` but with modifications to deal with Clorm
    facts and fact bases.

    Adds an additional parameter ``unifier`` to specify how any generated clingo
    models will be unified with the clorm Predicate definitions. The unifier can
    be specified as a list of predicates or as a FactBaseBuilder object.

    An existing ``clingo.Control`` object can be passed using the ``control_``
    parameter.

    '''

    def __init__(self, *args, **kwargs):
        self._unifier = None
        if len(args) == 0 and "control_" in kwargs:
            self._ctrl = kwargs["control_"]
            if "unifier" in kwargs:
                unifier = kwargs["unifier"]
                if not isinstance(unifier, FactBaseBuilder):
                    unifier=FactBaseBuilder(predicates=unifier)
                self._unifier = unifier
        else:
            # Remove unifier from the arguments that are passed to clingo.Control()
            if "unifier" in kwargs:
                self._unifier = kwargs["unifier"]
                kwargs2 = dict(kwargs)
                del kwargs2["unifier"]
                self._ctrl = OControl(*args, **kwargs2)
            else:
                self._ctrl = OControl(*args, **kwargs)

    #------------------------------------------------------------------------------
    # Return the underlying control object
    #------------------------------------------------------------------------------
    @property
    def control_(self):
        '''Returns the underlying clingo.Control object.'''
        return self._ctrl

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
    # Overide assign_external to deal with NonLogicalSymbol object and a Clingo Symbol
    #------------------------------------------------------------------------------
    def assign_external(self, fact, truth):
        '''Assign a truth value to an external atom (represented as a function symbol
        or program literam or a clorm fact.

        This function extends ``clingo.Control.release_external``.

        '''
        if isinstance(fact, NonLogicalSymbol):
            self._ctrl.assign_external(fact.raw, truth)
        else:
            self._ctrl.assign_external(fact, truth)

    #------------------------------------------------------------------------------
    # Overide release_external to deal with NonLogicalSymbol object and a Clingo Symbol
    #------------------------------------------------------------------------------
    def release_external(self, fact):
        '''Release an external atom represented by the given symbol, program literal, or
        clorm fact.

        This function extends ``clingo.Control.release_external``.

        '''
        if isinstance(fact, NonLogicalSymbol):
            self._ctrl.release_external(fact.raw)
        else:
            self._ctrl.release_external(fact)

    #---------------------------------------------------------------------------
    # Overide solve and if necessary replace on_model with a wrapper that
    # returns a clorm.Model object. Also because of the issue with using the
    # keyword "async" as a parameter in Python 3.7 (which means that newer
    # clingo version use "async_") we use a more complicated way to determine
    # the function parameters.
    #---------------------------------------------------------------------------
    def solve(self, **kwargs):
        '''Run the clingo solver.

        This function extends ``clingo.Control.solve`` to take assumptions that
        are facts or a fact base, and return clorm.clingo.SolveHandle and
        clorm.clingo.Model objects.

        '''

        # validargs stores the valid arguments and their default values
        validargs = { "assumptions": [], "on_model" : None,
                        "on_finish": None, "yield_" : False }

        # Use "async" or "async_" depending on clingo version. Note: "async" is
        # a keyword for Python 3.7+.
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

        # check and process if we have a assumption pair or single literal
        def _process_assumption(a):
            if isinstance(a[0], NonLogicalSymbol): return (a[0].raw, a[1])
            return a

        # generate a new assumptions list if necesary
        assumptions = kwargs["assumptions"]
        if isinstance(assumptions, FactBase):
            kwargs["assumptions"] = [(f.raw, True) for f in assumptions.facts()]
        else:
            kwargs["assumptions"] = [_process_assumption(a) for a in assumptions]

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

