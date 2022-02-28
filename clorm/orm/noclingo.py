"""Hack for the persistence problem of clingo Symbols.

Currently clingo Symbols cannot be freed once they have been created. This is
potentially a problem for long running processes (such as a server). The
solution in clorm is to provide a "noclingo" mode where a faked Symbol object
can be used. The fake Symbol object can be passed around and freed. It is only
when we need to call the solver that a real clingo Symbol needs to be used.

So the idea is that you can run clorm in a server process using noclingo
Symbols and clingo is only run in a sub-process where you can use real clingo
Symbols.

"""
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------

import functools
import enum
import clingo
import typing

from clingo import SymbolType, Symbol
from typing import Sequence, Union, Any

from clorm.noclingo import ENABLE_NOCLINGO


__all__ = [
    'SymbolType',
    'Symbol',
    'Function',
    'String',
    'Number',
    'SymbolMode',
    'clingo_to_noclingo',
    'noclingo_to_clingo',
    'get_Infimum',
    'get_Supremum',
    'get_symbol_mode',
    'set_symbol_mode'
]



# --------------------------------------------------------------------------------
# Note: the ordering between symbols is manually determined to match clingo 5.5
# --------------------------------------------------------------------------------

_SYMBOLTYPE_OID = {
    SymbolType.Infimum: 1,
    SymbolType.Number: 2,
    SymbolType.Function: 3,
    SymbolType.String: 4,
    SymbolType.Supremum: 5
}

class NoSymbol(object):
    """A noclingo replacement for clingo.Symbol.

    noclingo is a replacement for clingo that provides basic Symbol object
    instantiation as pure python objects (rather than the C clingo external
    library). This allows a process to create a problem instance using the clorm
    predicate/complex term objects, JSON serialise the instance (using the
    clorm.json module) and pass the instance to a second process for actual
    processing.

    This is useful because clingo has a known issue that it cannot release
    Symbol objects. The solver was originally designed to solve one problem and
    exit. It has slowly evolved into calling the solver repeated as part of a
    larger application, but no facility has been added (yet) to allow the old
    Symbol objects to be released.
    """

    __slots__=("_stype","_args","_value","_sign","_hash")

    def __init__(self, stype: SymbolType, value: Any=None, args: Sequence[Any]=[],sign: bool=True):
        if not isinstance(stype, SymbolType):
            raise TypeError("{} is not a SymbolType".format(stype))
        self._stype = stype
        self._args = None
        self._value = None
        self._sign = None
        if stype == SymbolType.Infimum:
            self._hash = hash(0)
        elif stype == SymbolType.Supremum:
            self._hash = hash(100)
        elif stype == SymbolType.Number:
            self._value = int(value)
            self._hash = hash(self._value)
        elif stype == SymbolType.String:
            self._value = str(value)
            self._hash = hash(self._value)
        elif stype == SymbolType.Function:
            self._sign = bool(sign)
            self._value = str(value)
            self._args = tuple(args)
            self._hash = hash((self._value,self._args,self._sign))

            if not self._value and not self._sign:
                raise ValueError("Tuple symbol cannot have a negative sign")
        else:
            raise ValueError("Unknown SymbolType {}".format(stype))

    @property
    def name(self):
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return self._value

    @property
    def arguments(self):
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return self._args

    @property
    def string(self):
        if self._stype != SymbolType.String:
            raise RuntimeError()
        return self._value

    @property
    def number(self):
        if self._stype != SymbolType.Number:
            raise RuntimeError()
        return self._value

    @property
    def type(self):
        return self._stype

    @property
    def positive(self):
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return self._sign

    @property
    def negative(self):
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return not self._sign

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__) and not isinstance(other, Symbol):
            return NotImplemented
        if self.type != other.type:
            return False
        if self.type == SymbolType.Infimum:
            return True
        if self.type == SymbolType.Supremum:
            return True
        if self.type == SymbolType.String:
            return self.string == other.string
        if self.type == SymbolType.Number:
            return self.number == other.number

        # SymbolType.Function
        if self.positive != other.positive:
            return False
        if self.name != other.name:
            return False
        if len(self.arguments) != len(other.arguments):
            return False
        return self.arguments, tuple(other.arguments)

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __gt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__) and not isinstance(other, Symbol):
            return NotImplemented
        if self.type != other.type:
            return _SYMBOLTYPE_OID[self.type] > _SYMBOLTYPE_OID[other.type]
        if self.type == SymbolType.Infimum:
            return False
        if self.type == SymbolType.Supremum:
            return False
        if self.type == SymbolType.Number:
            return self.number > other.number
        if self.type == SymbolType.String:
            return self.string > other.string
        if self.negative and other.positive:
            return True
        if self.positive and other.negative:
            return False
        return self.arguments > tuple(other.arguments)


    def __le__(self, other):
        """Overloaded boolean operator."""
        result = self.__gt__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __lt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__) and not isinstance(other, Symbol):
            return NotImplemented
        if self.type != other.type:
            return _SYMBOLTYPE_OID[self.type] < _SYMBOLTYPE_OID[other.type]
        if self.type == SymbolType.Infimum:
            return False
        if self.type == SymbolType.Supremum:
            return False
        if self.type == SymbolType.Number:
            return self.number < other.number
        if self.type == SymbolType.String:
            return self.string < other.string
        if self.negative and other.positive:
            return False
        if self.positive and other.negative:
            return True
        return self.arguments < tuple(other.arguments)

    def __ge__(self, other):
        """Overloaded boolean operator."""
        result = self.__lt__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __str__(self):
        if self._stype == SymbolType.Number: return str(self._value)
        if self._stype == SymbolType.String: return '"' + self._value + '"'
        if self._stype == SymbolType.Infimum: return "#inf"
        if self._stype == SymbolType.Supremum: return "#sup"

        # SymbolType.Function
        if not self._args: return str(self._value)
        if self._value or len(self._args) > 1:
            return "{}{}({})".format("" if self._sign else "-", self._value,
                                     ",".join([str(a) for a in self._args]))
        # A singleton tuple
        return "({},)".format(str(self._args[0]))

    def __repr__(self):
        return self.__str__()

#--------------------------------------------------------------------------------
# helper functions to create objects
#--------------------------------------------------------------------------------

def NoFunction(name, args=[],sign=True):
    return NoSymbol(SymbolType.Function,name,args,sign)

def NoString(string):
    return NoSymbol(SymbolType.String,string)

def NoNumber(number):
    return NoSymbol(SymbolType.Number,number)

def NoTuple_(args=[]):
    return NoSymbol(SymbolType.Function,"",args)

NoInfimum = NoSymbol(SymbolType.Infimum)

NoSupremum = NoSymbol(SymbolType.Supremum)


#--------------------------------------------------------------------------------
# Functions to convert between clingo.Symbol and noclingo.Symbol
# --------------------------------------------------------------------------------

def clingo_to_noclingo(clsym):
    if isinstance(clsym, NoSymbol): return clsym
    if clsym.type == clingo.SymbolType.Infimum: return NoInfimum
    elif clsym.type == clingo.SymbolType.Supremum: return NoSupremum
    elif clsym.type == clingo.SymbolType.Number: return NoNumber(clsym.number)
    elif clsym.type == clingo.SymbolType.String: return NoString(clsym.string)
    elif clsym.type != clingo.SymbolType.Function:
        raise TypeError(("Symbol '{}' ({}) is not of type clingo.SymbolType."
                         "Function").format(clsym,type(clsym)))

    return NoFunction(clsym.name,
                      (clingo_to_noclingo(t) for t in clsym.arguments),
                      clsym.positive)


def noclingo_to_clingo(nclsym):
    if isinstance(nclsym, clingo.Symbol): return nclsym
    if nclsym.type == SymbolType.Infimum: return clingo.Infimum
    elif nclsym.type == SymbolType.Supremum: return clingo.Supremum
    elif nclsym.type == SymbolType.Number: return clingo.Number(nclsym.number)
    elif nclsym.type == SymbolType.String: return clingo.String(nclsym.string)
    elif nclsym.type != SymbolType.Function:
        raise TypeError(("Symbol '{}' ({}) is not of type noclingo.SymbolType."
                         "Function").format(nclsym,type(nclsym)))

    return clingo.Function(nclsym.name,
                    tuple(noclingo_to_clingo(t) for t in nclsym.arguments),
                    nclsym.positive)

#------------------------------------------------------------------------------
# A mechanism to group together the symbol generator functions for clingo or
# noclingo.
# ------------------------------------------------------------------------------

class SymbolMode(enum.IntEnum):
    CLINGO=0
    NOCLINGO=1

# ------------------------------------------------------------------------------
# Globals to will change depending on clingo or noclingo mode
# ------------------------------------------------------------------------------

_infimum = clingo.Infimum
_supremum = clingo.Supremum
_string = clingo.String
_number = clingo.Number
_tuple_ = clingo.Tuple_
_function = clingo.Function
_mode = SymbolMode.CLINGO


# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------

AnySymbol = Union[Symbol, NoSymbol]

# Forward function signature declaration
def Function(name: str, arguments: Sequence[Symbol] = [], positive: bool=True) -> AnySymbol:
    pass
def String(string: str) -> AnySymbol:
    pass
def Number(number: int) -> AnySymbol:
    pass
def Tuple_(arguments: Sequence[Symbol] = []) -> AnySymbol:
    pass

# ------------------------------------------------------------------------------
# Common functions that are valid even if NOCLINGO is disabled
# ------------------------------------------------------------------------------

def get_symbol_mode() -> SymbolMode:
    return _mode

def get_Infimum() -> AnySymbol:
    return _infimum

def get_Supremum() -> AnySymbol:
    return _supremum


if typing.TYPE_CHECKING:
    def Function(name: str, arguments: Sequence[Symbol] = [], positive: bool=True) -> AnySymbol:
        pass
    def String(string: str) -> AnySymbol:
        pass
    def Number(number: int) -> AnySymbol:
        pass
    def Tuple_(arguments: Sequence[Symbol] = []) -> AnySymbol:
        pass

# NoClingo introduces some overhead, with the indirection when creating
# symbols. But if we don't need NoClingo then we can avoid this indirection
if ENABLE_NOCLINGO:

    def set_symbol_mode(sm: SymbolMode):
        global _infimum, _supremum, _string, _number, _tuple_, _function, _mode
        _mode = sm
        if sm == SymbolMode.CLINGO:
            _infimum = clingo.Infimum
            _supremum = clingo.Supremum
            _string = clingo.String
            _number = clingo.Number
            _tuple_ = clingo.Tuple_
            _function = clingo.Function
        else:
            _infimum = NoInfimum
            _supremum = NoSupremum
            _string = NoString
            _number = NoNumber
            _tuple_ = NoTuple_
            _function = NoFunction

    def Function(name: str, arguments: Sequence[Symbol] = [], positive: bool=True) -> Symbol:
        return _function(name, arguments, positive)

    def String(string: str) -> Symbol:
        return _string(string)

    def Number(number: int) -> Symbol:
        return _number(number)

    def Tuple_(arguments: Sequence[Symbol] = []) -> Symbol:
        return _tuple_(arguments)

else:

    def set_symbol_mode(sm: SymbolMode):
        raise RuntimeError("NOCLINGO mode is disabled.")

    Function=clingo.Function
    String=clingo.String
    Number=clingo.Number
    Tuple_=clingo.Tuple_

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
