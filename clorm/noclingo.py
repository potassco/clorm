#--------------------------------------------------------------------------------
# A library to use instead of the clingo module when we want to convert to/from
# clingo symbol objects without actually using clingo symbol objects. The
# advantage is that it is just a basic python object and doesn't have the
# garbage collection issues that the real clingo symbol objects have. Useful for
# distributed applications.
# --------------------------------------------------------------------------------
import functools
import enum

__all__ = [
    'Function',
    'String',
    'Number',
    'Infimum',
    'Supremum',
    'SymbolType',
    'Control'
]

class SymbolType(enum.IntEnum):
    Infimum = 1
    Number = 2
    String = 3
    Function = 4
    Supremum = 5

    def __str__(self):
        if self.Infimum: return "Infimum"
        elif self.Number: return "Number"
        elif self.String: return "String"
        elif self.Function: return "Function"
        return "Supremum"


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

    def __init__(self, stype, value=None, args=[],sign=True):
        if not isinstance(stype, SymbolType):
            raise TypeError("{} is not a SymbolType".format(stype))
        self._stype = stype
        self._args = None
        self._value = None
        self._sign = bool(sign)
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
            self._value = str(value)
            self._args = list(args)
            self._hash = hash(self._value)
            self._hash ^= hash(self._sign)
            if self._args:
                t = functools.reduce(lambda x,y: x ^ y, [ hash(a) for a in self._args ])
                self._hash ^= t
            if not self._value and not self._sign:
                raise ValueError("Tuple symbol cannot have a negative sign")
        else:
            raise ValueError("Unknown SymbolType {}".format(stype))

    @property
    def name(self):
        if self._stype != SymbolType.Function: return None
        return self._value

    @property
    def arguments(self):
        if self._stype != SymbolType.Function: return None
        return self._args

    @property
    def string(self):
        if self._stype != SymbolType.String: return None
        return self._value

    @property
    def number(self):
        if self._stype != SymbolType.Number: return None
        return self._value

    @property
    def type(self):
        return self._stype

    @property
    def positive(self):
        if self._stype != SymbolType.Function: return None
        return self._sign

    @property
    def negative(self):
        if self._stype != SymbolType.Function: return None
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
        if self._stype != other._stype: return self._stype > other._stype
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
        if self._stype != other._stype: return self._stype < other._stype
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
# Replacement for clingo.Control that simply throws an exception when
# instantiated.
# --------------------------------------------------------------------------------

class Control(object):
    """A noclingo replacement for clingo.Control.

    noclingo is a replacement for clingo that provides basic Symbol object
    instatiation as pure python objects (rather than the C clingo external
    library). The solver cannot be run using noclingo so noclingo.Control simply
    raises a TypeError on instantiation.

    """

    def __init__(*args, **kwargs):
        raise TypeError("noclingo.Control cannot be instantiated")

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
