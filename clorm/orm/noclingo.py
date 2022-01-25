#--------------------------------------------------------------------------------
# A library to use instead of the clingo module when we want to convert to/from
# clingo symbol objects without actually using clingo symbol objects. The
# advantage is that it is just a basic python object and doesn't have the
# garbage collection issues that the real clingo symbol objects have. Useful for
# distributed applications.
# --------------------------------------------------------------------------------
import functools
import enum
import clingo
from clingo import SymbolType

__all__ = [
    'Function',
    'String',
    'Number',
    'Infimum',
    'Supremum',
    'SymbolType',
    'is_Number',
    'is_Function',
    'is_String',
    'is_Infimum',
    'is_Supremum',
    'is_Symbol',
    'clingo_to_noclingo',
    'noclingo_to_clingo',
    'SymbolMode',
    'get_symbol_generator'
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

class Symbol(object):
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

    def __init__(self, stype, value=None, args=[],sign=True):
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
        if not isinstance(other, self.__class__): return NotImplemented
        if self._stype != other._stype: return False
        if self._stype == SymbolType.Infimum: return True
        if self._stype == SymbolType.Supremum: return True
        if self._stype != SymbolType.Function: return self._value == other._value

        # SymbolType.Function
        if self._hash != other._hash: return False
        if self._value != other._value: return False
        return self._args == other._args

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __gt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__): return NotImplemented
        if self._stype != other._stype:
            return _SYMBOLTYPE_OID[self._stype] > _SYMBOLTYPE_OID[other._stype]
        if self._stype == SymbolType.Infimum: return False
        if self._stype == SymbolType.Supremum: return False

        if self._stype != SymbolType.Function: return self._value > other._value
        if self._value != other._value: return self._value < other._value
        return self._args > other._args

    def __le__(self, other):
        """Overloaded boolean operator."""
        result = self.__gt__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __lt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__): return NotImplemented
        if self._stype != other._stype:
            return _SYMBOLTYPE_OID[self._stype] < _SYMBOLTYPE_OID[other._stype]
        if self._stype == SymbolType.Infimum: return False
        if self._stype == SymbolType.Supremum: return False

        if self._stype != SymbolType.Function: return self._value < other._value
        if self._value != other._value: return self._value < other._value
        return self._args < other._args

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
        return "{}{}({})".format("" if self._sign else "-", self._value,
                                 ",".join([str(a) for a in self._args]))

    def __repr__(self):
        return self.__str__()

#--------------------------------------------------------------------------------
# Constants
#--------------------------------------------------------------------------------

Infimum = Symbol(SymbolType.Infimum)
Supremum = Symbol(SymbolType.Supremum)

#--------------------------------------------------------------------------------
# helper functions to create objects
#--------------------------------------------------------------------------------

def Function(name, args=[],sign=True):
    return Symbol(SymbolType.Function,name,args,sign)

def String(string):
    return Symbol(SymbolType.String,string)

def Number(number):
    return Symbol(SymbolType.Number,number)


#--------------------------------------------------------------------------------
# Functions to convert between clingo.Symbol and noclingo.Symbol
# --------------------------------------------------------------------------------

def clingo_to_noclingo(clsym):
    if clsym.type == clingo.SymbolType.Infimum: return Infimum
    elif clsym.type == clingo.SymbolType.Supremum: return Supremum
    elif clsym.type == clingo.SymbolType.Number: return Number(clsym.number)
    elif clsym.type == clingo.SymbolType.String: return String(clsym.string)
    elif clsym.type != clingo.SymbolType.Function:
        raise TypeError(("Symbol '{}' ({}) is not of type clingo.SymbolType."
                         "Function").format(clsym,type(clsym)))

    return Function(clsym.name,
                    (clingo_to_noclingo(t) for t in clsym.arguments),
                    clsym.positive)


def noclingo_to_clingo(nclsym):
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

# ------------------------------------------------------------------------------
# Functions to test the type of Symbol irrespective of clingo.Symbol or
# noclingo.Symbol.
# ------------------------------------------------------------------------------
def is_Number(sym):
    try:
        return sym.type == SymbolType.Number
    except:
        return False

def is_String(sym):
    try:
        return sym.type == SymbolType.String
    except:
        return False

def is_Function(sym):
    try:
        return sym.type == SymbolType.Function
    except:
        return False

def is_Supremum(sym):
    try:
        return sym.type == SymbolType.Supremum
    except:
        return False

def is_Infimum(sym):
    try:
        return sym.type == SymbolType.Infimum
    except:
        return False

def is_Symbol(sym):
    return (isinstance(sym, clingo.Symbol) or
            isinstance(sym, noclingo.Symbol))

#------------------------------------------------------------------------------
# A mechanism to group together the symbol generator functions for clingo or
# noclingo.
# ------------------------------------------------------------------------------

class SymbolMode(enum.IntEnum):
    CLINGO=0
    NOCLINGO=1

class SymbolGenerator(object):
    """Groups together the Symbol generators for clingo or noclingo.

    noclingo is a mirror of the clingo ``Symbol`` class that creates a Python
    only object. ``noclingo.Symbol`` objects can be used as a proxy for
    ``clingo.Symbol`` in places where you don't need to pass the object to the
    clingo solver. The advantage is that this object is not persistent
    throughout the life time of the process.

    The available member functions and properties are:

    * ``Infimum``

    * ``Supremum``

    * ``String()``

    * ``Number()``

    * ``Function()``
    """

    def __init__(self, mode, **kwargs):
        self._mode = mode
        self._links = dict(kwargs)

    @property
    def mode(self): return self._mode

    def __getattr__(self, item):
        return self._links[item]


clingo_symbol_generator = SymbolGenerator(SymbolMode.CLINGO,
                                          Function=clingo.Function,
                                          String=clingo.String,
                                          Number=clingo.Number,
                                          Infimum=clingo.Infimum,
                                          Supremum=clingo.Supremum,
                                          SymbolType=clingo.SymbolType)

noclingo_symbol_generator = SymbolGenerator(SymbolMode.NOCLINGO,
                                            Function=Function,
                                            String=String,
                                            Number=Number,
                                            Infimum=Infimum,
                                            Supremum=Supremum,
                                            SymbolType=SymbolType)

def get_symbol_generator(mode):
    if mode == SymbolMode.CLINGO: return clingo_symbol_generator
    if mode == SymbolMode.NOCLINGO: return noclingo_symbol_generator
    raise ValueError("Unknown SymbolMode {}".format(mode))


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
