#-----------------------------------------------------------------------------
# ORM provides a Object Relational Mapper type model for specifying non-logical
# symbols (ie., predicates and terms)
# ------------------------------------------------------------------------------

#import logging
#import os
import io
import inspect
import operator
import collections
import bisect
import abc
import clingo

__version__ = '0.1.0'
__all__ = [
    'IntegerField',
    'StringField',
    'ConstantField',
    'ComplexField',
    'Field',
    'NonLogicalSymbol',
    'Predicate',
    'ComplexTerm',
    'Comparator',
    'Select',
    'FactBase',
    'integer_cltopy',
    'string_cltopy',
    'constant_cltopy',
    'integer_pytocl',
    'string_pytocl',
    'constant_pytocl',
    'integer_unifies',
    'string_unifies',
    'constant_unifies',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'not_',
    'and_',
    'or_',
    'fact_generator',
    'control_add_facts',
    'control_assign_external',
    'control_release_external',
    'model_contains',
    'model_facts'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
#g_logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
# A _classproperty decorator. (see https://stackoverflow.com/questions/3203286/how-to-create-a-read-only-class-property-in-python)
#------------------------------------------------------------------------------
class _classproperty(object):
    def __init__(self, getter):
        self.getter= getter
    def __get__(self, instance, owner):
        return self.getter(owner)

#------------------------------------------------------------------------------
# Convert different clingo symbol objects to the appropriate python type
#------------------------------------------------------------------------------

def integer_cltopy(term):
    if term.type != clingo.SymbolType.Number:
        raise TypeError("Object {0} is not a Number term")
    return term.number

def string_cltopy(term):
    if term.type != clingo.SymbolType.String:
        raise TypeError("Object {0} is not a String term")
    return term.string

def constant_cltopy(term):
    if   (term.type != clingo.SymbolType.Function or
          not term.name or len(term.arguments) != 0):
        raise TypeError("Object {0} is not a Simple term")
    return term.name

#------------------------------------------------------------------------------
# Convert python object to the approproate clingo Symbol object
#------------------------------------------------------------------------------

def integer_pytocl(v):
    return clingo.Number(v)

def string_pytocl(v):
    return clingo.String(v)

def constant_pytocl(v):
    return clingo.Function(v,[])

#------------------------------------------------------------------------------
# check that a symbol unifies with the different field types
#------------------------------------------------------------------------------

def integer_unifies(term):
    if term.type != clingo.SymbolType.Number: return False
    return True

def string_unifies(term):
    if term.type != clingo.SymbolType.String: return False
    return True

def constant_unifies(term):
    if term.type != clingo.SymbolType.Function: return False
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
        super(IntegerField,self).__init__(inner_cltopy=integer_cltopy,
                                          inner_pytocl=integer_pytocl,
                                          unifies=integer_unifies,
                                          outfunc=outfunc,infunc=infunc,
                                          default=default)

class StringField(SimpleField):
    def __init__(self, outfunc=None, infunc=None, default=None):
        super(StringField,self).__init__(inner_cltopy=string_cltopy,
                                         inner_pytocl=string_pytocl,
                                         unifies=string_unifies,
                                         outfunc=outfunc,infunc=infunc,
                                         default=default)

class ConstantField(SimpleField):
    def __init__(self, outfunc=None, infunc=None, default=None):
        super(ConstantField,self).__init__(inner_cltopy=constant_cltopy,
                                           inner_pytocl=constant_pytocl,
                                           unifies=constant_unifies,
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
        return value.symbol

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
# Field - similar to a property but with overloaded comparison operator
# that build a query so that we can perform lazy evaluation for querying.
#------------------------------------------------------------------------------

class Field(abc.ABC):

    @abc.abstractmethod
    def __get__(self, instance, owner=None):
        pass

    @abc.abstractmethod
    def __hash__(self):
        pass

    @abc.abstractmethod
    def __eq__(self, other):
        pass

    @abc.abstractmethod
    def __ne__(self, other):
        pass

    @abc.abstractmethod
    def __lt__(self, other):
        pass

    @abc.abstractmethod
    def __le__(self, other):
        pass

    @abc.abstractmethod
    def __gt__(self, other):
        pass

    @abc.abstractmethod
    def __ge__(self, other):
        pass

#------------------------------------------------------------------------------
# Implementation of a Field
# ------------------------------------------------------------------------------
class _Field(Field):
    def __init__(self, field_name, field_index, field_defn, no_setter=True):
        self._no_setter=no_setter
        self._field_name = field_name
        self._field_index = field_index
        self._field_defn = field_defn
        self._parent_cls = None

    @property
    def field_name(self): return self._field_name

    @property
    def field_index(self): return self._field_index

    @property
    def field_defn(self): return self._field_defn

    @property
    def parent(self): return self._parent_cls

    def set_parent(self, parent_cls):
        self._parent_cls = parent_cls

    def __get__(self, instance, owner=None):
        if not instance: return self
        if not isinstance(instance, self._parent_cls):
            raise TypeError("field accessor doesn't match instance type")
        return instance._field_values[self._field_name]
#            return field_defn.cltopy(self._symbol.arguments[idx])

    def __set__(self, instance, value):
        if not self._no_setter:
            raise AttributeError("can't set attribute")
        if not isinstance(instance, self._parent_cls):
            raise TypeError("field accessor doesn't match instance type")
        instance._field_values[self._field_name] = value

    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return _FieldComparator(operator.eq, self, other)
    def __ne__(self, other):
        return _FieldComparator(operator.ne, self, other)
    def __lt__(self, other):
        return _FieldComparator(operator.lt, self, other)
    def __le__(self, other):
        return _FieldComparator(operator.le, self, other)
    def __gt__(self, other):
        return _FieldComparator(operator.gt, self, other)
    def __ge__(self, other):
        return _FieldComparator(operator.ge, self, other)

    def __str__(self):
        return "{}.{}".format(self.parent.__name__,self.field_name)
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
    self._symbol = symbol
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
    self._symbol = self._generate_symbol()

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
    self._symbol = self._generate_symbol()

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
# Metaclass constructor support functions to create the fields
#------------------------------------------------------------------------------

# Function to check that an object satisfies the requirements of a field.
# Must have functions cltopy and pytocl, and a property default
def _is_field_defn(obj):
    try:
        if obj.is_field_defn: return True
    except AttributeError:
        pass
    return False

# build the metadata for the NonLogicalSymbol
def _make_nls_metadata(class_name, dct):

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

    reserved = set(["meta", "symbol", "clone"])
    # Generate the field definitions
    field_defns = collections.OrderedDict()
    idx = 0
    for field_name, field_defn in dct.items():
        if not _is_field_defn(field_defn): continue
        if field_name.startswith('_'):
            raise ValueError(("Error: field name starts with an "
                              "underscore: {}").format(field_name))
        if field_name in reserved:
            raise ValueError(("Error: invalid field name: '{}' "
                              "is a reserved keyword").format(field_name))
        field_defns[field_name] = field_defn
        idx += 1

    # Now create the MetaData object
    return NonLogicalSymbol.MetaData(name=name,field_defns=field_defns)

#------------------------------------------------------------------------------
# A Metaclass for the NonLogicalSymbol base class
#------------------------------------------------------------------------------
class _NonLogicalSymbolMeta(type):

    #--------------------------------------------------------------------------
    # Support member fuctions
    #--------------------------------------------------------------------------


    #--------------------------------------------------------------------------
    # Allocate the new metaclass
    #--------------------------------------------------------------------------
    def __new__(meta, name, bases, dct):
        if name == "NonLogicalSymbol":
            return super(_NonLogicalSymbolMeta, meta).__new__(meta, name, bases, dct)

        md = _make_nls_metadata(name, dct)

        # Set the _meta attribute and constructor
        dct["_meta"] = md
        dct["__init__"] = _nls_constructor

        # Create a property attribute corresponding to each field name while
        # also making the values indexable.
        field_accessors = []
        for idx, (field_name, field_defn) in enumerate(md.field_defns.items()):
            fa = _Field(field_name, idx, field_defn)
            dct[field_name] = fa
            field_accessors.append(fa)
        dct["_field_accessors"] = tuple(field_accessors)

        return super(_NonLogicalSymbolMeta, meta).__new__(meta, name, bases, dct)

    def __init__(cls, name, bases, dct):
        if name == "NonLogicalSymbol":
            return super(_NonLogicalSymbolMeta, cls).__init__(name, bases, dct)

        md = dct["_meta"]
        # The property attribute for each field can only be created in __new__
        # but the class itself does not get created until after __new__. Hence
        # we have to set the pointer within the field back to the this class
        # here.
        for idx, (field_name, field_defn) in enumerate(md.field_defns.items()):
            dct[field_name].set_parent(cls)

#        print("CLS: {}".format(cls) + "I am still called '" + name +"'")
        return super(_NonLogicalSymbolMeta, cls).__init__(name, bases, dct)

#------------------------------------------------------------------------------
# A base non-logical symbol that all predicate/term declarations must inherit
# from. The Metaclass creates the magic to create the fields and the underlying
# clingo symbol object.
# ------------------------------------------------------------------------------

class NonLogicalSymbol(object, metaclass=_NonLogicalSymbolMeta):

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
    # Properties and functions the NonLogicalSymbol
    #--------------------------------------------------------------------------

    # Get the underlying clingo symbol object
    @property
    def symbol(self):
#        return self._symbol
        return self._generate_symbol()

    # Recompute the symbol object from the stored field objects
    def _generate_symbol(self):
        pred_args = []
        for field_name, field_defn in self.meta.field_defns.items():
            pred_args.append(field_defn.pytocl(self._field_values[field_name]))
        # Create the clingo symbol object
        return clingo.Function(self.meta.name, pred_args)

    # Clone the object with some differences
    def clone(self, **kwargs):
        # Sanity check
        clonekeys = set(kwargs.keys())
        objkeys = set(self.meta.field_defns.keys())
        diffkeys = clonekeys - objkeys
        if diffkeys:
            raise ValueError("Unknown field names: {}".format(diffkeys))

        # Get the arguments for the new object
        cloneargs = {}
        for field_name, field_defn in self.meta.field_defns.items():
            if field_name in kwargs: cloneargs[field_name] = kwargs[field_name]
            else: cloneargs[field_name] = kwargs[field_name] = self._field_values[field_name]

        # Create the new object
        return type(self)(**cloneargs)

    #--------------------------------------------------------------------------
    # Class methods and properties
    #--------------------------------------------------------------------------

    # Get the metadata for the NonLogicalSymbol definition
    @_classproperty
    def meta(cls):
        return cls._meta

    # Returns whether or not a Symbol can unify with this NonLogicalSymbol
    @classmethod
    def _unifies(cls, symbol):
        if symbol.type != clingo.SymbolType.Function: return False

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
        return self._field_accessors[idx].__get__(self)

    def __setitem__(self, idx,v):
        return self._field_accessors[idx].__set__(self,v)

    #--------------------------------------------------------------------------
    # Overloaded operators
    #--------------------------------------------------------------------------
    def __eq__(self, other):
        self_symbol = self.symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.symbol
            return self_symbol == other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol == other
        else:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        self_symbol = self.symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.symbol
            return self_symbol < other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol < other
        else:
            return NotImplemented

    def __ge__(self, other):
        result = self.__lt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __gt__(self, other):
        self_symbol = self.symbol
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.symbol
            return self_symbol > other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol > other
        else:
            return NotImplemented

    def __le__(self, other):
        result = self.__gt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return self.symbol.__hash__()

    def __str__(self):
        self_symbol = self.symbol
        return str(self_symbol)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Convenience aliases for NonLogicalSymbol - this makes it more intuitive
#------------------------------------------------------------------------------
Predicate=NonLogicalSymbol
ComplexTerm=NonLogicalSymbol

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Generate facts from an input array of Symbols.  The unifiers argument is
# contains the names of predicate classes to unify against (order matters) and
# symbols contains the list of raw clingo.Symbol objects.
# ------------------------------------------------------------------------------

def fact_generator(unifiers, symbols):
    def unify(cls, r):
        try:
            return cls._unify(r)
        except ValueError:
            return None

    types = {(cls.meta.name, cls.meta.arity) : cls for cls in unifiers}
    for raw in symbols:
        cls = types.get((raw.name, len(raw.arguments)))
        if not cls: continue
        f = unify(cls,raw)
        if f: yield f


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Fact comparator: is a function that determines if a fact (i.e., predicate
# instance) satisfies some property or condition. Any function that takes a
# single fact as a argument and returns a bool is a fact comparator. However, we
# define a few special types.
# ------------------------------------------------------------------------------

# A helper function to return a simplified version of a fact comparator
def _simplify_fact_comparator(comparator):
    try:
        return comparator.simplified()
    except:
        if isinstance(comparator, bool):
            return _StaticComparator(comparator)
        return comparator


# A helper function to return the list of field comparators of a comparator
def _get_field_comparators(comparator):
    try:
        return comparator.field_comparators
    except:
        if isinstance(comparator, _FieldComparator):
            return [comparator]
        return []

#------------------------------------------------------------------------------
# Placeholder allows for variable substituion of a query
#------------------------------------------------------------------------------
class Placeholder(abc.ABC):
    pass

class _Placeholder(Placeholder):
    def __init__(self, name, default=None):
        self._name = name
        self._default = default
        self._value = None
    @property
    def name(self):
        return self._name
    def reset(self):
        self._value = self._default
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, v):
        self._value = v

def ph_(name,default=None):
    return _Placeholder(name,default)
def ph1_(): return _Placeholder(0)
def ph2_(): return _Placeholder(1)
def ph3_(): return _Placeholder(2)
def ph4_(): return _Placeholder(3)

#------------------------------------------------------------------------------
# A Comparator is a boolean functor that takes a fact instance and returns
# whether it satisfies some condition.
# ------------------------------------------------------------------------------

class Comparator(abc.ABC):

    @abc.abstractmethod
    def __call__(self,fact):
        pass

#------------------------------------------------------------------------------
# A Fact comparator functor that returns a static value
#------------------------------------------------------------------------------

class _StaticComparator(Comparator):
    def __init__(self, value):
        self._value=bool(value)
    def __call__(self,fact):
        return self._value
    def simpified(self):
        return self
    @property
    def value(self):
        return self._value

#------------------------------------------------------------------------------
# A fact comparator functor that tests whether a fact satisfies a comparision
# with the value of some predicate's field.
#
# Note: instances of _FieldComparator are constructed by calling the comparison
# operator for Field objects.
# ------------------------------------------------------------------------------
class _FieldComparator(Comparator):
    def __init__(self, compop, arg1, arg2):
        self._compop = compop
        self._arg1 = arg1
        self._arg2 = arg2
        self._static = False

        # Comparison is trivial if:
        # 1) the objects are identical then it is a trivial comparison and
        # equivalent to checking if the operator satisfies a simple identity (eg., 1)
        # 2) neither argument is a field accessor
        if arg1 is arg2:
            self._static = True
            self._value = compop(1,1)
        elif not isinstance(arg1, _Field) and not isinstance(arg2, _Field):
            self._static = True
            self._value = compop(arg1,arg2)
        elif callable(self._arg2):
            self._arg2 = self._arg2()

    def __call__(self, fact):
        if self._static: return self._value
        try:
            def getargval(arg,fact):
                if isinstance(arg, _Field): return arg.__get__(fact)
                elif isinstance(arg, _Placeholder): return arg.value
                else: return arg

            v1 = getargval(self._arg1, fact)
            v2 = getargval(self._arg2, fact)
            return self._compop(v1,v2)
        except (KeyError, TypeError) as e:
            return False

    def simplified(self):
        if self._static: return _StaticComparator(self._value)
        return self

    def placeholders(self):
        tmp = []
        if isinstance(self._arg1, _Placeholder): tmp.append(self._arg1)
        if isinstance(self._arg2, _Placeholder): tmp.append(self._arg2)
        return tmp

    def indexable(self):
        if self._static: return None
        if not isinstance(self._arg1, _Field) or isinstance(self._arg2, _Field):
            return None
        return (self._arg1, self._compop, self._arg2)

    def __str__(self):
        if self._compop == operator.eq: opstr = "=="
        elif self._compop == operator.ne: opstr = "!="
        elif self._compop == operator.lt: opstr = "<"
        elif self._compop == operator.le: opstr = "<="
        elif self._compop == operator.gt: opstr = ">"
        elif self._compop == operator.et: opstr = ">="
        else: opstr = "<unknown>"

        return "{} {} {}".format(self._arg1, opstr, self._arg2)
#------------------------------------------------------------------------------
# A fact comparator that is a boolean operator over other Fact comparators
# ------------------------------------------------------------------------------

class _BoolComparator(Comparator):
    def __init__(self, boolop, *args):
        if boolop not in [operator.not_, operator.or_, operator.and_]:
            raise TypeError("non-boolean operator")
        if boolop == operator.not_ and len(args) != 1:
            raise IndexError("'not' operator expects exactly one argument")
        elif boolop != operator.not_ and len(args) <= 1:
            raise IndexError("bool operator expects more than one argument")

        self._boolop=boolop
        self._args = args

    def __call__(self, fact):
        if self._boolop == operator.not_:
            return operator.not_(self._args[0](fact))
        elif self._boolop == operator.and_:
            for a in self._args:
                if not a(fact): return False
            return True
        elif self._boolop == operator.or_:
            for a in self._args:
                if a(fact): return True
            return False
        raise ValueError("unsupported operator: {}".format(self._boolop))

    def simplified(self):
        newargs=[]
        # Try and simplify each argument
        for arg in self._args:
            sarg = _simplify_fact_comparator(arg)
            if isinstance(sarg, _StaticComparator):
                if self._boolop == operator.not_: return _StaticComparator(not sarg.value)
                if self._boolop == operator.and_ and not sarg.value: sarg
                if self._boolop == operator.or_ and sarg.value: sarg
            else:
                newargs.append(sarg)
        # Now see if we can simplify the combination of the arguments
        if not newargs:
            if self._boolop == operator.and_: return _StaticComparator(True)
            if self._boolop == operator.or_: return _StaticComparator(False)
        if self._boolop != operator.not_ and len(newargs) == 1:
            return newargs[0]
        # If we get here there then there is a real boolean comparison
        return _BoolComparator(self._boolop, *newargs)

    @property
    def boolop(self): return self._boolop

    @property
    def args(self): return self._args

# ------------------------------------------------------------------------------
# Functions to build _BoolComparator instances
# ------------------------------------------------------------------------------

def not_(*conditions):
    return _BoolComparator(operator.not_,*conditions)
def and_(*conditions):
    return _BoolComparator(operator.and_,*conditions)
def or_(*conditions):
    return _BoolComparator(operator.or_,*conditions)

#------------------------------------------------------------------------------
# A multimap
#------------------------------------------------------------------------------

class _MultiMap(object):
    def __init__(self):
        self._keylist = []
        self._key2values = {}

    def keys(self):
        return list(self._keylist)

    def keys_eq(self, key):
        if key in self._key2values: return [key]
        return []

    def keys_ne(self, key):
        posn1 = bisect.bisect_left(self._keylist, key)
        if posn1: left =  self._keylist[:posn1]
        else: left = []
        posn2 = bisect.bisect_right(self._keylist, key)
        if posn2: right = self._keylist[posn2:]
        else: right = []
        return left + right

    def keys_lt(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def keys_le(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def keys_gt(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    def keys_ge(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    def keys_op(self, op, key):
        if op == operator.eq: return self.keys_eq(key)
        elif op == operator.ne: return self.keys_ne(key)
        elif op == operator.lt: return self.keys_lt(key)
        elif op == operator.le: return self.keys_le(key)
        elif op == operator.gt: return self.keys_gt(key)
        elif op == operator.ge: return self.keys_ge(key)
        raise ValueError("unsupported operator")

    def clear(self):
        self._keylist = []
        self._key2values = {}

    #--------------------------------------------------------------------------
    # Overloaded index operator to access the values
    #--------------------------------------------------------------------------
    def __getitem__(self, key):
        return self._key2values[key]

    def __setitem__(self, key,v):
        if key not in self._key2values: self._key2values[key] = []
        self._key2values[key].append(v)
        posn = bisect.bisect_left(self._keylist, key)
        if len(self._keylist) > posn and self._keylist[posn] == key: return
        bisect.insort_left(self._keylist, key)

    def __delitem__(self, key):
        del self._key2values[key]
        posn = bisect.bisect_left(self._keylist, key)
        del self._keylist[posn]

    def __str__(self):
        tmp = ", ".join(["{} : {}".format(key, self._key2values[key]) for key in self._keylist])
        return "{{ {} }}".format(tmp)


#------------------------------------------------------------------------------
# Select is an interface query over a FactBase.
# ------------------------------------------------------------------------------

class Select(abc.ABC):

    @abc.abstractmethod
    def where(self, *expressions):
        pass

    @abc.abstractmethod
    def get(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def get_unique(self, *args, **kwargs):
        pass

#------------------------------------------------------------------------------
# Delete is an interface to perform a query delete from a FactBase.
# ------------------------------------------------------------------------------

class Delete(abc.ABC):

    @abc.abstractmethod
    def where(self, *expressions):
        pass

    @abc.abstractmethod
    def execute(self, *args, **kwargs):
        pass

#------------------------------------------------------------------------------
# A selection over a _FactMap
#------------------------------------------------------------------------------
class _Select(Select):
    def __init__(self, factmap):
        self._factmap = factmap
        self._index_priority = { f:p for (p,f) in enumerate(factmap.indexed_fields()) }
        self._where = None
        self._indexable = None
        self._name_to_ph = {}

    def where(self, *expressions):
        if self._where:
            raise ValueError("trying to specify multiple where clauses")
        if not expressions:
            self._where = None
        elif len(expressions) == 1:
            self._where = _simplify_fact_comparator(expressions[0])
        else:
            self._where = _simplify_fact_comparator(and_(*expressions))

        self._indexable = self._primary_search(self._where)
        self._name_to_ph = { p.name : p for p in self._get_placeholders(self._where) }
        return self

    def _primary_search(self, where):
        def validate_indexable(indexable):
            if not indexable: return None
            if indexable[0] not in self._index_priority: return None
            return indexable

        if isinstance(where, _FieldComparator):
            return validate_indexable(where.indexable())
        indexable = None
        if isinstance(where, _BoolComparator) and where.boolop == operator.and_:
            for arg in where.args:
                tmp = self._primary_search(arg)
                if tmp:
                    if not indexable: indexable = tmp
                    elif self._index_priority[tmp[0]] < self._index_priority[indexable[0]]:
                        indexable = tmp
        return indexable

    def  _get_placeholders(self, where):
        if isinstance(where, _FieldComparator): return where.placeholders()
        tmp = []
        if isinstance(where, _BoolComparator):
            for arg in where.args:
                tmp.extend(self._get_placeholders(arg))
        return tmp

    def _set_placeholder_values(self, *args, **kwargs):
        if not self._name_to_ph and not kwargs and not args: return

        # Cannot specify both keyword and positional arguments
        if args and kwargs:
                raise ValueError("cannot specify both positional and keyword arguments")

        # If variable length positional arguments are used then there must be a
        # matching placeholder with a matching index.
        if args:
            if len(args) != len(self._name_to_ph):
                raise ValueError("Mismatch in the number of placeholder arguments")
            for idx,arg in enumerate(args):
                ph = self._name_to_ph.get(idx,None)
                if not ph:
                    raise ValueError(("no placeholder for positional argument "
                                      "index: {}").format(idx))
                ph.value = arg
            return

        # Sanity check that argument names match placeholders
        for n in kwargs.keys():
            if not self._name_to_ph or n not in self._name_to_ph:
                raise ValueError("unknown placeholder name: {}".format(n))

        # Set the placeholder values based on the keyword arguments or the default
        for n, ph in self._name_to_ph.items():
            v = kwargs.get(n, None)
            if v is None: ph.reset()
            else: ph.value = v
            if ph.value is None:
                raise ValueError("no value for placeholder: {}".format(n))

#    @property
    def _debug(self):
        return self._indexable

    def get(self, *args, **kwargs):
        # Function to get a value - resolving placeholder if necessary
        def get_value(v):
            if isinstance(v, _Placeholder): return v.value
            return v

        # Set any placeholder values
        self._set_placeholder_values(*args, **kwargs)

        # If there is no index test all instances else use the index
        if not self._indexable:
            for f in self._factmap.facts():
                if not self._where: yield f
                elif self._where and self._where(f): yield(f)
        else:
            mmap=self._factmap.get_facts_multimap(self._indexable[0])
            for key in mmap.keys_op(self._indexable[1], get_value(self._indexable[2])):
                for f in mmap[key]:
                    if self._where(f): yield f

    def get_unique(self, *args, **kwargs):
        count=0
        fact=None
        for f in self.get(*args, **kwargs):
            fact=f
            count += 1
            if count > 1:
                raise ValueError("Multiple facts found - exactly one expected")
        if count == 0:
            raise ValueError("No facts found - exactly one expected")
        return fact


#------------------------------------------------------------------------------
# A map for facts of the same type - Indexes can be built to allow for fast
# lookups based on a field value. The order that the fields are specified in the
# index matters as it determines the priority of the index.
# ------------------------------------------------------------------------------

class _FactMap(object):
    def __init__(self, index=[]):
        self._allfacts = []
        if len(index) == 0:
            self._mmaps = None
        else:
            self._mmaps = collections.OrderedDict( (f, _MultiMap()) for f in index )

    def add(self, fact):
        self._allfacts.append(fact)
        if self._mmaps:
            for field, mmap in self._mmaps.items():
                mmap[field.__get__(fact)] = fact

    def indexed_fields(self):
        return self._mmaps.keys() if self._mmaps else []

    def get_facts_multimap(self, field):
        return self._mmaps[field]

    def facts(self):
        return self._allfacts

    def clear(self):
        self._allfacts.clear()
        if self._mmaps:
            for field, mmap in self._mmaps.items():
                mmap.clear()

    def select(self):
        return _Select(self)

    def asp_str(self):
        out = io.StringIO()
        for f in self._allfacts:
            print("{}.".format(f), file=out)
        data = out.getvalue()
        out.close()
        return data

    def __str__(self):
        self.asp_str()


#------------------------------------------------------------------------------
# Functions to be added to FactBase class or sub-class definitions
#------------------------------------------------------------------------------

def _fb_base_constructor(self, facts=[], delayed_init=False):
    _fb_subclass_constructor(self, facts=facts, delayed_init=delayed_init)

def _fb_subclass_constructor(self, facts=None, symbols=None, delayed_init=False):
    if facts is not None and symbols is not None:
        raise ValueError("'facts' and 'symbols' are mutually exclusive arguments")
    if not delayed_init:
        self._init(facts=facts, symbols=symbols)
    else:
        self._delayed_init = lambda : self._init(facts=facts, symbols=symbols)


def _fb_base_add(self, fact=None,facts=None):
    # Always check if we have delayed initialisation
    if self._delayed_init: self.delayed_init()

    count = 0
    if fact is not None: count += 1
    if facts is not None: count += 1
    if count != 1:
        raise ValueError(("Must specify exactly one of a "
                          "'facts' list, or a 'symbols' list"))
    self._add(fact=fact,facts=facts)

def _fb_subclass_add(self, fact=None,facts=None,symbols=None):
    # Always check if we have delayed initialisation
    if self._delayed_init: self.delayed_init()

    count = 0
    if fact is not None: count += 1
    if facts is not None: count += 1
    if symbols is not None: count += 1
    if count != 1:
        raise ValueError(("Must specify exactly one of a fact argument, a "
                          "'facts' list, or a 'symbols' list"))

    self._add(fact=fact,facts=facts,symbols=symbols)

#------------------------------------------------------------------------------
# A Metaclass for FactBase
#------------------------------------------------------------------------------

class _FactBaseMeta(type):
    #--------------------------------------------------------------------------
    # Allocate the new metaclass
    #--------------------------------------------------------------------------
    def __new__(meta, name, bases, dct):
        plistname = "predicates"
        ilistname = "indexes"

        # Creating the FactBase class itself
        if name == "FactBase":
            dct[plistname] = []
            dct[ilistname] = []
            dct["__init__"] = _fb_base_constructor
            dct["add"] = _fb_base_add
            return super(_FactBaseMeta, meta).__new__(meta, name, bases, dct)

        # Cumulatively inherits the predicates and indexes from the base classes -
        # which we can then override.
        # use ordered dict to preserve ordering
        p_oset = collections.OrderedDict()
        i_oset = collections.OrderedDict()
        for bc in bases:
            if not issubclass(bc, FactBase): continue
            for p in bc.predicates: p_oset[p] = p
            for i in bc.indexes: i_oset[i] = i
        if plistname not in dct:
            dct[plistname] = [ p for p,_ in p_oset.items() ]
        if ilistname not in dct:
            dct[ilistname] = [ i for i,_ in i_oset.items() ]

        # If we're dealing with a subclass then validate the specified
        # predicates and indexes and add the sub-class constructor

        # Make sure "predicates" is defined and is a non-empty list
        pset = set()
        if plistname not in dct:
            raise TypeError("Error: class definition missing 'predicates' specification")
        if not dct[plistname]:
            raise TypeError("Error: class definition empty 'predicates' specification")
        for pitem in dct[plistname]:
            pset.add(pitem)
            if not issubclass(pitem, Predicate):
                raise TypeError("Error: non-predicate class {} in list".format(pitem))

        # Validate the "indexes" list (and define if if it doesn't exist)
        if ilistname not in dct: dct[ilistname] = []
        for iitem in dct[ilistname]:
            if iitem.parent not in pset:
                raise TypeError(("Error: parent of index {} item not in the predicates "
                                  "list").format(iitem))
        dct["__init__"] = _fb_subclass_constructor
        dct["add"] = _fb_subclass_add
        return super(_FactBaseMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# A FactBase consisting of facts of different types
#------------------------------------------------------------------------------

class FactBase(object, metaclass=_FactBaseMeta):

    #--------------------------------------------------------------------------
    # Internal member functions
    #--------------------------------------------------------------------------

    # A special purpose initialiser so that we can do delayed initialisation
    def _init(self, facts=None, symbols=None):

        # Create _FactMaps for the predicate types with indexed fields
        grouped = {}
        for field in self.indexes:
            if field.parent not in grouped: grouped[field.parent] = []
            grouped[field.parent].append(field)
        for p in self.predicates:
            if p not in grouped: grouped[p] = []
        self._factmaps = { pt : _FactMap(fs) for pt, fs in grouped.items() }

        # add the facts
        self._add(facts=facts, symbols=symbols)

        # flag that initialisation has taken place
        self._delayed_init = None

    def _add(self, fact=None,facts=None,symbols=None):
        if fact is not None: self._add_fact(fact)
        elif facts is not None:
            for f in facts: self._add_fact(f)
        elif symbols is not None:
            for f in fact_generator(self.predicates, symbols):
                self._add_fact(f)

    def _add_fact(self, fact):
        predicate_cls = type(fact)
        if not issubclass(predicate_cls,Predicate):
            raise TypeError("type of object {} is not a Predicate subclass".format(fact))
        if predicate_cls not in self._factmaps: self._factmaps[predicate_cls] = _FactMap()
        self._factmaps[predicate_cls].add(fact)


    #--------------------------------------------------------------------------
    # External member functions
    #--------------------------------------------------------------------------

    def select(self, predicate_cls):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        # If no predicate class exists then create one on the basis that facts
        # of this class may be inserted at some future point.
        if predicate_cls not in self._factmaps:
            self._factmaps[predicate_cls] = _FactMap()
        return self._factmaps[predicate_cls].select()

    def predicate_types(self):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        return set(self._factmaps.keys())

    def clear(self):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        self._symbols = None

        for pt, fm in self._factmaps.items():
            fm.clear()

    def facts(self):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        fcts = []
        for fm in self._factmaps.values():
            fcts.extend(fm.facts())
        return fcts

    def asp_str(self):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        out = io.StringIO()
        for fm in self._factmaps.values():
            print("{}".format(fm.asp_str()), file=out)
        data = out.getvalue()
        out.close()
        return data

    def __str__(self):
        return self.asp_str()

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Functions that operate on a clingo Control object
#------------------------------------------------------------------------------

# Add the facts in a FactBase
def control_add_facts(ctrl, factbase):
    with ctrl.builder() as b:
        clingo.parse_program(factbase.asp_str(), lambda stmt: b.add(stmt))

# assign/release externals for a NonLogicalSymbol object or a Clingo Symbol
def control_assign_external(ctrl, fact, truth):
    if isinstance(fact, NonLogicalSymbol):
        ctrl.assign_external(fact.symbol, truth)
    else:
        ctrl.assign_external(fact, truth)

def control_release_external(ctrl, fact):
    if isinstance(fact, NonLogicalSymbol):
        ctrl.release_external(fact.symbol)
    else:
        ctrl.release_external(fact)

#------------------------------------------------------------------------------
# Functions that operator on a clingo Model object
#------------------------------------------------------------------------------

def model_contains(model, fact):
    if isinstance(fact, NonLogicalSymbol):
        return model.contains(fact.symbol)
    return model.contains(fact)

def model_facts(model, factbase, atoms=False, terms=False, shown=False):
#    symbols=[ f for f in fact_generator(factbase.predicates,\
#              model.symbols(atoms=atoms,terms=terms,shown=shown))]
    return factbase(symbols=model.symbols(atoms=atoms,terms=terms,shown=shown),
                    delayed_init=True)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

