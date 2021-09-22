# -----------------------------------------------------------------------------
# Functions and classes to help with converting symbols to facts and
# vice-versa. This includes the unification process of unifying a set of symbols
# to matching predicate signatures as well as more high-level tasks such as
# asserting a set of facts into the solver (ie. clingo backend)
#
# Also includes SymbolPredicateUnifier and unify function
# implementation. Although should refactor SymbolPredicateUnifier to something
# less heavy handed.
# ------------------------------------------------------------------------------

import itertools
import clingo
from .core import *
from .factbase import *
from .core import get_field_definition, PredicatePath, kwargs_check_keys


__all__ = [
    'SymbolPredicateUnifier',
    'unify',
    'control_add_facts',
    'symbolic_atoms_to_facts'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# A fact generator that takes a list of predicates to unify against (order
# matters) and a set of raw clingo symbols against this list.
# ------------------------------------------------------------------------------

def _unify(predicates, symbols):
    def unify_single(cls, r):
        try:
            return cls._unify(r)
        except ValueError:
            return None

    # To make things a little more efficient use the name/arity signature as a
    # filter. However, Python doesn't have a built in multidict class, and I
    # don't want to add a dependency to an external library just for one small
    # feature, so implement a simple structure here.
    sigs = [((cls.meta.name, len(cls.meta)),cls) for cls in predicates]
    types = {}
    for sig,cls in sigs:
        if sig not in types: types[sig] = [cls]
        else: types[sig].append(cls)

    # Loop through symbols and yield when we have a match
    for raw in symbols:
        classes = types.get((raw.name, len(raw.arguments)))
        if not classes: continue
        for cls in classes:
            f = unify_single(cls,raw)
            if f is not None:
                yield f
                break


#------------------------------------------------------------------------------
# SymbolPredicateUnifier offers a decorator interface for gathering predicate and index
# definitions to be used in defining a FactBase subclass.
# ------------------------------------------------------------------------------
class SymbolPredicateUnifier(object):
    """A fact base builder simplifies the task of unifying raw clingo.Symbol objects
    with Clorm predicates. Predicates classes are registered using the
    'register' function (which can be called as a normal function or as a class
    decorator.
    """

    def __init__(self, predicates=[], indexes=[], suppress_auto_index=False):
        self._predicates = ()
        self._indexes = ()
        self._suppress_auto_index = suppress_auto_index
        tmppreds = []
        tmpinds = []
        tmppredset = set()
        tmpindset = set()
        for pred in predicates:
                self._register_predicate(pred,tmppreds,tmpinds,tmppredset,tmpindset)
        for fld in indexes:
                self._register_index(fld,tmppreds,tmpinds,tmppredset,tmpindset)
        self._predicates = tuple(tmppreds)
        self._indexes = tuple(tmpinds)

    def _register_predicate(self, cls, predicates, indexes, predicateset, indexset):
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        if cls in predicateset: return
        predicates.append(cls)
        predicateset.add(cls)
        if self._suppress_auto_index: return

        # Add all fields (and sub-fields) that are specified as indexed
        for fp in cls.meta.indexes:
            self._register_index(fp,predicates,indexes,predicateset,indexset)

    def _register_index(self, path, predicates, indexes, predicateset, indexset):
        if path.meta.hashable in indexset: return
        if isinstance(path, PredicatePath) and path.meta.predicate in predicateset:
            indexset.add(path.meta.hashable)
            indexes.append(path)
        else:
            raise TypeError("{} is not a predicate field for one of {}".format(
                path, [ p.__name__ for p in predicates ]))

    def register(self, cls):
        if cls in self._predicates: return cls
        predicates = list(self._predicates)
        indexes = list(self._indexes)
        tmppredset = set(self._predicates)
        tmpindset = set([p.meta.hashable for p in self._indexes])
        self._register_predicate(cls,predicates,indexes,tmppredset,tmpindset)
        self._predicates = tuple(predicates)
        self._indexes = tuple(indexes)
        return cls

    def unify(self, symbols, delayed_init=False, raise_on_empty=False):
        def _populate():
            facts=list(_unify(self.predicates, symbols))
            if not facts and raise_on_empty:
                raise ValueError("FactBase creation: failed to unify any symbols")
            return facts

        if delayed_init:
            return FactBase(facts=_populate, indexes=self._indexes)
        else:
            return FactBase(facts=_populate(), indexes=self._indexes)

    @property
    def predicates(self): return self._predicates
    @property
    def indexes(self): return self._indexes

#------------------------------------------------------------------------------
# Generate facts from an input array of Symbols.  The `unifier` argument takes a
# list of predicate classes or a SymbolPredicateUnifer object to unify against
# the symbol object contained in `symbols`.
# ------------------------------------------------------------------------------

def unify(unifier,symbols,ordered=False):
    '''Unify raw symbols against a list of predicates or a SymbolPredicateUnifier.

    Symbols are tested against each predicate unifier until a match is
    found. Since it is possible to define multiple predicate types that can
    unify with the same symbol, the order of the predicates in the unifier
    matters. With the `ordered` option set to `True` a list is returned that
    preserves the order of the input symbols.

    Args:
      unifier: a list of predicate classes or a SymbolPredicateUnifier object.
      symbols: the symbols to unify.
      ordered (default: False): optional to return a list rather than a FactBase.
    Return:
      a FactBase containing the unified facts, indexed by any specified indexes,
         or a list if the ordered option is specified

    '''
    if not unifier:
        raise ValueError(("The unifier must be a list of predicates "
                          "or a SymbolPredicateUnifier"))
    if ordered:
        if isinstance(unifier, SymbolPredicateUnifier):
            unifier=unifier.predicates
        return list(_unify(unifier,symbols))
    else:
        if not isinstance(unifier, SymbolPredicateUnifier):
            unifier=SymbolPredicateUnifier(predicates=unifier)
        return unifier.unify(symbols)

#------------------------------------------------------------------------------
# Function to add a collection of facts to the solver backend
#------------------------------------------------------------------------------

if clingo.__version__ >= "5.5.0":

    from clingo.ast import parse_string

    def control_add_facts(ctrl, facts):
        with ctrl.backend() as bknd:
            for f in facts:
                raw=f.raw if isinstance(f,Predicate) else f
                atm = bknd.add_atom(raw)
                bknd.add_rule([atm])
else:
    from clingo import parse_program

    def control_add_facts(ctrl, facts):
        with ctrl.builder() as bldr:
            line=1
            for f in facts:
                raw=f.raw if isinstance(f,Predicate) else f
                floc = { "filename" : "<input>", "line" : line , "column" : 1 }
                location = { "begin" : floc, "end" : floc }
                r = ast.Rule(location,
                             ast.Literal(location, ast.Sign.NoSign,
                                         ast.SymbolicAtom(ast.Symbol(location,raw))),
                             [])
                bldr.add(r)
                line += 1

control_add_facts.__doc__ = '''Assert a collection of facts to the solver

    Provides a flexible approach to asserting facts to the solver. The facts can
    be either `clingo.Symbol` objects or clorm facts and can be in any type of
    be in any collection (including a `clorm.FactBase`).

    Args:
        ctrl: a `clingo.Control` object
        facts: the collection of facts to be asserted into the solver
'''

# ------------------------------------------------------------------------------
# Function to take a SymbolicAtoms object and extract facts from it
# ------------------------------------------------------------------------------

def symbolic_atoms_to_facts(symbolic_atoms, unifier, *,
                            facts_only=False, factbase=None):
    '''Extract `clorm.FactBase` from `clingo.SymbolicAtoms`

    A `clingo.SymbolicAtoms` object is returned from the
    `clingo.Control.symbolic_atoms` property. This property is a view into the
    internal atoms within the solver and can be examined at anytime
    (ie. before/after the grounding/solving). Some of the atoms are trivially
    true (as determined by the grounder) while others may only be true in some
    models.

    Args:
        symbolic_atoms: a `clingo.SymbolicAtoms` object
        unifier: a list of Clorm Predicate sub-classes to unify against
        facts_only (default False): return facts only or include contingent literals
        factbase (default None): add to existing FactBase or return a new FactBase
    '''

    if factbase is None: factbase=FactBase()

    def group_predicates():
        groups = {}
        for pcls in unifier:
            groups.setdefault((pcls.meta.name,pcls.meta.arity),[]).append(pcls)
        return groups

    def single(cls,sym):
        try:
            factbase.add(cls._unify(sym))
            return True
        except ValueError:
            return False

    groups = group_predicates()
    for (name,arity), mpredicates in groups.items():
        for symatom in itertools.chain(
                symbolic_atoms.by_signature(name,arity,True),
                symbolic_atoms.by_signature(name,arity,False)):
            if facts_only and not symatom.is_fact: continue
            for pcls in mpredicates:
                if single(pcls,symatom.symbol): continue
    return factbase

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
