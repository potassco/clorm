#------------------------------------------------------------------------------
# A wrapper around clingo to accept a new booking (if possible)
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
#
#------------------------------------------------------------------------------
def _check_symbol(term):
    if type(term) != Symbol:
        raise TypeError("Object {0} is not of type {1}".format(term,Symbol))

#------------------------------------------------------------------------------
# The default getters
#------------------------------------------------------------------------------

def number_getter(term):
    _check_symbol(term)
    if term.type != SymbolType.Number:
        raise TypeError("Object {0} is not a Number term")
    return term.number

def string_getter(term):
    _check_symbol(term)
    if term.type != SymbolType.String:
        raise TypeError("Object {0} is not a String term")
    return term.string

def simple_getter(term):
    _check_symbol(term)
    if   (term.type != SymbolType.Function or
          not term.name or len(term.arguments) != 0):
        raise TypeError("Object {0} is not a Simple term")
    return term.name

#------------------------------------------------------------------------------
# The default setters
#------------------------------------------------------------------------------

def number_setter(v):
    return Number(v)

def string_setter(v):
    return String(v)

def simple_setter(v):
    return Function(v,[])

#------------------------------------------------------------------------------
# Define the predicate fields
#------------------------------------------------------------------------------

class BaseField(object):
    def __init__(self, getter, setter, default=None):
        self._getter = getter
        self._setter = setter
        self._default = default

class NumberField(BaseField):
    def __init__(self, getter=number_getter, setter=number_setter, default=None):
        super(NumberField,self).__init__(getter,setter,default)

class StringField(BaseField):
    def __init__(self, getter=string_getter, setter=string_setter, default=None):
        super(StringField,self).__init__(getter,setter,default)

class SimpleField(BaseField):
    def __init__(self, getter=simple_getter, setter=simple_setter, default=None):
        super(SimpleField,self).__init__(getter,setter,default)

#------------------------------------------------------------------------------
# functions to process and construct the Predicate classes and their attributes
# ------------------------------------------------------------------------------
def _predicate_name(name):
    return name[:1].lower() + name[1:] if name else ''

# The Meta attribute must be a class that defines predicate metadata
def _process_meta_attr(input_dct, meta_attr):
    if not inspect.isclass(meta_attr):
        raise TypeError("Meta attribute is not an inner class")
    maa = meta_attr.__dict__
#    maa = inspect.getmembers(meta_attr, lambda a: not(inspect.isroutine(a)))
    if "name" in maa: input_dct["name"] = maa["name"]

# Function that will be the predicate class constructor
def _predicate_constructor(self, **kwargs):
    class_name = type(self).__name__
    pred_name = self._metadata["name"]
    fields = set(self._fields.keys())

    invalids = [ k for k in kwargs if k not in fields ]
    if invalids:
        raise ValueError(("Arguments {} are not valid fields "
                          "of {}".format(invalids,class_name)))

    # Construct the clingo function arguments
    pred_args = []
    for field_name, field_defn in self._fields.items():
        if field_name not in kwargs:
            if not field_defn._default:
                raise ValueError(("Unspecified field {} has no "
                                  "default value".format(field_name)))
            pred_args.append(field_defn._setter(field_defn._default))
        else:
            pred_args.append(field_defn._setter(kwargs[field_name]))

    # Create the clingo symbol object
    self._symbol = Function(pred_name, pred_args)

# Create a functor that gets the value of a field.
def _make_field_functor(field_defn, idx):
    def get_value(self):
        return field_defn._getter(self._symbol.arguments[idx])
    return get_value

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
class PredicateMeta(type):
    fields = [ NumberField ]

    def __new__(meta, name, bases, dct):
        if name == "BasePredicate":
            return super(PredicateMeta, meta).__new__(meta, name, bases, dct)

#        print("-----------------------------")
#        print("NEW CLASS: {} = {}".format(name, meta))
#        print("BASES: {}".format(bases))
#        print("DICT: {}".format(dct))

        pred_metadata = { "name" : _predicate_name(name) }
        if "Meta" in dct: _process_meta_attr(pred_metadata, dct["Meta"])
#        print("PREDICATE METADATA = {}".format(pred_metadata))

        pred_fields = collections.OrderedDict()
        idx = 0
        for fname, fdefn in dct.items():
            if not issubclass(type(fdefn), BaseField): continue
            pred_fields[fname] = (fdefn)
            dct[fname] = property(_make_field_functor(fdefn,idx))
            idx += 1
#        print("NEW FIELDS: {}".format(pred_fields))

        dct["_metadata"] = pred_metadata
        dct["_fields"] = pred_fields
        dct["__init__"] = _predicate_constructor

        return super(PredicateMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# A base predicate that all predicate declarations must inherit from. The
# Metaclass creates the magic to create the fields and the underlying clingo
# symbol object.
# ------------------------------------------------------------------------------

class BasePredicate(object, metaclass=PredicateMeta):

    #--------------------------------------------------------------------------
    # Return the underlying clingo symbol object
    #--------------------------------------------------------------------------
    @property
    def raw(self):
        return self._symbol

    #--------------------------------------------------------------------------
    # Add the predicate instance to a Control object
    #--------------------------------------------------------------------------
    def insert(self, prg):
        
        pass

    #--------------------------------------------------------------------------
    # Set the external status of the predicate instance
    #--------------------------------------------------------------------------
    def external_true(self, prg):
        prg.assign_external(self.raw, True)

    def external_false(self, prg):
        prg.assign_external(self.raw, False)

    def external_release(self, prg):
        prg.release_external(self.raw)



#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

