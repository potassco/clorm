#------------------------------------------------------------------------------
# ORM provides a Object Relational Mapper type model for specifying
# predicates/terms.
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
# Predicate field definitions. All fields have the functions: pytocl, cltopy,
# and unifies, and the properties: default, is_field_defn
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
# Predicate field definitions for function and tuple fields.
# ------------------------------------------------------------------------------

class FunctionField(object):
    def __init__(self, fields, name="", default=None):
        if type(self) == FunctionField and not name:
            raise ValueError("Cannot define a function with an empty name")
        if not fields: raise ValueError("No defined sub-fields")
        for fd in fields:
            if not fd.is_field_defn:
                raise ValueError("Not a field defintion: {}".format(fd))
            if fd.default != None:
                raise ValueError("Tuple fields cannot have a default value")
        self._field_defns = fields.copy()
        self._arity = len(fields)
        self._default = default
        self._name = name

    def pytocl(self, tuple_value):
        if len(tuple_value) != self._arity:
            raise ValueError("Mismatched arity of value and field definitions")
        clargs = []
        for idx in range(0,self._arity):
            fd = self._field_defns[idx]
            e = tuple_value[idx]
            clargs.append(fd.pytocl(e))
        return Function(self._name,clargs)

    def cltopy(self, symbol):
        values=[]
        if   (symbol.type != SymbolType.Function or
              symbol.name != self._name or
              len(symbol.arguments) != self._arity):
            raise TypeError("Symbol {0} does not match defn {}".format(self))
        for idx in range(0,self._arity):
            fd = self._field_defns[idx]
            values.append(fd.cltopy(symbol.arguments[idx]))
        return tuple(values)

    def unifies(self, symbol):
        if   (symbol.type != SymbolType.Function or
              symbol.name != self._name or
              len(symbol.arguments) != self._arity): return False
        for idx in range(0,self._arity):
            fd = self._field_defns[idx]
            if not fd.unifies(symbol.arguments[idx]): return Fasle
        return True

    @property
    def default(self):
        return self._default

    @property
    def is_field_defn(self): return True

class TupleField(FunctionField):
    def __init__(self, fields, default=None):
        super(TupleField,self).__init__(fields, name="", default=default)


#------------------------------------------------------------------------------
# A ComplexField definition allows you to wrap an existing Predicate definition
# ------------------------------------------------------------------------------

class ComplexField(object):
    def __init__(self, defn, default=None):
        if not issubclass(defn, BasePredicate):
            raise TypeError("Not a subclass of ComplexTerm: {}".format(defn))
        self._defn = defn
        self._default = default

    def pytocl(self, value):
        if not isinstance(value, self._defn):
            raise TypeError("Value not an instance of {}".format(self._defn))
        return value._raw

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
# Functions to process and construct the Predicate/ComplexTerm classes and their
# attributes.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Construct a predicate name from a class name
def _func_name(name):
    return name[:1].lower() + name[1:] if name else ''

# ------------------------------------------------------------------------------
# The Meta attribute must be a class that defines predicate metadata
def _process_func_meta_class(input_dct, func_meta_class):
    if not inspect.isclass(func_meta_class):
        raise TypeError("Meta attribute is not an inner class")
    maa = func_meta_class.__dict__
#    maa = inspect.getmembers(meta_attr, lambda a: not(inspect.isroutine(a)))
    if "name" in maa: input_dct["name"] = maa["name"]

# ------------------------------------------------------------------------------
# Unify a clingo symbol  with a predicate - return False if they don't unify
def _unify_symbol_and_predicate(symbol, predicate):
    if type(symbol) != Symbol: return False
    if symbol.type != SymbolType.Function: return False
    if not isinstance(predicate, BasePredicate): return False

    pred_name = predicate._metadata["name"]
    pred_field_defns = predicate._field_defns

    if symbol.name != pred_name: return False
    if len(symbol.arguments) != len(pred_field_defns): return False

    for idx, (field_name, field_defn) in enumerate(pred_field_defns.items()):
        term = symbol.arguments[idx]
        if not field_defn.unifies(symbol.arguments[idx]): return False
    return True

# ------------------------------------------------------------------------------
# _predicate_pushup_symbol(self, symbol)
# ------------------------------------------------------------------------------
def _predicate_push_symbol_update(self, symbol):
    self._symbol = symbol

    # Populate the individual fields
    self._field_values = {}
    for idx, (field_name, field_defn) in enumerate(self._field_defns.items()):
        self._field_values[field_name] = field_defn.cltopy(self._symbol.arguments[idx])

# ------------------------------------------------------------------------------
# Construct predicate via an explicit clingo Symbol
def _predicate_init_by_symbol(self, **kwargs):
    if len(kwargs) != 1:
        raise ValueError("Invalid combination of keyword arguments")
    symbol = kwargs["_symbol"]
    class_name = type(self).__name__
    if not _unify_symbol_and_predicate(symbol, self):
        raise ValueError(("Failed to unify symbol {} with "
                          "predicate {}").format(symbol, class_name))
    _predicate_push_symbol_update(self, symbol)

# ------------------------------------------------------------------------------
# Construct predicate via the field keywords
def _predicate_init_by_keyword_values(self, **kwargs):
    class_name = type(self).__name__
    pred_name = self._metadata["name"]
    fields = set(self._field_defns.keys())

    invalids = [ k for k in kwargs if k not in fields ]
    if invalids:
        raise ValueError(("Arguments {} are not valid fields "
                          "of {}".format(invalids,class_name)))

    # Construct the clingo function arguments
    self._field_values = {}
    pred_args = []
    for field_name, field_defn in self._field_defns.items():
        pyvalue=None
        if field_name not in kwargs:
            if not field_defn.default:
                raise ValueError(("Unspecified field {} has no "
                                  "default value".format(field_name)))
            pyvalue=field_defn.default
        else:
            pyvalue=kwargs[field_name]

        # Set the value
        clvalue = field_defn.pytocl(pyvalue)
        self._field_values[field_name] = clvalue
        pred_args.append(clvalue)

    # Create the clingo symbol object
    self._symbol = Function(pred_name, pred_args)

# ------------------------------------------------------------------------------
# Construct predicate via the field keywords
def _predicate_init_by_positional_values(self, *args):
    class_name = type(self).__name__
    pred_name = self._metadata["name"]
    argc = len(args)
    arity = len(self._field_defns)
    if argc != arity:
        return ValueError("Expected {} arguments but {} given".format(arity,argc))

    pred_args = []
    for idx, (field_name, field_defn) in enumerate(self._field_defns.items()):
        pred_args.append(field_defn.pytocl(args[idx]))

    # Create the clingo symbol object
    self._symbol = Function(pred_name, pred_args)

# ------------------------------------------------------------------------------
# Constructor for every BasePredicate sub-class
def _predicate_constructor(self, *args, **kwargs):
    self._symbol = None
    if "_symbol" in kwargs:
        _predicate_init_by_symbol(self, **kwargs)
    elif len(args) > 0:
        _predicate_init_by_positional_values(self, *args)
    else:
        _predicate_init_by_keyword_values(self, **kwargs)



# -----------------------------------------------------------------------------
# Create a functor that gets the value of a field.
def _make_field_functor(field_defn, idx):
    def get_value(self):
        return field_defn.cltopy(self._symbol.arguments[idx])
    return get_value

# ------------------------------------------------------------------------------
# Function to check that an object satisfies the requirements of a field.
# Must have functions cltopy and pytocl, and a property default
def _is_field_definition(obj):
    try:
        if obj.is_field_defn: return True
    except AttributeError:
        pass
    return False

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
class PredicateMeta(type):

    def __new__(meta, name, bases, dct):
        if name == "BasePredicate":
            return super(PredicateMeta, meta).__new__(meta, name, bases, dct)

        pred_metadata = { "name" : _func_name(name) }
        if "Meta" in dct: _process_func_meta_class(pred_metadata, dct["Meta"])

        pred_field_defns = collections.OrderedDict()
        idx = 0
        for fname, fdefn in dct.items():
            if not _is_field_definition(fdefn): continue
            if fname.startswith('_'):
                raise ValueError(("Error: field name starts with an "
                                  "underscore: {}").format(fname))
            pred_field_defns[fname] = fdefn
            dct[fname] = property(_make_field_functor(fdefn,idx))
            idx += 1

        dct["_metadata"] = pred_metadata
        dct["_field_defns"] = pred_field_defns
        dct["__init__"] = _predicate_constructor

        return super(PredicateMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# A base predicate that all predicate declarations must inherit from. The
# Metaclass creates the magic to create the fields and the underlying clingo
# symbol object.
# ------------------------------------------------------------------------------

class BasePredicate(object, metaclass=PredicateMeta):

    #--------------------------------------------------------------------------
    # Some properties of the predicate
    #--------------------------------------------------------------------------

    # Get the underlying clingo symbol object
    @property
    def _raw(self):
        return self._symbol

    # Get the name of the predicate
    @classproperty
    def _name(cls):
        return cls._metadata["name"]

    # Get the arity of the predicate
    @classproperty
    def _arity(cls):
        return len(cls._field_defns)

    #--------------------------------------------------------------------------
    # Overloaded operators
    #--------------------------------------------------------------------------
    def __eq__(self, other):
        if isinstance(other, BasePredicate):
            return self._symbol == other._symbol
        elif type(other) == Symbol:
            return self._symbol == other
        else:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        if isinstance(other, BasePredicate):
            return self._symbol < other._symbol
        elif type(other) == Symbol:
            return self._symbol < other
        else:
            return NotImplemented

    def __ge__(self, other):
        result = self.__lt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __gt__(self, other):
        if isinstance(other, BasePredicate):
            return self._symbol > other._symbol
        elif type(other) == Symbol:
            return self._symbol > other
        else:
            return NotImplemented

    def __le__(self, other):
        result = self.__gt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __str__(self):
        return str(self._symbol)

#    def __repr__(self):
#        return self.__str__()



#------------------------------------------------------------------------------
# Functions to process the terms/symbols within the clingo Model object
#------------------------------------------------------------------------------

def process_facts(facts, pred_filter):
    # Create a hash for matching predicates
    matcher = {}
    matches = {}
    for p in pred_filter:
        name = p._metadata["name"]
        arity = len(p._field_defns)
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
    if not isinstance(fact, BasePredicate):
        raise TypeError("Object {} is not a predicate".format(fact))
    fact_str = "{}.".format(fact._raw)
    ctrl.add("base",[], fact_str)

#--------------------------------------------------------------------------
# Set the external status of the predicate instance is easier
#--------------------------------------------------------------------------
def control_assign_external(ctrl, fact, truth):
    if not isinstance(fact, BasePredicate):
        raise TypeError("Object {} is not a predicate".format(fact))
    ctrl.assign_external(fact._raw, truth)

def control_release_external(ctrl, fact):
    ctrl.release_external(self._raw)

#------------------------------------------------------------------------------
# Run the solver - replace any high-level predicate assumptions with their
# clingo symbols.
# ------------------------------------------------------------------------------

def control_solve(ctrl, **kwargs):
    if "assumptions" in kwargs:
        nas = []
        for (a,b) in kwargs["assumptions"]:
            if isinstance(a, BasePredicate):
                nas.append((a._raw,b))
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

