"""
Extend clingo's Control, Model and SolveHandle classes to better use with clorm
"""

# TODO: For clorm v2.0 the raise_on_empty parameter in Model.facts() should be
#       moved to the second parameter position.

import functools
import itertools

import clingo as oclingo
from .util.wrapper import init_wrapper, make_class_wrapper
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Sequence, Tuple, Type, Union, cast, overload
from .orm import *

__all__ = ["ClormControl", "ClormModel", "ClormSolveHandle", "_expand_assumptions"]

OModel = oclingo.Model
OSolveHandle = oclingo.SolveHandle
OControl = oclingo.Control

# ------------------------------------------------------------------------------
# Helper function to smartly build a unifier if only a list of predicates have
# been provided.
# ------------------------------------------------------------------------------


_Unifier = Union[List[Type[Predicate]], SymbolPredicateUnifier]

def _build_unifier(unifier: Optional[_Unifier]) -> Optional[SymbolPredicateUnifier]:
    if unifier is None:
        return None
    if isinstance(unifier, SymbolPredicateUnifier):
        return unifier
    return SymbolPredicateUnifier(predicates=unifier)


# ------------------------------------------------------------------------------
# Helper function to test that an attribute exists and corresponds to a function.
# ------------------------------------------------------------------------------

def _check_is_func(obj: Any, name: str) -> None:
    if not callable(obj.__getattribute__(name)):
        raise AttributeError(("Wrapped object of type '{}' does not have "
                              "a function '{}()'").format(type(obj), name))


# ------------------------------------------------------------------------------
# Wrap clingo.Model and override some functions
# ------------------------------------------------------------------------------

# class Model(OModel, metaclass=WrapperMetaClass):
class ModelOverride(object):
    '''Provides access to a model during a solve call.

    Objects mustn't be created manually. Instead they are returned by
    ``clorm.clingo.Control.solve`` callbacks.

    Behaves like ``clingo.Model`` but offers better integration with clorm facts
    and fact bases.

    '''
    if TYPE_CHECKING:
        _wrapped: OModel  # will be set through init_wrapper

    def __init__(self, model: OModel, unifier: Optional[_Unifier] = None) -> None:
        self._unifier = _build_unifier(unifier)
        _check_is_func(model, "symbols")
        init_wrapper(self, wrapped_=model)

    # ------------------------------------------------------------------------------
    # Return the underlying model object
    # ------------------------------------------------------------------------------
    @property
    def model_(self) -> OModel:
        '''Returns the underlying clingo.Model object.'''
        return self._wrapped

    # ------------------------------------------------------------------------------
    # A new function to return a list of facts - similar to symbols
    # ------------------------------------------------------------------------------

    def facts(self, *args: Any, **kwargs: Any) -> FactBase:
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
        nargs = list(args)
        nkwargs = dict(kwargs)
        if len(nargs) >= 1 and "unifier" in nkwargs:
            raise TypeError("facts() got multiple values for argument 'unifier'")
        if len(nargs) >= 5 and "raise_on_empty" in nkwargs:
            raise TypeError("facts() got multiple values for argument 'raise_on_empty'")

        raise_on_empty = nkwargs.pop("raise_on_empty", False)
        if len(nargs) >= 5:
            raise_on_empty = nargs.pop(4)
        unifier = nkwargs.pop("unifier", None)
        if len(nargs) >= 1:
            unifier = nargs.pop(0)

        unifier_ = _build_unifier(unifier) if unifier is not None else self._unifier
        if unifier_ is None:
            msg = "Missing a predicate unifier specification in function call " + \
                "(no default was given at model instantiation)"
            raise ValueError(msg)

        return unifier_.unify(
            symbols=self.model_.symbols(*nargs, **nkwargs),
            raise_on_empty=raise_on_empty,
            delayed_init=True)

    # ------------------------------------------------------------------------------
    # Overide contains
    # ------------------------------------------------------------------------------

    def contains(self, fact: Union[Predicate, oclingo.Symbol]) -> bool:
        '''Return whether the fact or symbol is contained in the model. Extends
        ``clingo.Model.contains`` to allow for clorm facts as well as a clingo
        symbols.

        '''
        atom = fact.raw if isinstance(fact, Predicate) else fact
        return self.model_.contains(atom)



if TYPE_CHECKING:
    class ClormModel(ModelOverride, OModel):
        pass
else:
    ClormModel = make_class_wrapper(OModel, ModelOverride)

# ------------------------------------------------------------------------------
# Wrap clingo.SolveHandle and override some functions
# ------------------------------------------------------------------------------


# class SolveHandle(OSolveHandle, metaclass=WrapperMetaClass):
class SolveHandleOverride(object):
    '''Handle for solve calls.

    Objects mustn't be created manually. Instead they are returned by
    ``clorm.clingo.Control.solve``.

    Behaves like ``clingo.SolveHandle`` but iterates over ``clorm.clingo.Model``
    objects.

    '''
    if TYPE_CHECKING:
        _wrapped: OSolveHandle  # will be set through init_wrapper

    def __init__(self, handle: OSolveHandle, unifier: Optional[_Unifier] = None) -> None:
        init_wrapper(self, wrapped_=handle)
        self._unifier = _build_unifier(unifier)

    # ------------------------------------------------------------------------------
    # Return the underlying solvehandle object
    # ------------------------------------------------------------------------------
    @property
    def solvehandle_(self) -> OSolveHandle:
        '''Access the underlying clingo.SolveHandle object.'''
        return self._wrapped

    # ------------------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------------------

    def __iter__(self):
        for model in self.solvehandle_:
            yield ClormModel(model, unifier=self._unifier)

    def __enter__(self):
        self.solvehandle_.__enter__()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.solvehandle_.__exit__(exception_type, exception_value, traceback)
        return None


if TYPE_CHECKING:
    class ClormSolveHandle(SolveHandleOverride, OSolveHandle):
        pass
else:
    ClormSolveHandle = make_class_wrapper(OSolveHandle, SolveHandleOverride)


# ------------------------------------------------------------------------------
# Wrap clingo.Control and override some functions
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Helper functions to expand the assumptions list as part of a solve() call. The
# assumptions list is a list of argument-boolean pairs where the argument can be
# be a clingo symbol, or clorm predicate instance, or a collection of clingo
# symbols or clorm predicates. This needs to be expanded into a list of
# symbol-bool pairs.
# ------------------------------------------------------------------------------
def _expand_assumptions(assumptions: Iterable[Tuple[Union[Iterable[Union[Predicate, Symbol]],
                                                          Predicate, Symbol], bool]]) -> List[Tuple[Symbol, bool]]:
    pos_assump = set()
    neg_assump = set()

    def _add_fact(fact: Union[Predicate, Symbol], bval: bool) -> None:
        nonlocal pos_assump, neg_assump
        raw = fact.raw if isinstance(fact, Predicate) else fact
        if bval:
            pos_assump.add(raw)
        else:
            neg_assump.add(raw)

    try:
        for (arg, bval) in assumptions:
            if isinstance(arg, Predicate):
                _add_fact(arg, bval)
            elif isinstance(arg, Iterable):
                for f in arg:
                    _add_fact(cast(Union[Predicate, Symbol], f), bval)
            else:
                _add_fact(arg, bval)
    except (TypeError, ValueError) as e:
        raise TypeError(("Invalid solve assumptions. Expecting list of arg-bool "
                         "pairs (arg is a raw-symbol/predicate or a collection "
                         "of raw-symbols/predicates). Got: {}").format(assumptions))

    # Now returned a list of raw assumptions combining pos and neg
    pos = [(raw, True) for raw in pos_assump]
    neg = [(raw, False) for raw in neg_assump]
    return list(itertools.chain(pos, neg))

# ------------------------------------------------------------------------------
# Control class
# ------------------------------------------------------------------------------


# class Control(OControl, metaclass=WrapperMetaClass):
class ControlOverride(object):
    '''Control object for the grounding/solving process.

    Behaves like ``clingo.Control`` but with modifications to deal with Clorm
    facts and fact bases.

    Adds an additional parameter ``unifier`` to specify how any generated clingo
    models will be unified with the clorm Predicate definitions. The unifier can
    be specified as a list of predicates or as a SymbolPredicateUnifier object.

    An existing ``clingo.Control`` object can be passed using the ``control_``
    parameter.

    '''
    if TYPE_CHECKING:
        _wrapped: OControl  # will be set through init_wrapper

    @overload
    def __init__(self, arguments: Sequence[str] = [],
                 logger: Optional[oclingo.Logger] = None, message_limit: int = 20,
                 unifier: Optional[Union[List[Predicate], SymbolPredicateUnifier]] = None) -> None: ...

    @overload
    def __init__(self, control_: OControl) -> None: ...


    @overload
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._unifier = None
        if "unifier" in kwargs:
            self._unifier = _build_unifier(kwargs["unifier"])

        # Do we need to build a clingo.Control object or use an existing one. If
        # using existing one make sure the wrapped object has at least the
        # ground and solve functions.
        if len(args) == 0 and "control_" in kwargs:
            wrapped_ = kwargs["control_"]
            _check_is_func(wrapped_, "solve")
            _check_is_func(wrapped_, "ground")
            init_wrapper(self, wrapped_=wrapped_)
        else:
            kwargs2 = dict(kwargs)
            if "unifier" in kwargs2:
                del kwargs2["unifier"]
            init_wrapper(self, *args, **kwargs2)

    # ------------------------------------------------------------------------------
    # Return the underlying control object
    # ------------------------------------------------------------------------------
    @property
    def control_(self) -> OControl:
        '''Returns the underlying clingo.Control object.'''
        return self._wrapped

    # ------------------------------------------------------------------------------
    # Make the unifier a property with a getter and setter
    # ------------------------------------------------------------------------------
    @property
    def unifier(self) -> Optional[SymbolPredicateUnifier]:
        """Get/set the unifier.

        Unifier can be specified as a SymbolPredicateUnifier or a collection of
        Predicates. Always returns a SymbolPredicateUnifier (or None).

        """
        return self._unifier

    @unifier.setter
    def unifier(self, unifier: _Unifier) -> None:
        self._unifier = _build_unifier(unifier)

    # ------------------------------------------------------------------------------
    # A new function to add facts from a factbase or a list of facts
    # ------------------------------------------------------------------------------
    def add_facts(self, facts: Iterable[Union[Predicate, Symbol]]) -> None:
        '''Add facts to the control object. Note: facts must be added before grounding.

           This function can take an arbitrary collection containing a mixture
           of ``clorm.Predicate`` and ``clingo.Symbol`` objects. A
           ``clorm.FactBase`` is also a valid collection but it can only contain
           ``clorm.Predicate`` instances.

        Args:
          facts: a collection of ``clorm.Predicate`` or ``clingo.Symbol`` objects

        '''
        control_add_facts(self.control_, facts)

    # ------------------------------------------------------------------------------
    # Overide assign_external to deal with Predicate object and a Clingo Symbol
    # ------------------------------------------------------------------------------
    def assign_external(self, external: Iterable[Union[Predicate, oclingo.Symbol, int]], truth: Optional[bool]) -> None:
        '''Assign a truth value to an external fact (or collection of facts)

        A fact can be a raw clingo.Symbol object, a clorm.Predicate instance, or
        a program literal (an int). If the external is a collection then the
        truth value is assigned to all elements in the collection.

        This function extends ``clingo.Control.release_external``.

        '''
        def _assign_fact(fact: Union[Predicate, oclingo.Symbol, int]) -> None:
            if isinstance(fact, Predicate):
                self.control_.assign_external(fact.raw, truth)
            else:
                self.control_.assign_external(fact, truth)

        if isinstance(external, Iterable):
            for f in external:
                _assign_fact(f)
        else:
            _assign_fact(external)

    # ------------------------------------------------------------------------------
    # Overide release_external to deal with Predicate object and a Clingo Symbol
    # ------------------------------------------------------------------------------
    def release_external(self, external: Iterable[Union[Predicate, oclingo.Symbol, int]]) -> None:
        '''Release an external fact (or collection of facts)

        A fact can be a raw clingo.Symbol object, a clorm.Predicate instance, or
        a program literal (an int). If the external is a collection then the
        truth value is assigned to all elements in the collection.

        This function extends ``clingo.Control.release_external``.

        '''
        def _release_fact(fact: Union[Predicate, oclingo.Symbol, int]) -> None:
            if isinstance(fact, Predicate):
                self.control_.release_external(fact.raw)
            else:
                self.control_.release_external(fact)

        if isinstance(external, Iterable):
            for f in external:
                _release_fact(f)
        else:
            _release_fact(external)

    # ---------------------------------------------------------------------------
    # Overide solve and if necessary replace on_model with a wrapper that
    # returns a clorm.Model object. Also because of the issue with using the
    # keyword "async" as a parameter in Python 3.7 (which forced clingo 5.3.1+
    # to switch to using "async_") we have to use a complicated way to work out
    # function parameters. At some point will drop support for older clingo and
    # can simplify this function.
    # ---------------------------------------------------------------------------
    def solve(self, *args: Any, **kwargs: Any) -> Union[ClormSolveHandle, oclingo.SolveResult]:
        '''Run the clingo solver.

        This function extends ``clingo.Control.solve()`` in two ways:

        1) The ``assumptions`` argument is generalised so that in the list of
        argument-boolean pairs the argument can be be a clingo symbol, or clorm
        predicate instance, or a collection of clingo symbols or clorm
        predicates.

        2) It produces either a ``clorm.clingo.SolveHandle`` wrapper object or a
        ``clorm.clingo.Model`` wrapper objects as appropriate (depending on the
        ``yield_``, ``async_``, and ``on_model`` parameters).

        '''

        # Build the list of valid arguments; using the correct "async" or
        # "async_" parameter based on the clingo version.  Note: "async" is a
        # keyword for Python 3.7+.
        async_keyword = "async_" if oclingo.__version__ > '5.3.1' else "async"

        posnargs = ["assumptions", "on_model", "on_statistics",
                    "on_finish", "yield_", async_keyword]
        validargs = set(posnargs)

        # translate all positional arguments into keyword arguments.
        if len(args) > len(posnargs):
            raise TypeError(("solve() takes {} positional arguments but {}"
                             "were given").format(len(posnargs), len(args)))
        nkwargs = {posnargs[idx]: arg for idx, arg in enumerate(args)}

        for k, v in kwargs.items():
            if k not in validargs:
                raise TypeError(("solve() got an unexpected keyword "
                                 "argument '{}'").format(k))
            if k in nkwargs:
                raise TypeError(("solve() got multiple values for "
                                 "argument '{}'").format(k))
            nkwargs[k] = v

        # generate a new assumptions list if necesary
        if "assumptions" in nkwargs and nkwargs["assumptions"] is not None:
            nkwargs["assumptions"] = _expand_assumptions(nkwargs["assumptions"])

        # generate a new on_model function if necessary
        if "on_model" in nkwargs and nkwargs["on_model"] is not None:
            on_model = nkwargs["on_model"]

            @functools.wraps(on_model)
            def on_model_wrapper(model):
                return on_model(ClormModel(model, self.unifier))
            nkwargs["on_model"] = on_model_wrapper

        # Call the wrapped solve function and handle the return value
        # appropriately
        result = self.control_.solve(**nkwargs)
        if ("yield_" in nkwargs and nkwargs["yield_"]) or \
           (async_keyword in nkwargs and nkwargs[async_keyword]):
            return ClormSolveHandle(cast(OSolveHandle, result), unifier=self._unifier)
        else:
            return cast(oclingo.SolveResult, result)

    def __getattr__(self, attr):
        return getattr(self.control_, attr)


if TYPE_CHECKING:
    class ClormControl(ControlOverride, OControl):  # type: ignore
        pass
else:
    ClormControl = make_class_wrapper(OControl, ControlOverride)

# ------------------------------------------------------------------------------
# This is probably bad practice... Modify the original clingo docstrings so that
# when I generate the autodoc with clingo being mocked it installs a reference
# to the original clingo docs.
#
# UPDATE: I'm confused what the autodoc mocking is doing (or not doing). I'm
# sure I had it working but now seems to be failing. Adding more hacks :(
# ------------------------------------------------------------------------------

ClormControl.__doc__ += OControl.__doc__  # type: ignore
ClormControl.assign_external.__doc__ += OControl.assign_external.__doc__  # type: ignore
ClormControl.release_external.__doc__ += OControl.release_external.__doc__  # type: ignore
ClormControl.solve.__doc__ += OControl.solve.__doc__  # type: ignore
ClormModel.__doc__ += OModel.__doc__  # type: ignore
ClormModel.contains.__doc__ += OModel.contains.__doc__  # type: ignore
ClormSolveHandle.__doc__ += OSolveHandle.__doc__  # type: ignore

# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
