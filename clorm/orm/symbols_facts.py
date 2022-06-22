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
import sys
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Type, TypeVar, Union, cast, overload
from collections import defaultdict

import clingo
import clingo.ast as clast
from .core import *
from .noclingo import SymbolMode, Function, Number, String
from .factbase import *
from .core import AnySymbol, PredicatePath, get_symbol_mode

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

__all__ = [
    'SymbolPredicateUnifier',
    'unify',
    'control_add_facts',
    'symbolic_atoms_to_facts',
    'parse_fact_string',
    'parse_fact_files',
    'UnifierNoMatchError',
    'FactParserError',
    'Unifier'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
_PredicateGroups = Dict[Tuple[int, str], List[Type[Predicate]]]
_P = TypeVar("_P", bound=Predicate)

#------------------------------------------------------------------------------
# Clorm exception subclasses
#------------------------------------------------------------------------------

class UnifierNoMatchError(ClormError):
    def __init__(self,message, symbol, predicates):
        super().__init__(message)
        self._symbol=symbol
        self._predicates=predicates
    @property
    def symbol(self): return self._symbol
    @property
    def predicates(self): return self._predicates

class FactParserError(ClormError):
    def __init__(self,message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(message)

#------------------------------------------------------------------------------
# A unifier takes a list of predicates to unify against (order matters) and a
# set of raw clingo symbols against this list. Implementation detail: maintain
# a lookup of predicates that is determined first by arity and then by name.
# ------------------------------------------------------------------------------

class Unifier(object):
    def __init__(self,predicates: Iterable[Type[Predicate]]) -> None:
        self._predicates=tuple(predicates)
        self._pgroups: _PredicateGroups = defaultdict(list)
        self._add_predicates(predicates)

    def _add_predicates(self,predicates: Iterable[Type[Predicate]]) -> None:
        for p in predicates:
            self._pgroups[(p.meta.arity,p.meta.name)].append(p)

    def add_predicate(self,predicate: Type[Predicate]) -> None:
        self._add_predicates([predicate])

    def iter_unify(self, symbols: Iterable[AnySymbol], raise_nomatch: bool) -> Iterator[Predicate]:
        known_names = set([name for _, name in self._pgroups.keys()])
        for sym in symbols:
            sym_name = sym.name
            instance = None
            if sym_name in known_names:
                sym_args = sym.arguments
                for pred in self._pgroups[(len(sym_args),sym_name)]:
                    instance = pred._unify(sym, sym_args, sym_name)
                    if instance is not None:
                        yield instance
                        break
            if raise_nomatch and instance is None:
                raise UnifierNoMatchError(
                    f"Cannot unify symbol '{sym}' to predicates in {self._predicates}",
                    sym, self._predicates)

    def unify_symbol(self, sym: AnySymbol, *, raise_nomatch: bool=False) -> Optional[Predicate]:
        return next(self.iter_unify([sym], raise_nomatch), None)

    def unify(self, symbols: Iterable[AnySymbol], *, factbase: Optional[FactBase]=None, raise_nomatch: bool=False) -> FactBase:
        fb=FactBase() if factbase is None else factbase
        fb.add(list(self.iter_unify(symbols, raise_nomatch)))
        return fb

#------------------------------------------------------------------------------
# A fact generator that takes a list of predicates to unify against (order
# matters) and a set of raw clingo symbols against this list.
# ------------------------------------------------------------------------------

def _unify(predicates: Iterable[Type[Predicate]], symbols: Iterable[AnySymbol]) -> Iterator[Predicate]:
    return Unifier(predicates).iter_unify(symbols, raise_nomatch=False)


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

    def __init__(self,
                 predicates: Iterable[Type[Predicate]] = [],
                 indexes: Iterable[PredicatePath] = [],
                 suppress_auto_index: bool = False) -> None:
        self._suppress_auto_index = suppress_auto_index
        tmppreds: List[Type[Predicate]] = []
        tmpinds: List[PredicatePath] = []
        tmppredset: Set[Type[Predicate]] = set()
        tmpindset: Set[PredicatePath.Hashable] = set()
        for pred in predicates:
                self._register_predicate(pred,tmppreds,tmpinds,tmppredset,tmpindset)
        for fld in indexes:
                self._register_index(fld,tmppreds,tmpinds,tmppredset,tmpindset)
        self._predicates = tuple(tmppreds)
        self._indexes = tuple(tmpinds)

    def _register_predicate(self,
                            cls: Type[Predicate],
                            predicates: List[Type[Predicate]],
                            indexes: List[PredicatePath],
                            predicateset: Set[Type[Predicate]],
                            indexset: Set[PredicatePath.Hashable]) -> None:
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        if cls in predicateset: return
        predicates.append(cls)
        predicateset.add(cls)
        if self._suppress_auto_index: return

        # Add all fields (and sub-fields) that are specified as indexed
        for fp in cls.meta.indexes:
            self._register_index(fp,predicates,indexes,predicateset,indexset)

    def _register_index(self,
                        path: PredicatePath,
                        predicates: Iterable[Type[Predicate]],
                        indexes: List[PredicatePath],
                        predicateset: Set[Type[Predicate]],
                        indexset: Set[PredicatePath.Hashable]) -> None:
        if path.meta.hashable in indexset: return
        if isinstance(path, PredicatePath) and path.meta.predicate in predicateset:
            indexset.add(path.meta.hashable)
            indexes.append(path)
        else:
            raise TypeError("{} is not a predicate field for one of {}".format(
                path, [ p.__name__ for p in predicates ]))

    def register(self, cls: Type[_P])-> Type[_P]:
        if cls in self._predicates: return cls
        predicates = list(self._predicates)
        indexes = list(self._indexes)
        tmppredset = set(self._predicates)
        tmpindset = set([p.meta.hashable for p in self._indexes])
        self._register_predicate(cls,predicates,indexes,tmppredset,tmpindset)
        self._predicates = tuple(predicates)
        self._indexes = tuple(indexes)
        return cls

    def unify(self,
              symbols: Iterable[AnySymbol],
              delayed_init: bool=False,
              raise_on_empty: bool=False) -> FactBase:
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

@overload
def unify(unifier: Union[Iterable[Type[Predicate]], SymbolPredicateUnifier],
          symbols: Iterable[AnySymbol],
          ordered: Literal[True]) -> List[Predicate]: ...


@overload
def unify(unifier: Union[Iterable[Type[Predicate]], SymbolPredicateUnifier],
          symbols: Iterable[AnySymbol]) -> FactBase: ...


def unify(unifier: Union[Iterable[Type[Predicate]], SymbolPredicateUnifier],
          symbols: Iterable[AnySymbol],
          ordered: bool=False) -> Union[FactBase, List[Predicate]]:
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
        predicates = unifier.predicates if isinstance(unifier, SymbolPredicateUnifier) else unifier
        return list(_unify(predicates, symbols))
    else:
        if not isinstance(unifier, SymbolPredicateUnifier):
            unifier=SymbolPredicateUnifier(predicates=unifier)
        return unifier.unify(symbols)

#------------------------------------------------------------------------------
# Function to add a collection of facts to the solver backend
#------------------------------------------------------------------------------

if clingo.__version__ >= "5.5.0":

    def control_add_facts(ctrl: clingo.Control, facts: Iterable[Union[Predicate, clingo.Symbol]]) -> None:
        with ctrl.backend() as bknd:
            for f in facts:
                raw=f.raw if isinstance(f,Predicate) else f
                atm = bknd.add_atom(raw)
                bknd.add_rule([atm])
else:
    import clingo.ast as ast

    def control_add_facts(ctrl: clingo.Control, facts: Iterable[Union[Predicate, clingo.Symbol]]) -> None:
        with ctrl.builder() as bldr:  # type: ignore[attr-defined]
            line=1
            for f in facts:
                raw=f.raw if isinstance(f,Predicate) else f
                floc = { "filename" : "<input>", "line" : line , "column" : 1 }
                location = { "begin" : floc, "end" : floc }
                r = ast.Rule(location,  # type: ignore[arg-type]
                             ast.Literal(location, ast.Sign.NoSign,  # type: ignore[arg-type]
                                         ast.SymbolicAtom(ast.Symbol(location,raw))),  # type: ignore
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

def symbolic_atoms_to_facts(symbolic_atoms: clingo.SymbolicAtoms,
                            unifier: Iterable[Type[Predicate]], *,
                            facts_only: bool = False,
                            factbase: Optional[FactBase] = None) -> FactBase:
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

    groups = group_predicates()
    for (name,arity), mpredicates in groups.items():
        for symatom in itertools.chain(
                symbolic_atoms.by_signature(name,arity,True),
                symbolic_atoms.by_signature(name,arity,False)):
            if facts_only and not symatom.is_fact: continue
            for pcls in mpredicates:
                instance = pcls._unify(symatom.symbol)
                if instance is None:
                    continue
                factbase.add(instance)
    return factbase


#------------------------------------------------------------------------------
# parse a string containing ASP facts into a factbase
#------------------------------------------------------------------------------

class ClingoParserWrapperError(Exception):
    """A special exception for returning from the clingo parser.

    I think the clingo parser is assuming all exceptions behave as if they have
    a copy constructor.

    """
    def __init__(self, arg):
        if type(arg) == type(self):
            self.exc = arg.exc
        else:
            self.exc = arg
        super().__init__()

#------------------------------------------------------------------------------
# Parse ASP facts from a string or files into a factbase
#------------------------------------------------------------------------------

from clingo.ast import AST, ASTType, ASTSequence

class NonFactVisitor:
    ERROR_AST = set({
        ASTType.Id,
        ASTType.Variable,
        ASTType.BinaryOperation,
        ASTType.Interval,
        ASTType.Pool,
        ASTType.BooleanConstant,
        ASTType.Comparison,
        getattr(ASTType, "Guard" if clingo.version() >= (5, 6, 0)
                         else "AggregateGuard"),
        ASTType.ConditionalLiteral,
        ASTType.Aggregate,
        ASTType.BodyAggregateElement,
        ASTType.BodyAggregate,
        ASTType.HeadAggregateElement,
        ASTType.HeadAggregate,
        ASTType.Disjunction,
        ASTType.TheorySequence,
        ASTType.TheoryFunction,
        ASTType.TheoryUnparsedTermElement,
        ASTType.TheoryUnparsedTerm,
        ASTType.TheoryGuard,
        ASTType.TheoryAtomElement,
        ASTType.TheoryAtom,
        ASTType.TheoryOperatorDefinition,
        ASTType.TheoryTermDefinition,
        ASTType.TheoryGuardDefinition,
        ASTType.TheoryAtomDefinition,
        ASTType.Definition,
        ASTType.ShowSignature,
        ASTType.ShowTerm,
        ASTType.Minimize,
        ASTType.Script,
        ASTType.External,
        ASTType.Edge,
        ASTType.Heuristic,
        ASTType.ProjectAtom,
        ASTType.ProjectSignature,
        ASTType.Defined,
        ASTType.TheoryDefinition})

    def __call__(self, stmt: AST) -> None:
        self._stmt = stmt
        self._visit(stmt)

    def _visit(self, ast: AST) -> None:
        '''
        Dispatch to a visit method.
        '''
        if (ast.ast_type in NonFactVisitor.ERROR_AST or
            (ast.ast_type == ASTType.Function and ast.external)):
            line = cast(clast.Location, ast.location).begin.line
            column = cast(clast.Location, ast.location).begin.column
            exc = FactParserError(message=f"Non-fact '{self._stmt}'",
                                  line=line, column=column)
            raise ClingoParserWrapperError(exc)

        for key in ast.child_keys:
            subast = getattr(ast, key)
            if isinstance(subast, ASTSequence):
                for x in subast:
                    self._visit(x)
            if isinstance(subast, AST):
                self._visit(subast)

def parse_fact_string(aspstr: str, unifier: Iterable[Type[Predicate]], *, factbase: Optional[FactBase] = None,
                      raise_nomatch: bool = False, raise_nonfact: bool = False) -> FactBase:
    '''Parse a string of ASP facts into a FactBase

    Facts must be of a simple form that can correspond to clorm predicate
    instances. Rules that are NOT simple facts include: any rule with a body, a
    disjunctive fact, a choice rule, a theory atom, a literal with an external
    @-function reference, a literal that requires some mathematical calculation
    (eg., "p(1+1).")

    NOTE: Currently, this function is not safe when running in NOCLINGO mode and
    will raise a NotImplementedError if called.

    Args:
      aspstr: an ASP string containing the facts
      factbase: if no factbase is specified then create a new one
      unifier: a list of clorm.Predicate classes to unify against
      raise_nomatch: raise UnifierNoMatchError on a fact that cannot unify
      raise_nonfact: raise FactParserError on any non simple fact (eg. complex rules)

    '''

    if get_symbol_mode() == SymbolMode.NOCLINGO:
        if not raise_nonfact:
            raise NotImplementedError("Non-fact parsing not supported in NOCLINGO mode")
        return lark_parse_fact_string(aspstr=aspstr, unifier=unifier, factbase=factbase,
                                      raise_nomatch=raise_nomatch)

    ctrl = clingo.Control()
    un=Unifier(unifier)
    try:
        if raise_nonfact:
            with clast.ProgramBuilder(ctrl) as bld:
                nfv = NonFactVisitor()
                def on_rule(ast: AST) -> None:
                    nonlocal nfv, bld
                    if nfv: nfv(ast)
                    bld.add(ast)
                clast.parse_string(aspstr, on_rule)
        else:
            ctrl.add("base", [], aspstr)

    except ClingoParserWrapperError as e:
        raise e.exc

    ctrl.ground([("base",[])])

    return un.unify([sa.symbol for sa in ctrl.symbolic_atoms if sa.is_fact],
                    factbase=factbase, raise_nomatch=raise_nomatch)




def parse_fact_files(files: Sequence[str], unifier: Iterable[Type[Predicate]], *, factbase: Optional[FactBase] = None,
                     raise_nomatch: bool = False, raise_nonfact: bool = False) -> FactBase:
    '''Parse the facts from a list of files into a FactBase

    Facts must be of a simple form that can correspond to clorm predicate
    instances. Rules that are NOT simple facts include: any rule with a body, a
    disjunctive fact, a choice rule, a theory atom, a literal with an external
    @-function reference, a literal that requires some mathematical calculation
    (eg., "p(1+1).")

    NOTE: Currently, this function is not safe when running in NOCLINGO mode and
    will raise a NotImplementedError if called.

    Args:
      files: a list of ASP files containing the facts
      factbase: if no factbase is specified then create a new one
      unifier: a list of clorm.Predicate classes to unify against
      raise_nomatch: raise UnifierNoMatchError on a fact that cannot unify
      raise_nonfact: raise FactParserError on any non simple fact (eg. complex rules)
    '''

    if get_symbol_mode() == SymbolMode.NOCLINGO:
        if not raise_nonfact:
            raise NotImplementedError("Non-fact parsing not supported in NOCLINGO mode")
        return lark_parse_fact_files(files=files, unifier=unifier, factbase=factbase,
                                      raise_nomatch=raise_nomatch)

    ctrl = clingo.Control()
    un=Unifier(unifier)
    try:
        if raise_nonfact:
            with clast.ProgramBuilder(ctrl) as bld:
                nfv = NonFactVisitor()
                def on_rule(ast: AST) -> None:
                    nonlocal nfv, bld
                    if nfv: nfv(ast)
                    bld.add(ast)
                clast.parse_files(files, on_rule)
        else:
            for fn in files:
                ctrl.load(fn)
    except ClingoParserWrapperError as e:
        raise e.exc

    ctrl.ground([("base",[])])
    return un.unify([sa.symbol for sa in ctrl.symbolic_atoms if sa.is_fact],
                    factbase=factbase, raise_nomatch=raise_nomatch)

#------------------------------------------------------------------------------
#
# A pure-python fact parser that uses Lark
#------------------------------------------------------------------------------

from .lark_fact_parser import Lark_StandAlone, Transformer, LarkError, UnexpectedInput

class _END:
    pass

class _NEGATE:
    pass

END = _END()
NEGATE = _NEGATE()

class LarkFactTransformer(Transformer):
    def STRING(self, v):
        return String(v.value.strip("\""))
    def END(self, v):
        return END
    def NEGATE(self, v):
        return NEGATE
    def NAME(self, v):
        return str(v.value)
    def NUMBER(self, v):
        return Number(int(v))
    def function(self, v):
        if v[0] == NEGATE:
            positive = False
            v.pop(0)
        else:
            positive = True
        args = [] if len(v) == 1 else v[1]
        return Function(v[0],args,positive=positive)
    def fact(self, f):
        return f[0]
    def args(self,v):
        return v
    def tuple(self, v):
        return Function("",v[0])
    def start(self, v):
        return v

def lark_parse_fact_string(aspstr: str, unifier: Iterable[Type[Predicate]], *,
                           factbase: Optional[FactBase] = None, raise_nomatch: bool = False) -> FactBase:
    try:
        fact_parser = Lark_StandAlone(transformer=LarkFactTransformer())
        symbols =cast(List[clingo.Symbol], fact_parser.parse(aspstr))
        un = Unifier(unifier)
        return un.unify(symbols, factbase=factbase, raise_nomatch=raise_nomatch)
    except UnexpectedInput as e:
        raise FactParserError(str(e), line=e.line, column=e.column)
    except LarkError as e:
        raise FactParserError(str(e), line=0, column=0)

def lark_parse_fact_files(files: Iterable[str], unifier: Iterable[Type[Predicate]], *,
                          factbase: Optional[FactBase] = None, raise_nomatch: bool = False) -> FactBase:
    fb = FactBase() if factbase is None else factbase
    for fn in files:
        with open(fn, 'r') as file:
            aspstr = file.read()
            tmpfb = lark_parse_fact_string(aspstr=aspstr, unifier=unifier,
                                           factbase=fb,
                                           raise_nomatch=raise_nomatch)
    return fb

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
