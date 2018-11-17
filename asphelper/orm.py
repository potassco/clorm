#------------------------------------------------------------------------------
# ORM provides a Object Relational Mapper type model for specifying non-logical
# symbols (ie., predicates and terms)
# ------------------------------------------------------------------------------

#import logging
#import os
import inspect
import collections
from clingo import Number, String, Function, Symbol, SymbolType
from clingo import Control


#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
#g_logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
# A classproperty decorator. (see https://stackoverflow.com/questions/3203286/how-to-create-a-read-only-class-property-in-python)
#------------------------------------------------------------------------------
class classproperty(object):
    def __init__(self, getter):
        self.getter= getter
    def __get__(self, instance, owner):
        return self.getter(owner)

#------------------------------------------------------------------------------
# Convert different clingo symbol objects to the appropriate python type
#------------------------------------------------------------------------------

def _integer_cltopy(term):
    if term.type != SymbolType.Number:
        raise TypeError("Object {0} is not a Number term")
    return term.number

def _string_cltopy(term):
    if term.type != SymbolType.String:
        raise TypeError("Object {0} is not a String term")
    return term.string

def _constant_cltopy(term):
    if   (term.type != SymbolType.Function or
          not term.name or len(term.arguments) != 0):
        raise TypeError("Object {0} is not a Simple term")
    return term.name

#------------------------------------------------------------------------------
# Convert python object to the approproate clingo Symbol object
#------------------------------------------------------------------------------

def _integer_pytocl(v):
    return Number(v)

def _string_pytocl(v):
    return String(v)

def _constant_pytocl(v):
    return Function(v,[])

#------------------------------------------------------------------------------
# check that a symbol unifies with the different field types
#------------------------------------------------------------------------------

def _integer_unifies(term):
    if term.type != SymbolType.Number: return False
    return True

def _string_unifies(term):
    if term.type != SymbolType.String: return False
    return True

def _constant_unifies(term):
    if term.type != SymbolType.Function: return False
    if not term.name or len(term.arguments) != 0: return False
    return True

#------------------------------------------------------------------------------
# Field definitions. All fields have the functions: pytocl, cltopy, and unifies,
# and the properties: default, is_field_defn
# ------------------------------------------------------------------------------

class SimpleField(object):
    def __init__(self, inner_cltopy, inner_pytocl, unifies,
                 outfunc=None, infunc=None, default=None):
        self._inner_cltopy = inner_cltopy
        self._inner_pytocl = inner_pytocl
        self._unifies = unifies
        self._outfunc = outfunc
        self._infunc = infunc
        self._default = default

    def pytocl(self, v):
        if self._infunc: return self._inner_pytocl(self._infunc(v))
        return self._inner_pytocl(v)

    def cltopy(self, symbol):
        if self._outfunc: return self._outfunc(self._inner_cltopy(symbol))
        return self._inner_cltopy(symbol)

    def unifies(self, symbol):
        return self._unifies(symbol)

    @property
    def default(self):
        return self._default

    @property
    def is_field_defn(self): return True

class IntegerField(SimpleField):
    def __init__(self, outfunc=None, infunc=None, default=None):
        super(IntegerField,self).__init__(inner_cltopy=_integer_cltopy,
                                          inner_pytocl=_integer_pytocl,
                                          unifies=_integer_unifies,
                                          outfunc=outfunc,infunc=infunc,
                                          default=default)

class StringField(SimpleField):
    def __init__(self, outfunc=None, infunc=None, default=None):
        super(StringField,self).__init__(inner_cltopy=_string_cltopy,
                                         inner_pytocl=_string_pytocl,
                                         unifies=_string_unifies,
                                         outfunc=outfunc,infunc=infunc,
                                         default=default)

class ConstantField(SimpleField):
    def __init__(self, outfunc=None, infunc=None, default=None):
        super(ConstantField,self).__init__(inner_cltopy=_constant_cltopy,
                                           inner_pytocl=_constant_pytocl,
                                           unifies=_constant_unifies,
                                           outfunc=outfunc,infunc=infunc,
                                           default=default)

#------------------------------------------------------------------------------
# A ComplexField definition allows you to wrap an existing NonLogicalSymbol
# definition.
# ------------------------------------------------------------------------------

class ComplexField(object):
    def __init__(self, defn, default=None):
        if not issubclass(defn, NonLogicalSymbol):
            raise TypeError("Not a subclass of ComplexTerm: {}".format(defn))
        self._defn = defn
        self._default = default

    def pytocl(self, value):
        if not isinstance(value, self._defn):
            raise TypeError("Value not an instance of {}".format(self._defn))
        return value.clingo_symbol

    def cltopy(self, symbol):
        return self._defn(_symbol=symbol)

    def unifies(self, symbol):
        try:
            tmp = self.cltopy(symbol)
            return True
        except ValueError:
            return False

    @property
    def default(self):
        return self._default

    @property
    def is_field_defn(self): return True


#------------------------------------------------------------------------------
# The NonLogicalSymbol base class and supporting functions and classes
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Helper functions for NonLogicalSymbolMeta class to create a NonLogicalSymbol
# class constructor.
# ------------------------------------------------------------------------------

# Construct a NonLogicalSymbol via an explicit clingo Symbol
def _nls_init_by_symbol(self, **kwargs):
    if len(kwargs) != 1:
        raise ValueError("Invalid combination of keyword arguments")
    symbol = kwargs["_symbol"]
    class_name = type(self).__name__
    if not self._unifies(symbol):
        raise ValueError(("Failed to unify symbol {} with "
                          "NonLogicalSymbol class {}").format(symbol, class_name))
#    self._symbol = symbol
    for idx, (field_name, field_defn) in enumerate(self.meta.field_defns.items()):
        self._field_values[field_name] = field_defn.cltopy(symbol.arguments[idx])

# Construct a NonLogicalSymbol via the field keywords
def _nls_init_by_keyword_values(self, **kwargs):
    class_name = type(self).__name__
    pred_name = self.meta.name
    fields = set(self.meta.field_defns.keys())

    invalids = [ k for k in kwargs if k not in fields ]
    if invalids:
        raise ValueError(("Arguments {} are not valid fields "
                          "of {}".format(invalids,class_name)))

    # Construct the clingo function arguments
    for field_name, field_defn in self.meta.field_defns.items():
        if field_name not in kwargs:
            if not field_defn.default:
                raise ValueError(("Unspecified field {} has no "
                                  "default value".format(field_name)))
            self._field_values[field_name] = field_defn.default
        else:
            self._field_values[field_name] = kwargs[field_name]

    # Create the clingo symbol object
    #self._symbol = self._generate_symbol()

# Construct a NonLogicalSymbol via the field keywords
def _nls_init_by_positional_values(self, *args):
    class_name = type(self).__name__
    pred_name = self.meta.name
    argc = len(args)
    arity = len(self.meta.field_defns)
    if argc != arity:
        return ValueError("Expected {} arguments but {} given".format(arity,argc))

    for idx, (field_name, field_defn) in enumerate(self.meta.field_defns.items()):
        self._field_values[field_name] = args[idx]

    # Create the clingo symbol object
    #self._symbol = self._generate_symbol()

# Constructor for every NonLogicalSymbol sub-class
def _nls_constructor(self, *args, **kwargs):
    self._symbol = None
    self._field_values = {}
    if "_symbol" in kwargs:
        _nls_init_by_symbol(self, **kwargs)
    elif len(args) > 0:
        _nls_init_by_positional_values(self, *args)
    else:
        _nls_init_by_keyword_values(self, **kwargs)


#------------------------------------------------------------------------------
# A Metaclass for the NonLogicalSymbol base class
#------------------------------------------------------------------------------
class NonLogicalSymbolMeta(type):

    #--------------------------------------------------------------------------
    # Support member fuctions
    #--------------------------------------------------------------------------

    # Function to check that an object satisfies the requirements of a field.
    # Must have functions cltopy and pytocl, and a property default
    @classmethod
    def _is_field_defn(cls, obj):
        try:
            if obj.is_field_defn: return True
        except AttributeError:
            pass
        return False

    # Create a field getter functor
    @classmethod
    def _make_field_getter(cls, idx, field_name, field_defn):
        def getter(self):
            return self._field_values[field_name]
#            return field_defn.cltopy(self._symbol.arguments[idx])
        return getter

    # Create a field getter functor
    @classmethod
    def _make_field_setter(cls, idx, field_name, field_defn):
        def setter(self,x):
            self._field_values[field_name] = x
#            return field_defn.cltopy(self._symbol.arguments[idx])
        return setter

    # build the metadata for the NonLogicalSymbol
    @classmethod
    def _make_metadata(cls, class_name, dct):

        # Generate a name for the NonLogicalSymbol
        name = class_name[:1].lower() + class_name[1:]  # convert first character to lowercase
        if "Meta" in dct:
            metadefn = dct["Meta"]
            if not inspect.isclass(metadefn):
                raise TypeError("'Meta' attribute is not an inner class")
            name_def="name" in metadefn.__dict__
            istuple_def="istuple" in metadefn.__dict__
            if name_def : name = metadefn.__dict__["name"]
            istuple = metadefn.__dict__["istuple"] if istuple_def else False

            if name_def and istuple:
                raise AttributeError(("Mutually exclusive meta attibutes "
                                      "'name' and 'istuple' "))
            elif istuple: name = ""

        # Generate the field definitions
        field_defns = collections.OrderedDict()
        idx = 0
        for field_name, field_defn in dct.items():
            if not cls._is_field_defn(field_defn): continue
            if field_name.startswith('_'):
                raise ValueError(("Error: field name starts with an "
                                  "underscore: {}").format(field_name))
            if field_name == "meta":
                raise ValueError(("Error: invalid field name: 'meta' "
                                  "is a reserved word"))
            if field_name == "clingo_symbol":
                raise ValueError(("Error: invalid field name: 'clingo_symbol' "
                                  "is a reserved word"))
            field_defns[field_name] = field_defn
            idx += 1

        # Now create the MetaData object
        return NonLogicalSymbol.MetaData(name=name,field_defns=field_defns)

    #--------------------------------------------------------------------------
    # Allocate the new metaclass
    #--------------------------------------------------------------------------
    def __new__(meta, name, bases, dct):
        if name == "NonLogicalSymbol":
            return super(NonLogicalSymbolMeta, meta).__new__(meta, name, bases, dct)

        md = meta._make_metadata(name, dct)

        # Set the _meta attribute and constructor
        dct["_meta"] = md
        dct["__init__"] = _nls_constructor

        # Create a property attribute corresponding to each field name while
        # also making the values indexable.
        getters = []
        setters = []
        for idx, (field_name, field_defn) in enumerate(md.field_defns.items()):
            getter = meta._make_field_getter(idx, field_name, field_defn)
            setter = meta._make_field_setter(idx, field_name, field_defn)
            dct[field_name] = property(getter,setter)
            getters.append(getter)
            setters.append(setter)
        dct["_field_getters"] = tuple(getters)
        dct["_field_setters"] = tuple(setters)

        return super(NonLogicalSymbolMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# A base non-logical symbol that all predicate/term declarations must inherit
# from. The Metaclass creates the magic to create the fields and the underlying
# clingo symbol object.
# ------------------------------------------------------------------------------

class NonLogicalSymbol(object, metaclass=NonLogicalSymbolMeta):

    #--------------------------------------------------------------------------
    # A Metadata internal object for each NonLogicalSymbol class
    #--------------------------------------------------------------------------
    class MetaData(object):
        def __init__(self, name, field_defns):
            self._name = name
            self._field_defns = field_defns

        @property
        def name(self):
            return self._name

        @property
        def field_defns(self):
            return self._field_defns

        @property
        def field_names(self):
            return [ fn for fn, fd in self._field_defns.items() ]

        @property
        def arity(self):
            return len(self.field_names)

        @property
        def is_tuple(self):
            return self.name == ""

    #--------------------------------------------------------------------------
    # Some properties of the NonLogicalSymbol
    #--------------------------------------------------------------------------

    # Get the underlying clingo symbol object
    @property
    def clingo_symbol(self):
        return self._generate_symbol()

    # Recompute the symbol object from the stored field objects
    def _generate_symbol(self):
        pred_args = []
        for field_name, field_defn in self.meta.field_defns.items():
            pred_args.append(field_defn.pytocl(self._field_values[field_name]))
        # Create the clingo symbol object
        return Function(self.meta.name, pred_args)


    # Get the metadata for the NonLogicalSymbol definition
    @classproperty
    def meta(cls):
        return cls._meta

    #--------------------------------------------------------------------------
    # Class methods
    #--------------------------------------------------------------------------

    # Returns whether or not a Symbol can unify with this NonLogicalSymbol
    @classmethod
    def _unifies(cls, symbol):
        if symbol.type != SymbolType.Function: return False

        name = cls.meta.name
        field_defns = cls.meta.field_defns

        if symbol.name != name: return False
        if len(symbol.arguments) != len(field_defns): return False

        for idx, (field_name, field_defn) in enumerate(field_defns.items()):
            term = symbol.arguments[idx]
            if not field_defn.unifies(symbol.arguments[idx]): return False
        return True

    # Factory that returns a unified NonLogicalSymbol object
    @classmethod
    def _unify(cls, symbol):
        return cls(_symbol=symbol)

    #--------------------------------------------------------------------------
    # Overloaded index operator to access the values
    #--------------------------------------------------------------------------
    def __getitem__(self, idx):
        return self._field_getters[idx](self)

    def __setitem__(self, idx,v):
        return self._field_setters[idx](self,v)

    #--------------------------------------------------------------------------
    # Overloaded operators
    # FIXUP NOT SURE WHETHER I SHOULD SUPPORT THESE OVERLOADS
    #--------------------------------------------------------------------------
    def __eq__(self, other):
        self_symbol = self.clingo_symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.clingo_symbol
            return self_symbol == other_symbol
        elif type(other) == Symbol:
            return self_symbol == other
        else:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        self_symbol = self.clingo_symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.clingo_symbol
            return self_symbol < other_symbol
        elif type(other) == Symbol:
            return self_symbol < other
        else:
            return NotImplemented

    def __ge__(self, other):
        result = self.__lt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __gt__(self, other):
        self_symbol = self.clingo_symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.clingo_symbol
            return self_symbol > other_symbol
        elif type(other) == Symbol:
            return self_symbol > other
        else:
            return NotImplemented

    def __le__(self, other):
        result = self.__gt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __str__(self):
        self_symbol = self.clingo_symbol
        return str(self_symbol)

#    def __repr__(self):
#        return self.__str__()

#------------------------------------------------------------------------------
# Convenience aliases for NonLogicalSymbol - this makes it more intuitive
#------------------------------------------------------------------------------
Predicate=NonLogicalSymbol
ComplexTerm=NonLogicalSymbol

#------------------------------------------------------------------------------
# Functions to process the terms/symbols within the clingo Model object
#------------------------------------------------------------------------------

def process_facts(facts, pred_filter):
    # Create a hash for matching NonLogicalSymbols
    matcher = {}
    matches = {}
    for p in pred_filter:
        name = p.meta.name
        arity = len(p.meta.field_defns)
        matcher[(name,arity)] = p
        matches[p] = []
    for f in facts:
        if type(f) != Symbol:
            raise TypeError("Object {0} is not a Symbol")
        if f.type != SymbolType.Function:
            raise TypeError("Symbol {0} is not a Function")
        name = f.name
        arity = len(f.arguments)
        p = matcher.get((name,arity), None)
        if not p: continue
        try:
            matches[p].append(p(_symbol=f))
        except ValueError:
            pass
    return matches

#------------------------------------------------------------------------------
# Functions that overlay the clingo Control object
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Insert a fact (i.e., a ground atom) into the logic program.  Note: I don't
# think clingo.Control has a function for adding an atomic Function symbol,
# similar to the assign_external interface. Instead I regenerate a logic
# programming string and add it to the base program - which is not ideal.
# ------------------------------------------------------------------------------
def control_insert(ctrl, fact):
    if not isinstance(fact, NonLogicalSymbol):
        raise TypeError("Object {} is not a NonLogicalSymbol".format(fact))
    fact_str = "{}.".format(fact.clingo_symbol)
    ctrl.add("base",[], fact_str)

#--------------------------------------------------------------------------
# Set the external status of the NonLogicalSymbol instance is easier
#--------------------------------------------------------------------------
def control_assign_external(ctrl, fact, truth):
    if not isinstance(fact, NonLogicalSymbol):
        raise TypeError("Object {} is not a NonLogicalSymbol".format(fact))
    ctrl.assign_external(fact.clingo_symbol, truth)

def control_release_external(ctrl, fact):
    ctrl.release_external(self.clingo_symbol)

#------------------------------------------------------------------------------
# Run the solver - replace any high-level NonLogicalSymbol assumptions with their
# clingo symbols.
# ------------------------------------------------------------------------------

def control_solve(ctrl, **kwargs):
    if "assumptions" in kwargs:
        nas = []
        for (a,b) in kwargs["assumptions"]:
            if isinstance(a, NonLogicalSymbol):
                nas.append((a.clingo_symbol,b))
            else:
                nas.append((a,b))
            fi
        kwargs["assumptions"] = nas
    return ctrl.solve(kwargs)



# ------------------------------------------------------------------------------
# Patch the Symbol comparison operators
# ------------------------------------------------------------------------------

def patch_clingo_symbol():
    pass

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

