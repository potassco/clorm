#-----------------------------------------------------------------------------
# Monkey patching Clingo (or at least wrapping the Clingo objects).
# ------------------------------------------------------------------------------

import clingo
import functools
import clorm as orm

__version__ = '0.1.0'
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
        return orm.model_facts(self._model, unifiers, atoms=atoms, terms=terms,shown=shown)

    # Overide contains
    def contains(self, fact):
        return orm.model_contains(self._model, fact)


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
        orm.control_add_facts(self._ctrl, factbase)

    # Overide assign_external
    def assign_external(self, fact, truth):
        orm.control_assign_external(self._ctrl, fact, truth)

    # Overide release_external
    def release_external(ctrl, fact):
        orm.control_release_external(self._ctrl, fact)

    # Overide solve and call on_model with a replace Model object
    def solve(self, *, assumptions=[], on_model=None, on_finish=None,
              yield_=False, async_=False):

        new_a = [ (f.symbol if isinstance(f, NonLogicalSymbol) \
                    else f, b) for f,b in assumptions ]

        @functools.wraps(on_model)
        def on_model_wrapper(model):
            return on_model(Model(model))
        new_om = on_model_wrapper if on_model else None
        if yield_:
            sh = self._ctrl.solve(assumptions=new_a, on_model=new_om,
                                  on_finish=on_finish,
                                  yield_=yield_, async_=async_)
            return SolveHandle(sh)
        else:
            return self._ctrl.solve(assumptions=new_a, on_model=new_om,
                                    on_finish=on_finish,
                                    yield_=yield_, async_=async_)

#------------------------------------------------------------------------------
# Now patch the clingo objects
#------------------------------------------------------------------------------

def replace_control():
    clingo.Control=Control

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

