# -----------------------------------------------------------------------------
# Clorm ORM SymbolPredicateUnifier and unify function implementation. The
# provides the feature to get a list of raw clingo symbol objects and turn them
# into a FactBase.
# ------------------------------------------------------------------------------

from .core import *
from .factbase import *
from .core import get_field_definition, PredicatePath, kwargs_check_keys


__all__ = [
    'SymbolPredicateUnifier',
    'unify'
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
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
