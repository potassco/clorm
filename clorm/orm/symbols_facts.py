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
from typing import Any, Union
from collections import abc

import clingo
import clingo.ast as clast
from .core import *
from .noclingo import SymbolMode
from .factbase import *
from .core import get_field_definition, PredicatePath, kwargs_check_keys, \
    get_symbol_mode


__all__ = [
    'SymbolPredicateUnifier',
    'unify',
    'control_add_facts',
    'symbolic_atoms_to_facts',
    'parse_fact_string',
    'parse_fact_files',
    'UnifierNoMatchError',
    'FactParserError'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------

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
# set of raw clingo symbols against this list.
# ------------------------------------------------------------------------------

class Unifier(object):
    def __init__(self,predicates=[]):
        self._predicates=tuple(predicates)
        self._pgroups = {}
        self._add_predicates(predicates)

    def _add_predicates(self,predicates=[]):
        for p in predicates:
            self._pgroups.setdefault((p.meta.name,p.meta.arity),[]).append(p)

    def add_predicate(self,predicate):
        self._add_predicates([predicates])

    def unify_symbol(self,sym,*,raise_nomatch=False):
        mpredicates = self._pgroups.get((sym.name,len(sym.arguments)),[])
        for pred in mpredicates:
            try:
                return pred._unify(sym)
            except ValueError:
                pass
        if raise_nomatch:
            raise UnifierNoMatchError(
                f"Cannot unify symbol '{sym}' to predicates in {self._predicates}",
                sym, self._predicates)
        return None

    def unify(self,symbols,*,factbase=None,raise_nomatch=False):
        fb=FactBase() if factbase is None else factbase
        for sym in symbols:
            matched = False
            mpredicates = self._pgroups.get((sym.name,len(sym.arguments)),[])
            for pred in mpredicates:
                try:
                    fb.add(pred(raw=sym))
                    matched = True
                    break
                except ValueError:
                    pass
            if not matched and raise_nomatch:
                raise UnifierNoMatchError(
                    f"Cannot unify symbol '{sym}' to predicates in {self._predicates}",
                    sym, self._predicates)
        return fb

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

    def control_add_facts(ctrl, facts):
        with ctrl.backend() as bknd:
            for f in facts:
                raw=f.raw if isinstance(f,Predicate) else f
                atm = bknd.add_atom(raw)
                bknd.add_rule([atm])
else:
    import clingo.ast as ast

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
        ASTType.CspProduct,
        ASTType.CspSum,
        ASTType.CspGuard,
        ASTType.BooleanConstant,
        ASTType.Comparison,
        ASTType.CspLiteral,
        ASTType.AggregateGuard,
        ASTType.ConditionalLiteral,
        ASTType.Aggregate,
        ASTType.BodyAggregateElement,
        ASTType.BodyAggregate,
        ASTType.HeadAggregateElement,
        ASTType.HeadAggregate,
        ASTType.Disjunction,
        ASTType.DisjointElement,
        ASTType.Disjoint,
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

    def __call__(self, stmt: AST):
        self._stmt = stmt
        self._visit(stmt)

    def _visit(self, ast: AST):
        '''
        Dispatch to a visit method.
        '''
        if (ast.ast_type in NonFactVisitor.ERROR_AST or
            (ast.ast_type == ASTType.Function and ast.external)):
            line = ast.location.begin.line
            column = ast.location.begin.column
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

def parse_fact_string(aspstr,unifier,*,factbase=None,
                      raise_nomatch=False,raise_nonfact=False):
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
        with clast.ProgramBuilder(ctrl) as bld:
            if raise_nonfact:
                nfv = NonFactVisitor()
                def on_rule(ast: AST):
                    nonlocal nfv, bld
                    if nfv: nfv(ast)
                    bld.add(ast)
            else:
                on_rule = bld.add

            clast.parse_string(aspstr, on_rule)
    except ClingoParserWrapperError as e:
        raise e.exc

    ctrl.ground([("base",[])])

    return un.unify([sa.symbol for sa in ctrl.symbolic_atoms if sa.is_fact],
                    factbase=factbase, raise_nomatch=raise_nomatch)




def parse_fact_files(files,unifier,*,factbase=None,
                     raise_nomatch=False,raise_nonfact=False):
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
        with clast.ProgramBuilder(ctrl) as bld:
            if raise_nonfact:
                nfv = NonFactVisitor()
                def on_rule(ast: AST):
                    nonlocal nfv, bld
                    if nfv: nfv(ast)
                    bld.add(ast)
            else:
                def on_rule(ast: AST):
                    nonlocal bld
                    bld.add(ast)

            clast.parse_files(files, on_rule)

    except ClingoParserWrapperError as e:
        raise e.exc

    ctrl.ground([("base",[])])
    return un.unify([sa.symbol for sa in ctrl.symbolic_atoms if sa.is_fact],
                    factbase=factbase, raise_nomatch=raise_nomatch)

#------------------------------------------------------------------------------
#
# A pure-python fact parser that uses Lark
#------------------------------------------------------------------------------

from .lark_fact_parser import Lark_StandAlone, Transformer, VisitError, LarkError, UnexpectedInput

class _END:
    pass

class _NEGATE:
    pass

END = _END()
NEGATE = _NEGATE()

class LarkFactTransformer(Transformer):
    def STRING(self, v):
        return symbols.String(v.value.strip("\""))
    def END(self, v):
        return END
    def NEGATE(self, v):
        return NEGATE
    def NAME(self, v):
        return str(v.value)
    def NUMBER(self, v):
        return symbols.Number(int(v))
    def function(self, v):
        if v[0] == NEGATE:
            positive = False
            v.pop(0)
        else:
            positive = True
        args = [] if len(v) == 1 else v[1]
        return symbols.Function(v[0],args,positive=positive)
    def fact(self, f):
        return f[0]
    def args(self,v):
        return v
    def tuple(self, v):
        return symbols.Function("",v[0])
    def start(self, v):
        return v

def lark_parse_fact_string(aspstr,unifier, *,
                           factbase=None, raise_nomatch=False):
    try:
        fact_parser = Lark_StandAlone(transformer=LarkFactTransformer())
        symbols = fact_parser.parse(aspstr)
        un = Unifier(unifier)
        return un.unify(symbols, factbase=factbase, raise_nomatch=raise_nomatch)
    except UnexpectedInput as e:
        raise FactParserError(str(e), line=e.line, column=e.column)
    except LarkError as e:
        raise FactParserError(str(e))

def lark_parse_fact_files(files, unifier, *,
                          factbase=None, raise_nomatch=False):
    fb=FactBase() if factbase is None else factbase
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
