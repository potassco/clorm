#-----------------------------------------------------------------------------
# ORM provides a Object Relational Mapper type model for specifying non-logical
# symbols (ie., predicates and terms)
# ------------------------------------------------------------------------------

#import logging
#import os
import io
import contextlib
import inspect
import operator
import collections
import bisect
import abc
import functools
import clingo

__all__ = [
    'RawField',
    'IntegerField',
    'StringField',
    'ConstantField',
    'Field',
    'Placeholder',
    'NonLogicalSymbol',
    'Predicate',
    'ComplexTerm',
    'Comparator',
    'Select',
    'Delete',
    'FactBase',
    'FactBaseHelper',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'not_',
    'and_',
    'or_',
    'Signature'
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
# RawField class captures the definition of a term between python and clingo. It is
# not meant to be instantiated.
# ------------------------------------------------------------------------------

def _make_pytocl(fn):
    def _pytocl(cls, v):
        if cls._parentclass:
            return cls._parentclass.pytocl(fn(v))
        return fn(v)
    return _pytocl

def _make_cltopy(fn):
    def _cltopy(cls, v):
        if cls._parentclass:
            return fn(cls._parentclass.cltopy(v))
        return fn(v)
    return _cltopy

def _sfm_constructor(self, default=None, index=False):
    """Default values"""
    self._default = default
    self._index = index

class _RawFieldMeta(type):
    def __new__(meta, name, bases, dct):

        # Add a default initialiser if one is not already defined
        if "__init__" not in dct:
            dct["__init__"] = _sfm_constructor

        if name == "RawField":
            dct["_parentclass"] = None
            return super(_RawFieldMeta, meta).__new__(meta, name, bases, dct)

        for key in [ "cltopy", "pytocl" ]:
            if key in dct and not callable(dct[key]):
                raise AttributeError("Definition of {} is not callable".format(key))

        parents = [ b for b in bases if issubclass(b, RawField)]
        if len(parents) == 0:
            raise TypeError("Internal bug: number of RawField bases is 0!")
        if len(parents) > 1:
            raise TypeError("Multiple RawField sub-class inheritance forbidden")
        dct["_parentclass"] = parents[0]

        # When a conversion is not specified raise a NotImplementedError
        def _raise_nie(cls,v):
            raise NotImplementedError("No implemented conversion")

        if "cltopy" in dct:
            dct["cltopy"] = classmethod(_make_cltopy(dct["cltopy"]))
        else:
            dct["cltopy"] = classmethod(_raise_nie)

        if "pytocl" in dct:
            dct["pytocl"] = classmethod(_make_pytocl(dct["pytocl"]))
        else:
            dct["pytocl"] = classmethod(_raise_nie)

        return super(_RawFieldMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# Field definitions. All fields have the functions: pytocl, cltopy,
# and unifies, and the property: default
# ------------------------------------------------------------------------------

class RawField(object, metaclass=_RawFieldMeta):
    """A class that represents a field that correspond to logical terms.

    A field is typically used as part of a ``ComplexTerm`` or ``Predicate``
    definition. It defines the data type of an ASP term and provides functions
    for translating the term to a more convenient Python type.

    It contains two class functions ``cltopy`` and ``pytocl`` that implement the
    translation from Clingo to Python and Python to Clingo respectively. For
    ``RawField`` these functions simply pass the values straight though, however
    ``RawField`` can be sub-classed to build a chain of
    translations. ``StringField``, ``IntegerField``, and ``ConstantField`` are
    predefined sub-classes that provide translations for the ASP simple terms;
    *string*, *integer* and *constant*.

    To sub-class RawField (or one of its sub-classes) simply specify ``cltopy``
    and ``pytocl`` functions that take an input and perform some translation to
    an output format.

    Example:
       .. code-block:: python

           import datetime

           class DateField(StringField):
                     pytocl = lambda dt: dt.strftime("%Y%m%d")
                     cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()


       Because ``DateField`` sub-classes ``StringField``, rather than
       sub-classing ``RawField`` directly, it forms a longer data translation
       chain:

              ASP Symbol object -- RawField -- StringField -- date object

       Here the ``DateField.cltopy`` is called at the end of the chain of
       translations, so it expects a Python string object as input and outputs a
       date object. ``DateField.pytocl`` does the opposite and inputs a date
       object and is must output a Python string object.

    Args:
      default: A default value when instantiating a ``Predicate`` or
        ``ComplexTerm`` object. Defaults to ``None``.
      index (bool): Determine if this field should be indexed by default in a
        ``FactBase```. Defaults to ``False``.

    """

    @classmethod
    def cltopy(cls, v):
        """Called when translating data from a Clingo to Python"""
        return v

    @classmethod
    def pytocl(cls, v):
        """Called when translating data from a Python to Clingo"""
        return v

    @classmethod
    def unifies(cls, v):
        """Returns whether a `Clingo.Symbol` can be unified with this type of term"""
        try:
            cls.cltopy(v)
        except TypeError:
            return False
        return True

    @property
    def default(self):
        """Returns the specified default value for the term (or None)"""
        return self._default

    @property
    def index(self):
        """Returns whether this field should be indexed by default in a `FactBase`"""
        return self._index

#------------------------------------------------------------------------------
# The three RawField
#------------------------------------------------------------------------------

class StringField(RawField):
    """A field to convert between a Clingo.String object and a Python string."""
    def _string_cltopy(symbol):
        if symbol.type != clingo.SymbolType.String:
            raise TypeError("Object {0} is not a String symbol")
        return symbol.string

    cltopy = _string_cltopy
    pytocl = lambda v: clingo.String(v)

class IntegerField(RawField):
    """A field to convert between a Clingo.Number object and a Python integer."""
    def _integer_cltopy(symbol):
        if symbol.type != clingo.SymbolType.Number:
            raise TypeError("Object {0} is not a Number symbol")
        return symbol.number

    cltopy = _integer_cltopy
    pytocl = lambda v: clingo.Number(v)

class ConstantField(RawField):
    """A field to convert between a simple Clingo.Function object and a Python
    string.

    """
    def _constant_cltopy(symbol):
        if   (symbol.type != clingo.SymbolType.Function or
              not symbol.name or len(symbol.arguments) != 0):
            raise TypeError("Object {0} is not a Simple symbol")
        return symbol.name

    cltopy = _constant_cltopy
    pytocl = lambda v: clingo.Function(v,[])

#------------------------------------------------------------------------------
# Field - a Pyton descriptor (similar to a property) but with overloaded
# comparison operator that build a query so that we can perform lazy evaluation
# for querying.
# ------------------------------------------------------------------------------

class Field(abc.ABC):
    """Abstract class defining a field instance in a ``Predicate`` or
    ``ComplexTerm``.

    While the field is specified by the RawField sub-classes, when
    the ``Predicate`` or ``ComplexTerm`` class is actually created a ``Field``
    object is instantiated to handle extracting the actual term data from the
    underlying ``Clingo.Symbol``.

    The ``Field`` object is also referenced when building queries.

    """

    @abc.abstractmethod
    def __get__(self, instance, owner=None):
        """Overload of the Python *descriptor* to access the data values"""
        pass

    @abc.abstractmethod
    def __hash__(self):
        """Overload of the Python hash value generation"""
        pass

    @abc.abstractmethod
    def __eq__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

    @abc.abstractmethod
    def __ne__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

    @abc.abstractmethod
    def __lt__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

    @abc.abstractmethod
    def __le__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

    @abc.abstractmethod
    def __gt__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

    @abc.abstractmethod
    def __ge__(self, other):
        """Boolean operator is overloaded to return a ``Comparator`` object"""
        pass

#------------------------------------------------------------------------------
# Implementation of a Field
# ------------------------------------------------------------------------------
class _Field(Field):
    def __init__(self, term_name, term_index, term_defn, no_setter=True):
        self._no_setter=no_setter
        self._term_name = term_name
        self._term_index = term_index
        self._term_defn = term_defn
        self._parent_cls = None

    @property
    def term_name(self): return self._term_name

    @property
    def term_index(self): return self._term_index

    @property
    def term_defn(self): return self._term_defn

    @property
    def parent(self): return self._parent_cls

    def set_parent(self, parent_cls):
        self._parent_cls = parent_cls

    def __get__(self, instance, owner=None):
        if not instance: return self
        if not isinstance(instance, self._parent_cls):
            raise TypeError(("term {} doesn't match type "
                             "{}").format(self, type(instance).__name__))
        return instance._term_values[self._term_name]
#            return term_defn.cltopy(self._symbol.arguments[idx])

    def __set__(self, instance, value):
        if not self._no_setter:
            raise AttributeError("can't set attribute")
        if not isinstance(instance, self._parent_cls):
            raise TypeError("term accessor doesn't match instance type")
        instance._term_values[self._term_name] = value

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
        return "{}.{}".format(self.parent.__name__,self.term_name)
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
    symbol = kwargs["raw"]
    class_name = type(self).__name__
    if not self._unifies(symbol):
        raise ValueError(("Failed to unify symbol {} with "
                          "NonLogicalSymbol class {}").format(symbol, class_name))
    self._symbol = symbol
    for idx, (term_name, term_defn) in enumerate(self.meta.term_defns.items()):
        self._term_values[term_name] = term_defn.cltopy(symbol.arguments[idx])

# Construct a NonLogicalSymbol via the term keywords
def _nls_init_by_keyword_values(self, **kwargs):
    class_name = type(self).__name__
    pred_name = self.meta.name
    terms = set(self.meta.term_defns.keys())

    invalids = [ k for k in kwargs if k not in terms ]
    if invalids:
        raise ValueError(("Arguments {} are not valid terms "
                          "of {}".format(invalids,class_name)))

    # Construct the clingo function arguments
    for term_name, term_defn in self.meta.term_defns.items():
        if term_name not in kwargs:
            if not term_defn.default:
                raise ValueError(("Unspecified term {} has no "
                                  "default value".format(term_name)))
            self._term_values[term_name] = term_defn.default
        else:
            self._term_values[term_name] = kwargs[term_name]

    # Create the clingo symbol object
    self._symbol = self._generate_symbol()

# Construct a NonLogicalSymbol via the term keywords
def _nls_init_by_positional_values(self, *args):
    class_name = type(self).__name__
    pred_name = self.meta.name
    argc = len(args)
    arity = len(self.meta.term_defns)
    if argc != arity:
        return ValueError("Expected {} arguments but {} given".format(arity,argc))

    for idx, (term_name, term_defn) in enumerate(self.meta.term_defns.items()):
        self._term_values[term_name] = args[idx]

    # Create the clingo symbol object
    self._symbol = self._generate_symbol()

# Constructor for every NonLogicalSymbol sub-class
def _nls_constructor(self, *args, **kwargs):
    self._symbol = None
    self._term_values = {}
    if "raw" in kwargs:
        _nls_init_by_symbol(self, **kwargs)
    elif len(args) > 0:
        _nls_init_by_positional_values(self, *args)
    else:
        _nls_init_by_keyword_values(self, **kwargs)


#------------------------------------------------------------------------------
# Metaclass constructor support functions to create the terms
#------------------------------------------------------------------------------

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

    reserved = set(["meta", "raw", "clone", "Field"])

    # Generate the terms - NOTE: relies on dct being an OrderedDict()
    terms = []
    idx = 0
    for term_name, term_defn in dct.items():
        if not isinstance(term_defn, RawField): continue
        if term_name.startswith('_'):
            raise ValueError(("Error: term name starts with an "
                              "underscore: {}").format(term_name))
        if term_name in reserved:
            raise ValueError(("Error: invalid term name: '{}' "
                              "is a reserved keyword").format(term_name))

        term = _Field(term_name, idx, term_defn)
        dct[term_name] = term
        terms.append(term)
        idx += 1

    # Now create the MetaData object
    return NonLogicalSymbol.MetaData(name=name,terms=terms)

#------------------------------------------------------------------------------
#
class _FieldContainer(object):
    def __init__(self):
        self._defn = None
    def set_defn(self, cls):
        term_defn_name = "{}Field".format(cls.__name__)
        def fn_init(self, default=None):
            self._index = False
            self._default=default
        def _pytocl(v):
            if not isinstance(v, cls):
                raise TypeError("Value not an instance of {}".format(cls))
            return v.raw
        def _cltopy(v):
            return cls(raw=v)

        self._defn = type(term_defn_name, (RawField,),
                          { "__init__": fn_init,
                            "pytocl": _pytocl,
                            "cltopy": _cltopy })
    @property
    def defn(self):
        return self._defn

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

        # Create the metadata and populate the class dict (including the terms)
        md = _make_nls_metadata(name, dct)

        # Set the _meta attribute and constuctor
        dct["_meta"] = md
        dct["__init__"] = _nls_constructor
        dct["_termdefn"] = _FieldContainer()

        return super(_NonLogicalSymbolMeta, meta).__new__(meta, name, bases, dct)

    def __init__(cls, name, bases, dct):
        if name == "NonLogicalSymbol":
            return super(_NonLogicalSymbolMeta, cls).__init__(name, bases, dct)

        # Set this class as the field
        dct["_termdefn"].set_defn(cls)

        md = dct["_meta"]
        # The property attribute for each term can only be created in __new__
        # but the class itself does not get created until after __new__. Hence
        # we have to set the pointer within the term back to the this class
        # here.
        for term_name, term_defn in md.term_defns.items():
            dct[term_name].set_parent(cls)

#        print("CLS: {}".format(cls) + "I am still called '" + name +"'")
        return super(_NonLogicalSymbolMeta, cls).__init__(name, bases, dct)

#------------------------------------------------------------------------------
# A base non-logical symbol that all predicate/term declarations must inherit
# from. The Metaclass creates the magic to create the terms and the underlying
# clingo symbol object.
# ------------------------------------------------------------------------------

class NonLogicalSymbol(object, metaclass=_NonLogicalSymbolMeta):
    """Encapsulates an ASP predicate or complex term in an easy to access object.

    This is the heart of the ORM model for defining the mapping of a complex
    term or predicate to a Python object. ``Predicate`` and ``ComplexTerm`` are
    actually aliases for NonLogicalSymbol.

    Example:
       .. code-block:: python

           class Booking(Predicate):
               date = StringField(index = True)
               time = StringField(index = True)
               name = StringField(default = "relax")

           b1 = Booking("20190101", "10:00")
           b2 = Booking("20190101", "11:00", "Dinner")

    Fields names can be any valid Python variable name (i.e., not be a Python
    keyword) subject to the following restrictions:

    - start with a "_", or
    - be one of the following reserved words: "meta", "raw", "clone", "Field".

    The constructor creates a predicate instance (i.e., a *fact*) or complex
    term. If the ``raw`` parameter is used then it tries to unify the supplied
    Clingo.Symbol with the class definition, and will raise a ValueError if it
    fails to unify.

    Args:
      **kwargs:

         - if a single named parameter ``raw`` is specified then it will try to
           unify the parameter with the specification, or
         - named parameters corresponding to the term names.

    """

    #--------------------------------------------------------------------------
    # A Metadata internal object for each NonLogicalSymbol class
    #--------------------------------------------------------------------------
    class MetaData(object):
        """Internal class that encapsulates the meta-data for a NonLogicalSymbol
        definition

        .. warning:: Deprecated interface

           Thing remove these details from the external interface.

        """

        def __init__(self, name, terms):
            self._name = name
            self._terms = tuple(terms)

        @property
        def name(self):
            """Returns the string name of the predicate or complex term"""
            return self._name

        @property
        def term_defns(self):
#            """Returns the set of fields - keyed by field name"""
            return { f.term_name : f.term_defn for f in self._terms }

        @property
        def term_names(self):
#            """Returns the list of term names"""
            return [ f.term_name for f in self._terms ]

        @property
        def terms(self):
            return self._terms

        @property
        def arity(self):
            """Returns the number of fields"""
            return len(self._terms)

        @property
        def is_tuple(self):
            """Returns true if the definition corresponds to a tuple"""
            return self.name == ""

    #--------------------------------------------------------------------------
    # Properties and functions for NonLogicalSymbol
    #--------------------------------------------------------------------------

    # Get the underlying clingo symbol object
    @property
    def raw(self):
        """Returns the underlying Clingo.Symbol object"""
#        return self._symbol
        return self._generate_symbol()

    @_classproperty
    def Field(cls):
        """A RawField sub-class corresponding to a Field for this class."""
        return cls._termdefn.defn

    # Recompute the symbol object from the stored term objects
    def _generate_symbol(self):
        pred_args = []
        for term_name, term_defn in self.meta.term_defns.items():
            pred_args.append(term_defn.pytocl(self._term_values[term_name]))
        # Create the clingo symbol object
        return clingo.Function(self.meta.name, pred_args)

    # Clone the object with some differences
    def clone(self, **kwargs):
        """Clone the object with some differences.

        For any term name that is not one of the parameter keywords the clone
        keeps the same value. But for any term listed in the parameter keywords
        replace with specified new value.
        """

        # Sanity check
        clonekeys = set(kwargs.keys())
        objkeys = set(self.meta.term_defns.keys())
        diffkeys = clonekeys - objkeys
        if diffkeys:
            raise ValueError("Unknown term names: {}".format(diffkeys))

        # Get the arguments for the new object
        cloneargs = {}
        for term_name, term_defn in self.meta.term_defns.items():
            if term_name in kwargs: cloneargs[term_name] = kwargs[term_name]
            else: cloneargs[term_name] = kwargs[term_name] = self._term_values[term_name]

        # Create the new object
        return type(self)(**cloneargs)

    #--------------------------------------------------------------------------
    # Class methods and properties
    #--------------------------------------------------------------------------

    # Get the metadata for the NonLogicalSymbol definition
    @_classproperty
    def meta(cls):
        """Returns the meta data for the object"""
        return cls._meta

    # Returns whether or not a Symbol can unify with this NonLogicalSymbol
    @classmethod
    def _unifies(cls, symbol):
        if symbol.type != clingo.SymbolType.Function: return False

        name = cls.meta.name
        term_defns = cls.meta.term_defns

        if symbol.name != name: return False
        if len(symbol.arguments) != len(term_defns): return False

        for idx, (term_name, term_defn) in enumerate(term_defns.items()):
            term = symbol.arguments[idx]
            if not term_defn.unifies(symbol.arguments[idx]): return False
        return True

    # Factory that returns a unified NonLogicalSymbol object
    @classmethod
    def _unify(cls, symbol):
        return cls(raw=symbol)

    #--------------------------------------------------------------------------
    # Overloaded index operator to access the values
    #--------------------------------------------------------------------------
    def __getitem__(self, idx):
        """Allows for index based access to term elements."""
        return self.meta.terms[idx].__get__(self)

#------------------------------------------------------------------------
# Removed so don't allow value to be changed.
#    def __setitem__(self, idx,v):
#        return self.meta.terms[idx].__set__(self,v)

    #--------------------------------------------------------------------------
    # Overloaded operators
    #--------------------------------------------------------------------------
    def __eq__(self, other):
        """Overloaded boolean operator."""
        self_symbol = self.raw
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.raw
            return self_symbol == other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol == other
        else:
            return NotImplemented

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        """Overloaded boolean operator."""
        self_symbol = self.raw
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.raw
            return self_symbol < other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol < other
        else:
            return NotImplemented

    def __ge__(self, other):
        """Overloaded boolean operator."""
        result = self.__lt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __gt__(self, other):
        """Overloaded boolean operator."""
        self_symbol = self.raw
        if isinstance(other, NonLogicalSymbol):
            other_symbol = other.raw
            return self_symbol > other_symbol
        elif type(other) == clingo.Symbol:
            return self_symbol > other
        else:
            return NotImplemented

    def __le__(self, other):
        """Overloaded boolean operator."""
        result = self.__gt__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return self.raw.__hash__()

    def __str__(self):
        """Returns the NonLogicalSymbol as the string representation of the raw
        symbol.
        """
        self_symbol = self.raw
        return str(self_symbol)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Predicate and ComplexTerm are simply aliases for NonLogicalSymbol.
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

def _fact_generator(unifiers, symbols):
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


# A helper function to return the list of term comparators of a comparator
def _get_term_comparators(comparator):
    try:
        return comparator.term_comparators
    except:
        if isinstance(comparator, _FieldComparator):
            return [comparator]
        return []

#------------------------------------------------------------------------------
# Placeholder allows for variable substituion of a query. Placeholder is
# an abstract class that exposes no API other than its existence.
# ------------------------------------------------------------------------------
class Placeholder(abc.ABC):
    """An abstract class for defining parameterised queries.

    Currently, ClORM supports 4 placeholders: ph1\_, ph2\_, ph3\_, ph4\_. These
    correspond to the positional arguments of the query execute function call.

    """
    pass

class _NamedPlaceholder(Placeholder):
    def __init__(self, name, default=None):
        self._name = str(name)
        self._default = default
        self._value = None
    @property
    def name(self):
        return self._name
    @property
    def default(self):
        return self._default
    def __str__(self):
        tmpstr = "" if not self._default else ",{}"
        return "ph_({}{})".format(self._name, tmpstr)

class _PositionalPlaceholder(Placeholder):
    def __init__(self, posn):
        self._posn = posn
        self._value = None
    @property
    def posn(self):
        return self._posn
    def reset(self):
        self._value = None
    def __str__(self):
        return "ph{}_".format(self._posn+1)

def ph_(name,default=None):
    return _NamedPlaceholder(name,default)
ph1_ = _PositionalPlaceholder(0)
ph2_ = _PositionalPlaceholder(1)
ph3_ = _PositionalPlaceholder(2)
ph4_ = _PositionalPlaceholder(3)

#------------------------------------------------------------------------------
# A Comparator is a boolean functor that takes a fact instance and returns
# whether it satisfies some condition.
# ------------------------------------------------------------------------------

class Comparator(abc.ABC):

    @abc.abstractmethod
    def __call__(self,fact, *args, **kwargs):
        pass

#------------------------------------------------------------------------------
# A Fact comparator functor that returns a static value
#------------------------------------------------------------------------------

class _StaticComparator(Comparator):
    def __init__(self, value):
        self._value=bool(value)
    def __call__(self,fact, *args, **kwargs):
        return self._value
    def simpified(self):
        return self
    @property
    def value(self):
        return self._value

#------------------------------------------------------------------------------
# A fact comparator functor that tests whether a fact satisfies a comparision
# with the value of some predicate's term.
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
        # 2) neither argument is a Field
        if arg1 is arg2:
            self._static = True
            self._value = compop(1,1)
        elif not isinstance(arg1, _Field) and not isinstance(arg2, _Field):
            self._static = True
            self._value = compop(arg1,arg2)

    def __call__(self, fact, *args, **kwargs):
        if self._static: return self._value

        # Get the value of an argument (resolving placeholder)
        def getargval(arg):
            if isinstance(arg, _Field): return arg.__get__(fact)
            elif isinstance(arg, _PositionalPlaceholder):
                if arg.posn >= len(args):
                    raise TypeError(("missing argument in {} for placeholder "
                                     "{}").format(args, arg))
                return args[arg.posn]
            elif isinstance(arg, _NamedPlaceholder):
                if arg.name in kwargs:
                    return kwargs[arg.name]
                elif arg.default is not None:
                    return arg.default
                else:
                    raise TypeError(("missing argument in {} for named "
                                     "placeholder with no default "
                                     "{}").format(kwargs, arg))
            else: return arg

        # Get the values of the two arguments and then calculate the operator
        v1 = getargval(self._arg1)
        v2 = getargval(self._arg2)
        return self._compop(v1,v2)

    def simplified(self):
        if self._static: return _StaticComparator(self._value)
        return self

    def placeholders(self):
        tmp = []
        if isinstance(self._arg1, Placeholder): tmp.append(self._arg1)
        if isinstance(self._arg2, Placeholder): tmp.append(self._arg2)
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

    def __call__(self, fact, *args, **kwargs):
        if self._boolop == operator.not_:
            return operator.not_(self._args[0](fact,*args,**kwargs))
        elif self._boolop == operator.and_:
            for a in self._args:
                if not a(fact,*args,**kwargs): return False
            return True
        elif self._boolop == operator.or_:
            for a in self._args:
                if a(fact,*args,**kwargs): return True
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

    def del_values(self, keys, valueset):
        for k in keys:
            vs = self._key2values[k]
            newvs = [ f for f in vs if f not in valueset ]
            if not newvs:
                del self._key2values[k]
                del self._keylist[bisect.bisect_left(self._keylist, k)]
            else: self._key2values[k] = newvs

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
        tmp = ", ".join(["{} : {}".format(
            key, self._key2values[key]) for key in self._keylist])
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
        self._index_priority = { f:p for (p,f) in enumerate(factmap.indexed_terms()) }
        self._where = None
        self._indexable = None

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

#    @property
    def _debug(self):
        return self._indexable

    def get(self, *args, **kwargs):
        # Function to get a value - resolving placeholder if necessary
        def get_value(arg):
            if isinstance(arg, _PositionalPlaceholder):
                if arg.posn >= len(args):
                    raise TypeError(("missing argument in {} for placeholder "
                                     "{}").format(args, arg))
                return args[arg.posn]
            elif isinstance(arg, _NamedPlaceholder):
                if arg.name in kwargs:
                    return kwargs[arg.name]
                elif arg.default is not None:
                    return arg.default
                else:
                    raise TypeError(("missing argument in {} for named "
                                     "placeholder with no default "
                                     "{}").format(kwargs, arg))
            else: return arg

        # If there is no index test all instances else use the index
        if not self._indexable:
            for f in self._factmap.facts():
                if not self._where: yield f
                elif self._where and self._where(f,*args,**kwargs): yield(f)
        else:
            mmap=self._factmap.get_facts_multimap(self._indexable[0])
            for key in mmap.keys_op(self._indexable[1], get_value(self._indexable[2])):
                for f in mmap[key]:
                    if self._where(f,*args,**kwargs): yield f

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
# A deletion over a _FactMap
# - a stupid implementation that iterates over all facts and indexes
#------------------------------------------------------------------------------

class _Delete(Delete):

    def __init__(self, factmap):
        self._factmap = factmap
        self._index_prior = { f:p for (p,f) in enumerate(factmap.indexed_terms()) }
        self._where = None

    def where(self, *expressions):
        if self._where:
            raise ValueError("trying to specify multiple where clauses")
        if not expressions:
            self._where = None
        elif len(expressions) == 1:
            self._where = _simplify_fact_comparator(expressions[0])
        else:
            self._where = _simplify_fact_comparator(and_(*expressions))
        return self

    def execute(self, *args, **kwargs):
        # If there is no where clause then delete everything
        if not self._where:
            num_deleted = len(self._factmap.facts())
            self._factmap.clear()
            return num_deleted

        # Gather all the facts to delete
        to_delete = \
            set([ f for f in self._factmap.facts() if self._where(f,*args,**kwargs) ])

        # Replace the all facts by a new list with the matching facts removed
        self._factmap._allfacts = \
            [ f for f in self._factmap.facts() if f not in to_delete ]

        # Remove the facts from each multimap
        for fid, term in enumerate(self._factmap.indexed_terms()):
            keys = set([ term.__get__(f) for f in to_delete ])
            mm  = self._factmap.get_facts_multimap(term)
            mm.del_values(keys, to_delete)

        # return the number deleted
        return len(to_delete)


#------------------------------------------------------------------------------
# A map for facts of the same type - Indexes can be built to allow for fast
# lookups based on a term value. The order that the terms are specified in the
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
            for term, mmap in self._mmaps.items():
                mmap[term.__get__(fact)] = fact

    def indexed_terms(self):
        return self._mmaps.keys() if self._mmaps else []

    def get_facts_multimap(self, term):
        return self._mmaps[term]

    def facts(self):
        return self._allfacts

    def clear(self):
        self._allfacts.clear()
        if self._mmaps:
            for term, mmap in self._mmaps.items():
                mmap.clear()

    def select(self):
        return _Select(self)

    def delete(self):
        return _Delete(self)

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
# FactBaseHelper offers a decorator interface for gathering predicate and index
# definitions to be used in defining a FactBase subclass.
# ------------------------------------------------------------------------------
class FactBaseHelper(object):
    def __init__(self, suppress_auto_index=False):
        self._predicates = []
        self._indexes = []
        self._predset = set()
        self._indset = set()
        self._suppress_auto_index = suppress_auto_index

    def register_predicate(self, cls):
        if cls in self._predset: return    # ignore if already registered
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        self._predset.add(cls)
        self._predicates.append(cls)
        if self._suppress_auto_index: return

        # Register the terms that have the index flag set
        for term in cls.meta.terms:
            with contextlib.suppress(AttributeError):
                if term.term_defn.index: self.register_index(term)

    def register_index(self, term):
        if term in self._indset: return    # ignore if already registered
        if isinstance(term, Field) and term.parent in self.predicates:
            self._indset.add(term)
            self._indexes.append(term)
        else:
            raise TypeError("{} is not a predicate term for one of {}".format(
                term, [ p.__name__ for p in self.predicates ]))

    def register(self, *args):
        def wrapper(cls):
            self.register_predicate(cls)
            terms = [ getattr(cls, fn) for fn in args ]
            for f in terms: self.register_index(f)
            return cls

        if len(args) == 1 and inspect.isclass(args[0]):
            self.register_predicate(args[0])
            return args[0]
        else:
            return wrapper

    def create_class(self, name):
        return type(name, (FactBase,),
                    { "predicates" : self.predicates, "indexes" : self.indexes })

    @property
    def predicates(self): return self._predicates
    @property
    def indexes(self): return self._indexes

#------------------------------------------------------------------------------
# Functions to be added to FactBase class or sub-class definitions
#------------------------------------------------------------------------------

def _fb_base_constructor(self, *args, **kwargs):
    raise TypeError("{} must be sub-classed ".format(self.__class__.__name__))

#def _fb_base_constructor(self, facts=[], delayed_init=False):
#    _fb_subclass_constructor(self, facts=facts, delayed_init=delayed_init)

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

    return self._add(fact=fact,facts=facts,symbols=symbols)



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
            dct["__init__"] = _fb_base_constructor
            dct[plistname] = []
            dct[ilistname] = []
#            dct["add"] = _fb_base_add
            return super(_FactBaseMeta, meta).__new__(meta, name, bases, dct)

        # Cumulatively inherits the predicates and indexes from the FactBase
        # base classes - which we can then override.  Use ordered dict to
        # preserve ordering
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

        # Make sure "predicates" is defined and is a non-empty list
        pset = set()
        if plistname not in dct:
            raise TypeError("Class definition missing 'predicates' specification")
        if not dct[plistname]:
            raise TypeError("Class definition empty 'predicates' specification")
        for pitem in dct[plistname]:
            pset.add(pitem)
            if not issubclass(pitem, Predicate):
                raise TypeError("Non-predicate class {} in list".format(pitem))

        # Validate the "indexes" list (and define if if it doesn't exist)
        if ilistname not in dct: dct[ilistname] = []
        for iitem in dct[ilistname]:
            if iitem.parent not in pset:
                raise TypeError(("Parent of index {} item not in the predicates "
                                  "list").format(iitem))
        dct["__init__"] = _fb_subclass_constructor
        dct["add"] = _fb_subclass_add
        return super(_FactBaseMeta, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# A FactBase consisting of facts of different types
#------------------------------------------------------------------------------

class FactBase(object, metaclass=_FactBaseMeta):
    """A fact base is a container for facts that must be subclassed.

    ``FactBase`` can be thought of as a minimalist database. It stores facts for
    a given set of ``Predicate`` types (where a predicate type loosely
    corresponding to a *table* in a database) and allows for certain fields to
    be indexed in order to perform more efficient queries.

    Subclassing ``FactBase`` is done by specifying a ``predicates`` and
    ``indexes`` variables; cntaining a list of ``Predicate`` sub-classes to
    include and a list ``indexes`` of fields to index (respectively).

    .. code-block:: python

          class Predicate1(Predicate):
              anum = IntegerField(index=1)
              astr = String()

          class Predicate2(Predicate):
              # ...

         class MyFactBase(FactBase):
              predicates = [Predicate1, Predicate2]
              indexes = [Predicate1.anum]

    See the ``FactBaseHelper`` for a helper class to simplify the process of
    creating a ``FactBase`` sub-class.

    Args:
      facts(Predicate): a list of facts (predicate instances) to add to the fact
          base. Default None.
      symbols(Clingo.Symbol): a list of symbols which are unified against the
         given Predicate types. Symbols that fail to unify are ignored. Default
         None.
      delayed_init(bool): whether to perform delayed intialisation. Default
         False.

    The ``facts`` and ``symbols`` parameters in the constructor are mutually
    exclusive.

    """

    # A special purpose initialiser so that we can do delayed initialisation
    def _init(self, facts=None, symbols=None):

        # Create _FactMaps for the predicate types with indexed terms
        grouped = {}
        for term in self.indexes:
            if term.parent not in grouped: grouped[term.parent] = []
            grouped[term.parent].append(term)
        for p in self.predicates:
            if p not in grouped: grouped[p] = []
        self._factmaps = { pt : _FactMap(fs) for pt, fs in grouped.items() }

        # add the facts
        self._add(facts=facts, symbols=symbols)

        # flag that initialisation has taken place
        self._delayed_init = None

    #--------------------------------------------------------------------------
    # Internal member functions
    #--------------------------------------------------------------------------

    def _add(self, fact=None,facts=None,symbols=None):
        count = 0
        if fact is not None: return self._add_fact(fact)
        elif facts is not None:
            for f in facts:
                count += self._add_fact(f)
        elif symbols is not None:
            for f in _fact_generator(self.predicates, symbols):
                count += self._add_fact(f)
        return count

    def _add_fact(self, fact):
        predicate_cls = type(fact)
        if not issubclass(predicate_cls,Predicate):
            raise TypeError(("type of object {} is not a Predicate "
                             "subclass").format(fact))
        if predicate_cls not in self._factmaps: return 0
#            self._factmaps[predicate_cls] = _FactMap()
        self._factmaps[predicate_cls].add(fact)
        return 1


    #--------------------------------------------------------------------------
    # External member functions
    #--------------------------------------------------------------------------

    def select(self, predicate_cls):
        """Create a Select query for a predicate type."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        return self._factmaps[predicate_cls].select()

    def delete(self, predicate_cls):
        """Create a Select query for a predicate type."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        return self._factmaps[predicate_cls].delete()

    def predicate_types(self):
        """Return the list of predicate types that this fact base can deal with."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        return set(self._factmaps.keys())

    def clear(self):
        """Clear the fact base of all facts."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        self._symbols = None

        for pt, fm in self._factmaps.items():
            fm.clear()

    def facts(self):
        """Return all facts."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        fcts = []
        for fm in self._factmaps.values():
            fcts.extend(fm.facts())
        return fcts

    def asp_str(self):
        """Return a string representation of the fact base that is suitable for adding
        to an ASP program

        """

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
# When calling Python functions from ASP you need to do some type
# conversions. The Signature class can be used to generate a wrapper function
# that does the type conversion for you.
# ------------------------------------------------------------------------------

class Signature(object):
    """Defines a function signature for converting to/from Clingo data types.

    Args:
      sigs(\*sigs): A list of function signature elements.

      - Inputs. Match the sub-elements [:-1] define the input signature while
        the last element defines the output signature. Each input must be a a
        RawField (or sub-class).

      - Output: Must be RawField (or sub-class) or a singleton list
        containing a RawField (or sub-class).

   Example:
       .. code-block:: python

           import datetime

           class DateField(StringField):
                     pytocl = lambda dt: dt.strftime("%Y%m%d")
                     cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

           drsig = Signature(DateField, DateField, [DateField])

           @drsig.make_clingo_wrapper
           def date_range(start, end):
               return [ start + timedelta(days=x) for x in range(0,end-start) ]

       The function ``date_range`` that takes a start and end date and returns
       the list of dates within that range.

       When *decorated* with the signature it provides the conversion code so
       that the decorated function expects a start and end date encoded as
       Clingo.String objects (matching YYYYMMDD format) and returns a list of
       Clingo.String objects corresponding to the dates in that range.

        """

    def __init__(self, *sigs):
        def _validate_basic_sig(sig):
            if issubclass(sig, RawField): return True
            raise TypeError(("Signature element {} must be a RawField "
                             "subclass".format(s)))

        self._insigs = sigs[:-1]
        self._outsig = sigs[-1]

        # Validate the signature
        for s in self._insigs: _validate_basic_sig(s)
        if isinstance(self._outsig, collections.Iterable):
            if len(self._outsig) != 1:
                raise ValueError("Return value list signature not a singleton")
            _validate_basic_sig(self._outsig[0])
        else:
            _validate_basic_sig(self._outsig)

    def _input(self, sig, arg):
        return sig.cltopy(arg)

    def _output(self, sig, arg):
        # Since signature already validated we can make assumptions
        if inspect.isclass(sig) and issubclass(sig, RawField):
            return sig.pytocl(arg)

        # Deal with a list
        if isinstance(sig, collections.Iterable) and isinstance(arg, collections.Iterable):
            return [ self._output(sig[0], v) for v in arg ]
        raise ValueError("Value {} does not match signature {}".format(arg, sig))


    def wrap_function(self, fn):
        """Function wrapper that adds data type conversions for wrapped function.

        Args:
           fn: A function satisfing the inputs and output defined by the Signature.
        """

        @functools.wraps(fn)
        def wrapper(*args):
            if len(args) > len(self._insigs):
                raise ValueError("Mis-matched arguments in call of clingo wrapper")
            newargs = [ self._input(self._insigs[i], arg) for i,arg in enumerate(args) ]
            return self._output(self._outsig, fn(*newargs))
        return wrapper


    def wrap_method(self, fn):
        """Member function wrapper that adds data type conversions for wrapped member
        functions.

        Args:
           fn: A function satisfing the inputs and output defined by the Signature.

        """

        @functools.wraps(fn)
        def wrapper(self_, *args):
            if len(args) > len(self._insigs):
                raise ValueError("Mis-matched arguments in call of clingo wrapper")
            newargs = [ self._input(self._insigs[i], arg) for i,arg in enumerate(args) ]
            return self._output(self._outsig, fn(self_, *newargs))
        return wrapper

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
