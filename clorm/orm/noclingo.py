"""Dealing with the persistence problem of clingo Symbols.


When `clingo.Symbol` objects are created they cannot be freed and will persist
until the process ends. This works fine for many applications where the process
is short-lived. For example when running the solver once to find a solution and
present it to the user and then exit. However, for long running processes, such
as a server that needs to solve many problems, not being able to free
`clingo.Symbol` objects can cause memory problems if many new objects are being
created.

Clorm solves this problem by allow for an internal `clorm.NoSymbol` object to
be used instead of `clingo.Symbol` objects when creating clorm facts. These
objects behave the same as `clingo.Symbol` objects except that they cannot be
passed to the solver. NOCLINGO mode is when Clorm is configured to create
NoSymbol facts.

The idea is that a long-running process would be run in NOCLINGO mode, while
the clingo solver would be run in a, relatively short-lived, spawned
sub-process that is operating in "normal" CLINGO mode.  Any `clingo.Symbol`
data that needs to be communicated back to the main process can be converted to
`clorm.NoSymbol` objects, which can then be serialised and sent to the main
process. If clorm fact objects are serialized this conversion process happens
transparently to the user.

However, despite the potential usefulness of NOCLINGO, in many, and perhaps
most, use-cases there is no need for long running process. In such cases the
small, but non-zero, overhead of NOCLINGO can be undesirable. Because of this
NOCLINGO is disabled by default and must be explictly enabled with an
environment variable CLORM_NOCLINGO that must be set before the clorm libraries
are loaded. For example in a bash environment:

    export CLORM_NOCLINGO = True

Or from within a Python process (but before clorm is imported) set:

    import os
    os.environ["CLORM_NOCLINGO"] = "True"

Once CLORM_NOCLINGO is enabled then depending on the current symbol mode Clorm
will (internally) create `clingo.Symbol` or `noclingo.NoSymbol` objects when
facts are created. The current symbol mode can be set and viewed with the
function `set_symbol_mode()` and `get_symbol_mode()`. If the CLORM_NOCLINGO
environment variable is not set, or is set to one of "0", "False", "No",
"Disable" (case-insensitive), then the NOCLINGO mechanism is disabled and it is
not possible to switch between modes. In this case calling `set_symbol_mode()`
will raise an exception.

"""
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------

import os
import enum
import clingo

from clingo import SymbolType, Symbol
from typing import TYPE_CHECKING, Optional, Sequence, Tuple, Union, Any, cast

if TYPE_CHECKING:
    from ._typing import AnySymbol

__all__ = [
    'SymbolType',
    'Symbol',
    'Function',
    'Tuple_',
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
# Get and sanitise the value of the CLORM_NOCLINGO environment variable. If the
# environment variable is not defined or if it is any one of "0", "False",
# "No", "Disable" (case-insensitive) then NOCLINGO mode is disabled. Any other
# input is treated as True.
# --------------------------------------------------------------------------------

CLORM_NOCLINGO_DEFAULT = 'False'


def _get_CLORM_NOCLINGO() -> bool:
    tmp = os.environ.get('CLORM_NOCLINGO', CLORM_NOCLINGO_DEFAULT).lower()
    return tmp not in ('0', 'false', 'no', 'disable')


ENABLE_NOCLINGO = _get_CLORM_NOCLINGO()

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

    __slots__ = ("_stype", "_args", "_value", "_sign", "_hash")

    def __init__(self, stype: SymbolType, value: Any = None, args: Sequence['NoSymbol'] = [], sign: bool = True):
        if not isinstance(stype, SymbolType):
            raise TypeError("{} is not a SymbolType".format(stype))
        self._stype = stype
        self._args: Tuple[NoSymbol, ...] = tuple([])
        self._value: Optional[Union[int, str]] = None
        self._sign = None
        if stype == SymbolType.Infimum:
            self._hash = hash(0)
        elif stype == SymbolType.Supremum:
            self._hash = hash(100)
        elif stype == SymbolType.Number:
            if not isinstance(value, int):
                raise TypeError("an integer is required")
            self._value = int(value)
            self._hash = hash(self._value)
        elif stype == SymbolType.String:
            if not isinstance(value, str):
                raise TypeError("{value} is not a str")
            self._value = value
            self._hash = hash(self._value)
        elif stype == SymbolType.Function:
            if not isinstance(value, str):
                raise TypeError("{value} is not a str")
            self._sign = bool(sign)
            self._value = str(value)
            self._args = tuple(args)
            self._hash = hash((self._value, self._args, self._sign))

            if not self._value and not self._sign:
                raise ValueError("Tuple symbol cannot have a negative sign")
        else:
            raise ValueError("Unknown SymbolType {}".format(stype))

    @property
    def name(self) -> str:
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return cast(str, self._value)

    @property
    def arguments(self) -> Tuple['NoSymbol', ...]:
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return self._args

    @property
    def string(self) -> str:
        if self._stype != SymbolType.String:
            raise RuntimeError()
        return cast(str, self._value)

    @property
    def number(self) -> int:
        if self._stype != SymbolType.Number:
            raise RuntimeError()
        return cast(int, self._value)

    @property
    def type(self):
        return self._stype

    @property
    def positive(self) -> bool:
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return cast(bool, self._sign)

    @property
    def negative(self) -> bool:
        if self._stype != SymbolType.Function:
            raise RuntimeError()
        return not self._sign

    def __hash__(self):
        return self._hash

    def __eq__(self, other: object) -> bool:
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
        return self.arguments == tuple(other.arguments)

    def __gt__(self, other: object) -> bool:
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
        return self.arguments > tuple(clingo_to_noclingo(arg) for arg in other.arguments)

    def __le__(self, other: object) -> bool:
        """Overloaded boolean operator."""
        result = self.__gt__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    def __lt__(self, other: object) -> bool:
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
        return self.arguments < tuple(clingo_to_noclingo(arg) for arg in other.arguments)

    def __ge__(self, other: object) -> bool:
        """Overloaded boolean operator."""
        result = self.__lt__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    def __str__(self) -> str:
        if self._stype == SymbolType.Number:
            return f"{self._value}"
        if self._stype == SymbolType.String:
            return f'"{self._value}"'
        if self._stype == SymbolType.Infimum:
            return "#inf"
        if self._stype == SymbolType.Supremum:
            return "#sup"

        # SymbolType.Function - Note: tuples have special cases: empty tuple
        # "()" and a singleton "(a, )"
        if not self._args:
            return str(self._value) if self._value else "()"

        # A function or constant
        if self._value or len(self._args) > 1:
            return "{}{}({})".format("" if self._sign else "-", self._value,
                                     ",".join([str(a) for a in self._args]))
        # A singleton tuple
        return "({},)".format(str(self._args[0]))

    def __repr__(self) -> str:
        return self.__str__()

# --------------------------------------------------------------------------------
# helper functions to create objects
# --------------------------------------------------------------------------------


def NoFunction(name: str, arguments: Sequence[NoSymbol] = [], positive: bool = True) -> NoSymbol:
    return NoSymbol(SymbolType.Function, name, arguments, positive)


def NoString(string: str) -> NoSymbol:
    return NoSymbol(SymbolType.String, string)


def NoNumber(number: int) -> NoSymbol:
    return NoSymbol(SymbolType.Number, number)


def NoTuple_(arguments: Sequence[NoSymbol]) -> NoSymbol:
    return NoSymbol(SymbolType.Function, "", arguments)


NoInfimum = NoSymbol(SymbolType.Infimum)

NoSupremum = NoSymbol(SymbolType.Supremum)


# --------------------------------------------------------------------------------
# Functions to convert between clingo.Symbol and noclingo.Symbol
# --------------------------------------------------------------------------------

def clingo_to_noclingo(clsym: "AnySymbol") -> NoSymbol:
    if isinstance(clsym, NoSymbol):
        return clsym
    if clsym.type == clingo.SymbolType.Infimum:
        return NoInfimum
    elif clsym.type == clingo.SymbolType.Supremum:
        return NoSupremum
    elif clsym.type == clingo.SymbolType.Number:
        return NoNumber(clsym.number)
    elif clsym.type == clingo.SymbolType.String:
        return NoString(clsym.string)
    elif clsym.type != clingo.SymbolType.Function:
        raise TypeError(("Symbol '{}' ({}) is not of type clingo.SymbolType."
                         "Function").format(clsym, type(clsym)))

    return NoFunction(clsym.name,
                      tuple(clingo_to_noclingo(t) for t in clsym.arguments),
                      clsym.positive)


def noclingo_to_clingo(nclsym: "AnySymbol") -> Symbol:
    if isinstance(nclsym, clingo.Symbol):
        return nclsym
    if nclsym.type == SymbolType.Infimum:
        return clingo.Infimum
    elif nclsym.type == SymbolType.Supremum:
        return clingo.Supremum
    elif nclsym.type == SymbolType.Number:
        return clingo.Number(nclsym.number)
    elif nclsym.type == SymbolType.String:
        return clingo.String(nclsym.string)
    elif nclsym.type != SymbolType.Function:
        raise TypeError(("Symbol '{}' ({}) is not of type noclingo.SymbolType."
                         "Function").format(nclsym, type(nclsym)))

    return clingo.Function(nclsym.name,
                           tuple(noclingo_to_clingo(t) for t in nclsym.arguments),
                           nclsym.positive)


# ------------------------------------------------------------------------------
# A mechanism to group together the symbol generator functions for clingo or
# noclingo.
# ------------------------------------------------------------------------------

class SymbolMode(enum.IntEnum):
    CLINGO = 0
    NOCLINGO = 1


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
# Common functions that are valid even if NOCLINGO is disabled
# ------------------------------------------------------------------------------

def get_symbol_mode() -> SymbolMode:
    return _mode


def get_Infimum() -> "AnySymbol":
    return _infimum


def get_Supremum() -> "AnySymbol":
    return _supremum


if TYPE_CHECKING:
    def set_symbol_mode(sm: SymbolMode) -> None:
        ...

    def Function(name: str, arguments: Sequence[Symbol] = [], positive: bool = True) -> "AnySymbol":
        ...

    def String(string: str) -> "AnySymbol":
        ...

    def Number(number: int) -> "AnySymbol":
        ...

    def Tuple_(arguments: Sequence[Symbol]) -> "AnySymbol":
        ...

else:
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

        def Function(name: str, arguments: Sequence[Symbol] = [], positive: bool = True) -> Symbol:
            return _function(name, arguments, positive)

        def String(string: str) -> Symbol:
            return _string(string)

        def Number(number: int) -> Symbol:
            return _number(number)

        # clingo.Tuple_() doesn't have default parameters so follow the same here
        def Tuple_(arguments: Sequence[Symbol]) -> Symbol:
            return _tuple_(arguments)

    else:

        def set_symbol_mode(sm: SymbolMode):
            raise RuntimeError("NOCLINGO mode is disabled.")

        Function = clingo.Function
        String = clingo.String
        Number = clingo.Number
        Tuple_ = clingo.Tuple_


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
