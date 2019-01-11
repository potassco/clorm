#-----------------------------------------------------------------------------
# Monkey patching Clingo (or at least wrapping the Clingo objects).
# ------------------------------------------------------------------------------

import sys
import clingo
import functools
from .orm import *
#import clorm as orm

__all__ = [
    'Control',
    'Model',
    'SolveHandle'
    ]

# Reference to the original clingo objects so that when we replace them our
# references point to the originals.
OModel=clingo.Model
OSolveHandle=clingo.SolveHandle
OControl=clingo.Control

# ------------------------------------------------------------------------------
# Wrap clingo.Model and override some functions
# ------------------------------------------------------------------------------
def _model_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._model, *args, **kwargs)
    return wrapper

class _ModelMetaClass(type):
    def __new__(meta, name, bases, dct):
        overrides=["contains"]
        for key,value in OModel.__dict__.items():
            if key not in overrides and callable(value):
                dct[key]=_model_wrapper(value)
        return super(_ModelMetaClass, meta).__new__(meta, name, bases, dct)

class Model(object, metaclass=_ModelMetaClass):
    def __init__(self, model):
        self._model = model

    # A new function to return a list of facts - similar to symbols
    def facts(self, unifiers, *, atoms=False, terms=False, shown=False):
        return model_facts(self._model, unifiers, atoms=atoms, terms=terms,shown=shown)

    # Overide contains
    def contains(self, fact):
        return model_contains(self._model, fact)


# ------------------------------------------------------------------------------
# Wrap clingo.SolveHandle and override some functions
# ------------------------------------------------------------------------------
def _solvehandle_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._handle, *args, **kwargs)
    return wrapper

class _SolveHandleMetaClass(type):
    def __new__(meta, name, bases, dct):
        overrides=["__init__", "__iter__", "__next__"]
        for key,value in OSolveHandle.__dict__.items():
            if key not in overrides and callable(value):
                dct[key]=_model_wrapper(value)
        return super(_SolveHandleMetaClass, meta).__new__(meta, name, bases, dct)

class SolveHandle(object, metaclass=_SolveHandleMetaClass):
    def __init__(self, handle):
        self._handle = handle

    def __iter__(self):
        for m in self._handle.__iter__():
            yield Model(m)

    def __next__(self):
        m = self._handle.__next__()
        return Model(m)

# ------------------------------------------------------------------------------
# Wrap clingo.Control and override some functions
# ------------------------------------------------------------------------------
def _control_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._ctrl, *args, **kwargs)
    return wrapper

class _ControlMetaClass(type):
    def __new__(meta, name, bases, dct):
        overrides=["__init__", "__new__", "assign_external", "release_external", "solve"]
        for key,value in OControl.__dict__.items():
            if key not in overrides and callable(value):
                dct[key]=_control_wrapper(value)
        return super(_ControlMetaClass, meta).__new__(meta, name, bases, dct)



class Control(object, metaclass=_ControlMetaClass):
    def __init__(self, *args, **kwargs):
        self._ctrl = OControl(*args, **kwargs)

    # A new function to add facts from a factbase
    def add_facts(self, factbase):
        control_add_facts(self._ctrl, factbase)

    # Overide assign_external
    def assign_external(self, fact, truth):
        control_assign_external(self._ctrl, fact, truth)

    # Overide release_external
    def release_external(ctrl, fact):
        control_release_external(self._ctrl, fact)

    # Overide solve and if necessary replace on_model with a wrapper that
    # returns a clorm.Model object. Also because of the issue with using the
    # keyword "async" as a parameter in Python 3.7 (which means that newer
    # clingo version use "async_") we use a more complicated way to determine
    # the function parameters.
    def solve(self, **kwargs):
        # validargs stores the valid arguments and their default values
        validargs = { "assumptions": [], "on_model" : None,
                        "on_finish": None, "yield_" : False }

        # Use "async" or "async_" depending on the python or clingo version
        if sys.version_info >= (3,7) or clingo.__version__ > '5.3.1':
            validargs["async_"] = False
        else:
            validargs["async"] = False

        # validate the arguments and assign any missing default values
        keys = set(kwargs.keys())
        validkeys = set(validargs.keys())
        if not keys.issubset(validkeys):
            diff = keys - validkeys
            msg = "solve() got an unexpected keyword argument '{}'".format(next(iter(diff)))
            raise TypeError(msg)
        for k,v in validargs.items():
            if k not in kwargs: kwargs[k]=v

        # generate a new assumptions list if necesary
        assumptions = kwargs["assumptions"]
        if isinstance(assumptions, FactBase):
            kwargs["assumptions"] = [f.symbol for f in assumptions.facts()]
        else:
            kwargs["assumptions"] = [ (f.symbol if isinstance(f, NonLogicalSymbol) \
                                       else f, b) for f,b in assumptions ]

        # generate a new on_model function if necessary
        on_model=kwargs["on_model"]
        @functools.wraps(on_model)
        def on_model_wrapper(model):
            return on_model(Model(model))
        if on_model: kwargs["on_model"] =  on_model_wrapper

        result = self._ctrl.solve(**kwargs)
        if kwargs["yield_"]:
            return SolveHandle(result)
        else:
            return result

#------------------------------------------------------------------------------
# Now patch the clingo objects
#------------------------------------------------------------------------------

def patch():
    clingo.Control=Control

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

