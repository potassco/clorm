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
import typing

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
    'desc',
    'unify',
    'Select',
    'Delete',
    'FactBase',
    'FactBaseBuilder',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'not_',
    'and_',
    'or_',
    'TypeCastSignature',
    'make_function_asp_callable',
    'make_method_asp_callable'
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
    def desc(self):
        """Set descending sort order"""
        pass

    @abc.abstractmethod
    def asc(self):
        """Set descending sort order"""
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
#
#------------------------------------------------------------------------------
class _FieldOrderBy(object):
    def __init__(self, field, asc):
        self.field = field
        self.asc = asc
    def compare(self, a,b):
        va = self.field.__get__(a)
        vb = self.field.__get__(b)
        if  va == vb: return 0
        if self.asc and va < vb: return -1
        if not self.asc and va > vb: return -1
        return 1

    def __str__(self):
        return "_FieldOrderBy(field={},asc={})".format(self.field, self.asc)

#------------------------------------------------------------------------------
# A helper function to return a _FieldOrderBy descending object
#------------------------------------------------------------------------------
def desc(field):
    return field.desc()

#------------------------------------------------------------------------------
# Implementation of a Field
# ------------------------------------------------------------------------------
class _Field(Field):
    def __init__(self, term_name, term_index, term_defn):
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

    def asc(self):
        return _FieldOrderBy(self, asc=True)

    def desc(self):
        return _FieldOrderBy(self, asc=False)

    def __get__(self, instance, owner=None):
        if not instance: return self
        if not isinstance(instance, self._parent_cls):
            raise TypeError(("term {} doesn't match type "
                             "{}").format(self, type(instance).__name__))
        return instance._term_values[self._term_name]
#            return term_defn.cltopy(self._symbol.arguments[idx])

    def __set__(self, instance, value):
        raise AttributeError("field is a read-only data descriptor")

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
        def _pytocl(v):
            if not isinstance(v, cls):
                raise TypeError("Value not an instance of {}".format(cls))
            return v.raw
        def _cltopy(v):
            return cls(raw=v)

        self._defn = type(term_defn_name, (RawField,),
                          { "pytocl": _pytocl,
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
        return self._symbol
#        return self._generate_symbol()

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
        if not isinstance(other, self.__class__): return NotImplemented
        return self.raw == other.raw

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __lt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__): return NotImplemented

        # compare each field in order
        for idx in range(0,self._meta.arity):
            selfv = self[idx]
            otherv = other[idx]
            if selfv == otherv: continue
            return selfv < otherv
        return False

    def __ge__(self, other):
        """Overloaded boolean operator."""
        result = self.__lt__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __gt__(self, other):
        """Overloaded boolean operator."""
        if not isinstance(other, self.__class__): return NotImplemented

        # compare each field in order
        for idx in range(0,self._meta.arity):
            selfv = self[idx]
            otherv = other[idx]
            if selfv == otherv: continue
            return selfv > otherv
        return False

    def __le__(self, other):
        """Overloaded boolean operator."""
        result = self.__gt__(other)
        if result is NotImplemented: return NotImplemented
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

def unify(unifiers, symbols):
    '''Unify a collection of symbols against a list of predicate types.

    Symbols are tested against each unifier until a match is found. Since it is
    possible to define multiple predicate types that can unify with the same
    symbol, the order the unifiers differently can produce different results.

    Args:
      unifiers: a list of predicate classes to unify against
      symbols: the symbols to unify

    '''
    def unify_single(cls, r):
        try:
            return cls._unify(r)
        except ValueError:
            return None

    types = {(cls.meta.name, cls.meta.arity) : cls for cls in unifiers}
    facts = []
    for raw in symbols:
        cls = types.get((raw.name, len(raw.arguments)))
        if not cls: continue
        f = unify_single(cls,raw)
        if f: facts.append(f)
    return facts


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

    Currently, Clorm supports 4 placeholders: ph1\_, ph2\_, ph3\_, ph4\_. These
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

def ph_(value,default=None):
    try:
        idx = int(value)
    except ValueError:
        return _NamedPlaceholder(value,default)
    if default is not None:
        raise ValueError("Positional placeholders don't support default values")
    idx -= 1
    if idx < 0:
        raise ValueError("Index {} is not a positional argument".format(idx+1))
    return _PositionalPlaceholder(idx)

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
# _FactIndex indexes facts by a given field
#------------------------------------------------------------------------------

class _FactIndex(object):
    def __init__(self, field):
        if not isinstance(field, _Field):
            raise TypeError("{} is not a _Field instance".format(field))
        self._field = field
        self._keylist = []
        self._key2values = {}

    def add(self, fact):
        if not isinstance(fact, self._field.parent):
            raise TypeError("{} is not a {}".format(fact, self._field.parent))
        key = self._field.__get__(fact)

        # Index the fact by the key
        if key not in self._key2values: self._key2values[key] = set()
        self._key2values[key].add(fact)

        # Maintain the sorted list of keys
        posn = bisect.bisect_left(self._keylist, key)
        if len(self._keylist) > posn and self._keylist[posn] == key: return
        bisect.insort_left(self._keylist, key)

    def discard(self, fact):
        self.remove(fact, False)

    def remove(self, fact, raise_on_missing=True):
        if not isinstance(fact, self._field.parent):
            raise TypeError("{} is not a {}".format(fact, self._field.parent))
        key = self._field.__get__(fact)

        # Remove the value
        if key not in self._key2values:
            if raise_on_missing:
                raise KeyError("{} is not in the FactIndex".format(fact))
            return
        values = self._key2values[key]
        if raise_on_missing: values.remove(fact)
        else: values.discard(fact)

        # If still have values then we're done
        if values: return

        # remove the key
        del self._key2values[key]
        posn = bisect.bisect_left(self._keylist, key)
        del self._keylist[posn]

    def clear(self):
        self._keylist = []
        self._key2values = {}

    @property
    def keys(self): return self._keylist

    #--------------------------------------------------------------------------
    # Internal functions to get keys matching some boolean operator
    #--------------------------------------------------------------------------

    def _keys_eq(self, key):
        if key in self._key2values: return [key]
        return []

    def _keys_ne(self, key):
        posn1 = bisect.bisect_left(self._keylist, key)
        if posn1: left =  self._keylist[:posn1]
        else: left = []
        posn2 = bisect.bisect_right(self._keylist, key)
        if posn2: right = self._keylist[posn2:]
        else: right = []
        return left + right

    def _keys_lt(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def _keys_le(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[:posn]
        return []

    def _keys_gt(self, key):
        posn = bisect.bisect_right(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    def _keys_ge(self, key):
        posn = bisect.bisect_left(self._keylist, key)
        if posn: return self._keylist[posn:]
        return []

    #--------------------------------------------------------------------------
    # Find elements based on boolean match to a key
    #--------------------------------------------------------------------------
    def find(self, op, key):
        keys = []
        if op == operator.eq: keys = self._keys_eq(key)
        elif op == operator.ne: keys = self._keys_ne(key)
        elif op == operator.lt: keys = self._keys_lt(key)
        elif op == operator.le: keys = self._keys_le(key)
        elif op == operator.gt: keys = self._keys_gt(key)
        elif op == operator.ge: keys = self._keys_ge(key)
        else: raise ValueError("unsupported operator {}".format(op))

        sets = [ self._key2values[k] for k in keys ]
        if not sets: return set()
        return set.union(*sets)

#------------------------------------------------------------------------------
# Select is an interface query over a FactBase.
# ------------------------------------------------------------------------------

class Select(abc.ABC):

    @abc.abstractmethod
    def where(self, *expressions):
        """Set the select statement's where clause.

        The where clause consists of a set of comparison expressions. A
        comparison expression is simply a test functor that takes a predicate
        instance and returns whether or not that instance satisfies some
        requirement. Hence any lambda or function with this signature can be
        passed.

        Such test functors can also be generated using a more natural syntax,
        simply by making a boolean comparison between a field and a some other
        object. This is acheived by overloading the field boolean comparison
        operators to return a functor.

        The second parameter can point to an arbitrary value or a special
        placeholder value that issubstituted when the query is actually
        executed. These placeholders are named ``ph1_``, ``ph2_``, ``ph3_``, and
        ``ph4_`` and correspond to the 1st to 4th arguments of the ``get`` or
        ``get_unique`` function call.

        Args:
          expressions: one or more comparison expressions.

        """
        pass

    @abc.abstractmethod
    def order_by(self, *fieldorder):
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
        self._index_priority = { f:p for (p,f) in enumerate(factmap.indexes) }
        self._where = None
        self._indexable = None
        self._key = None

    def where(self, *expressions):
        if self._where:
            raise ValueError("cannot specify 'where' multiple times")
        if not expressions:
            raise ValueError("empty 'where' expression")
        elif len(expressions) == 1:
            self._where = _simplify_fact_comparator(expressions[0])
        else:
            self._where = _simplify_fact_comparator(and_(*expressions))

        self._indexable = self._primary_search(self._where)
        return self

    @property
    def has_where(self):
        return bool(self._where)

    def order_by(self, *expressions):
        if self._key:
            raise ValueError("cannot specify 'order_by' multiple times")
        if not expressions:
            raise ValueError("empty 'order_by' expression")
        field_orders = []
        for exp in expressions:
            if isinstance(exp, _FieldOrderBy): field_orders.append(exp)
            elif isinstance(exp, _Field): field_orders.append(exp.asc())
            else: raise ValueError("Invalid field order expression: {}".format(exp))

        # Create a comparator function
        def mycmp(a, b):
            for ford in field_orders:
                value = ford.compare(a,b)
                if value == 0: continue
                return value
            return 0

        self._key = functools.cmp_to_key(mycmp)
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
        result = []
        if not self._indexable:
            for f in self._factmap.facts():
                if not self._where: result.append(f)
                elif self._where and self._where(f,*args,**kwargs): result.append(f)
        else:
            findex = self._factmap.get_factindex(self._indexable[0])
            for f in findex.find(self._indexable[1], get_value(self._indexable[2])):
                if self._where(f,*args,**kwargs): result.append(f)

        # Return the results - sorted if necessary
        if self._key: result.sort(key=self._key)
        return result

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
        self._select = _Select(factmap)

    def where(self, *expressions):
        self._select.where(*expressions)
        return self

    def execute(self, *args, **kwargs):
        # If there is no where clause then delete everything
        if not self._select.has_where:
            num_deleted = len(self._factmap.facts())
            self._factmap.clear()
            return num_deleted

        # Gather all the facts to delete and remove them
        to_delete = [ f for f in self._select.get(*args, **kwargs) ]
        for fact in to_delete: self._factmap.remove(fact)
        return len(to_delete)


#------------------------------------------------------------------------------
# A map for facts of the same type - Indexes can be built to allow for fast
# lookups based on a term value. The order that the terms are specified in the
# index matters as it determines the priority of the index.
# ------------------------------------------------------------------------------

class _FactMap(object):
    def __init__(self, ptype, index=[]):
        self._ptype = ptype
        self._allfacts = set()
        self._findexes = None
        if not issubclass(ptype, Predicate):
            raise TypeError("{} is not a subclass of Predicate".format(ptype))
        if index:
            self._findexes = collections.OrderedDict( (f, _FactIndex(f)) for f in index )
            prts = set([f.parent for f in index])
            if len(prts) != 1 or prts != set([ptype]):
                raise TypeError("Fields in {} do not belong to {}".format(index,prts))

    def add(self, fact):
        self._allfacts.add(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.add(fact)

    def discard(self, fact):
        self.remove(fact, False)

    def remove(self, fact, raise_on_missing=True):
        if raise_on_missing: self._allfacts.remove(fact)
        else: self._allfacts.discard(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.remove(fact,raise_on_missing)

    @property
    def indexes(self):
        if not self._findexes: return []
        return [ f for f, vs in self._findexes.items() ]

    def get_factindex(self, field):
        return self._findexes[field]

    def facts(self):
        return self._allfacts

    def clear(self):
        self._allfacts.clear()
        if self._findexes:
            for f, findex in self._findexes.items(): findex.clear()

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
        return self.asp_str()

    #--------------------------------------------------------------------------
    # Special functions to support container operations
    #--------------------------------------------------------------------------

    def __contains__(self, fact):
        if not isinstance(fact, self._ptype): return False
        return fact in self._allfacts

    def __bool__(self):
        return bool(self._allfacts)

    def __len__(self):
        return len(self._allfacts)

    def __iter__(self):
        return iter(self._allfacts)

#------------------------------------------------------------------------------
# FactBaseBuilder offers a decorator interface for gathering predicate and index
# definitions to be used in defining a FactBase subclass.
# ------------------------------------------------------------------------------
class FactBaseBuilder(object):
    def __init__(self, predicates=[], indexes=[], suppress_auto_index=False):
        self._predicates = []
        self._indexes = []
        self._predset = set()
        self._indset = set()
        self._suppress_auto_index = suppress_auto_index
        for pred in predicates: self._register_predicate(pred)
        for field in indexes: self._register_index(field)

    def _register_predicate(self, cls):
        if cls in self._predset: return    # ignore if already registered
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        self._predset.add(cls)
        self._predicates.append(cls)
        if self._suppress_auto_index: return

        # Register the fields that have the index flag set
        for field in cls.meta.terms:
            with contextlib.suppress(AttributeError):
                if field.term_defn.index: self._register_index(field)

    def _register_index(self, field):
        if field in self._indset: return    # ignore if already registered
        if isinstance(field, Field) and field.parent in self.predicates:
            self._indset.add(field)
            self._indexes.append(field)
        else:
            raise TypeError("{} is not a predicate field for one of {}".format(
                field, [ p.__name__ for p in self.predicates ]))

    def register(self, cls):
        self._register_predicate(cls)
        return cls

    def new(self, facts=None, symbols=None, delayed_init=False, raise_on_empty=False):
        if not symbols and (delayed_init or raise_on_empty):
            raise ValueError("'delayed_init' and 'raise_on_empty' only valid for symbols")
        if symbols and facts:
            raise ValueError("'symbols' and 'facts' options are mutually exclusive")

        def _populate():
            facts=unify(self.predicates, symbols)
            if not facts and raise_on_empty:
                raise ValueError("FactBase creation: failed to unify any symbols")
            return facts

        if delayed_init:
            return FactBase(facts=_populate, indexes=self._indexes)
        if symbols:
            return FactBase(facts=_populate(), indexes=self._indexes)
        else:
            return FactBase(facts=facts, indexes=self._indexes)

    @property
    def predicates(self): return self._predicates
    @property
    def indexes(self): return self._indexes

#------------------------------------------------------------------------------
# A FactBase consisting of facts of different types
#------------------------------------------------------------------------------

class FactBase(object):
    """A fact base is a container for facts that must be subclassed.

    ``FactBase`` can be thought of as a minimalist database. It stores facts for
    ``Predicate`` types (where a predicate type loosely corresponding to a
    *table* in a database) and allows for certain fields to be indexed in order
    to perform more efficient queries.

    Args:
      facts([Predicate]|callable): a list of facts (predicate instances), or a
         functor that generates. If a functor is passed then the factbase
         performs a delayed initialisation.
      indexes(Field): a list of fields that are to be indexed.

    """

    #--------------------------------------------------------------------------
    # Internal member functions
    #--------------------------------------------------------------------------

    # A special purpose initialiser so that we can do delayed initialisation
    def _init(self, facts=None, indexes=[]):

        # flag that initialisation has taken place
        self._delayed_init = None

        # If it is delayed initialisation then get the facts
        if facts and callable(facts): facts = facts()

        # Create _FactMaps for the predicate types with indexed terms
        grouped = {}
        for field in indexes:
            if field.parent not in grouped: grouped[field.parent] = []
            grouped[field.parent].append(field)
        self._factmaps = { pt : _FactMap(pt, fields) for pt, fields in grouped.items() }

        if facts is None: return
        self._add(facts)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------

    def _add(self, arg):
        if isinstance(arg, Predicate): return self._add_fact(arg)
        for f in arg: self._add_fact(f)

    # Helper for _add
    def _add_fact(self, fact):
        ptype = type(fact)
        if not issubclass(ptype,Predicate):
            raise TypeError(("type of object {} is not a Predicate "
                             "subclass").format(fact))
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        self._factmaps[ptype].add(fact)

    def _remove(self, fact, raise_on_missing):
        ptype = type(fact)
        if not isinstance(arg, Predicate) or ptype not in self._factmaps:
            raise KeyError("{} not in factbase".format(arg))

        return self._factmaps[ptype].delete()

    #--------------------------------------------------------------------------
    # Special functions to support container operations
    #--------------------------------------------------------------------------

    def __contains__(self, fact):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        if not isinstance(fact,Predicate): return False
        ptype = type(fact)
        if ptype not in self._factmaps: return False
        return fact in self._factmaps[ptype].facts()

    def __bool__(self):
        for fm in self._factmaps.values():
            if fm: return True
        return False

    def __len__(self):
        return sum([len(fm) for fm in self._factmaps.values()])

    def __iter__(self):
        for fm in self._factmaps.values():
            for f in fm: yield f

    #--------------------------------------------------------------------------
    # Initiliser
    #--------------------------------------------------------------------------
    def __init__(self, facts=None, indexes=[]):
        self._delayed_init=None
        if callable(facts):
            def delayed_init():
                self._init(facts, indexes)
            self._delayed_init=delayed_init
        else:
            self._init(facts, indexes)


    #--------------------------------------------------------------------------
    # Set member functions
    #--------------------------------------------------------------------------
    def add(self, arg):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        return self._add(arg)

    def remove(self, arg):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        return self._remove(arg, raise_on_missing=True)

    def discard(self, arg):
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        return self._remove(arg, raise_on_missing=False)

    def clear(self):
        """Clear the fact base of all facts."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        for pt, fm in self._factmaps.items(): fm.clear()

    #--------------------------------------------------------------------------
    # Special FactBase member functions
    #--------------------------------------------------------------------------
    def select(self, ptype):
        """Create a Select query for a predicate type."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].select()

    def delete(self, ptype):
        """Create a Select query for a predicate type."""

        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()

        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].delete()

    @property
    def predicates(self):
        """Return the list of predicate types that this fact base contains."""
        # Always check if we have delayed initialisation
        if self._delayed_init: self._delayed_init()
        return [pt for pt, fm in self._factmaps.items() if fm.facts()]

    @property
    def indexes(self):
        if self._delayed_init: self._delayed_init()
        tmp = []
        for fm in self._factmaps.values():
            tmp.extend(fm.indexes)
        return tmp

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
# conversions. The TypeCastSignature class can be used to generate a wrapper
# function that does the type conversion for you.
# ------------------------------------------------------------------------------

class TypeCastSignature(object):
    """Defines a signature for converting to/from Clingo data types.

    Args:
      sigs(\*sigs): A list of signature elements.

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

           drsig = TypeCastSignature(DateField, DateField, [DateField])

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

    @staticmethod
    def is_input_element(se):
        '''An input element must be a subclass of RawField'''
        return inspect.isclass(se) and issubclass(se, RawField)

    @staticmethod
    def is_return_element(se):
        '''An output element must be a subclass of RawField or a singleton containing'''
        if isinstance(se, collections.Iterable):
            if len(se) != 1: return False
            return TypeCastSignature.is_input_element(se[0])
        return TypeCastSignature.is_input_element(se)

    def __init__(self, *sigs):
        def _validate_basic_sig(sig):
            if TypeCastSignature.is_input_element(sig): return True
            raise TypeError(("TypeCastSignature element {} must be a RawField "
                             "subclass".format(sig)))

        self._insigs = sigs[:-1]
        self._outsig = sigs[-1]

        # Validate the signature
        for s in self._insigs: _validate_basic_sig(s)
        if isinstance(self._outsig, collections.Iterable):
            if len(self._outsig) != 1:
                raise TypeError("Return value list signature not a singleton")
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
           fn: A function satisfing the inputs and output defined by the TypeCastSignature.
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
           fn: A function satisfing the inputs and output defined by the TypeCastSignature.

        """

        @functools.wraps(fn)
        def wrapper(self_, *args):
            if len(args) > len(self._insigs):
                raise ValueError("Mis-matched arguments in call of clingo wrapper")
            newargs = [ self._input(self._insigs[i], arg) for i,arg in enumerate(args) ]
            return self._output(self._outsig, fn(self_, *newargs))
        return wrapper

#------------------------------------------------------------------------------
# return and check that function has complete signature
# annotations. ignore_first is useful when dealing with member functions.
#------------------------------------------------------------------------------

def _get_annotations(fn, ignore_first=False):
    fsig = inspect.signature(fn)
    fsigparam = fsig.parameters
    annotations = [fsigparam[s].annotation for s in fsigparam]
    if not annotations and ignore_first:
        raise TypeError("Empty function signature - cannot ignore first element")
    annotations.append(fsig.return_annotation)
    if ignore_first: annotations.pop(0)
    if inspect.Signature.empty in annotations:
        raise TypeError("Failed to extract all annotations from {} ".format(fn))
    return annotations


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

def make_function_asp_callable(*args):
    '''A decorator for making a function callable from within an ASP program.

    Can be called in a number of ways. Can be called as a decorator with or
    without arguments. If called with arguments then the arguments must
    correspond to a *type cast signature*.

    A *type cast signature* specifies the type conversions required between a
    python function that is called from within an ASP program and a set of
    corresponding Python types.

    A type cast signature is specified in terms of the fields that are used to
    define a predicate.  It is a list of elements where the first n-1 elements
    correspond to type conversions for a functions inputs and the last element
    corresponds to the type conversion for a functions output.

    Args:
      sigs(\*sigs): A list of function signature elements.

      - Inputs. Match the sub-elements [:-1] define the input signature while
        the last element defines the output signature. Each input must be a a
        RawField (or sub-class).

      - Output: Must be RawField (or sub-class) or a singleton list
        containing a RawField (or sub-class).

    If no arguments are provided then the function signature is derived from the
    function annotations. The function annotations must conform to the signature
    above.

    If called as a normal function with arguments then the last element must be
    the function to be wrapped and the previous elements conform to the
    signature profile.

    '''
    if len(args) == 0: raise ValueError("Invalid call to decorator")
    fn = None ; sigs = None

    # If the last element is not a function to be wrapped then a signature has
    # been specified.
    if TypeCastSignature.is_return_element(args[-1]):
        sigs = args
    else:
        # Last element needs to be a function
        fn = args[-1]
        if not callable(fn): raise ValueError("Invalid call to decorator")

        # if exactly one element then use function annonations
        if len(args) == 1:
            sigs = _get_annotations(fn)
        else:
            sigs = args[:-1]

    # A decorator function that adjusts for the given signature
    def _sig_decorate(func):
        s = TypeCastSignature(*sigs)
        return s.wrap_function(func)

    # If no function and sig then called as a decorator with arguments
    if not fn and sigs: return _sig_decorate

    return _sig_decorate(fn)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

def make_method_asp_callable(*args):
    '''A decorator for making a member function callable from within an ASP program.

    See ``make_function_asp_callable`` for details. The only difference is that
    the first element of the function is ignore as it is assumed to be the
    ``self`` or ``cls`` parameter.

    '''
    if len(args) == 0: raise ValueError("Invalid call to decorator")
    fn = None ; sigs = None

    # If the last element is not a function to be wrapped then a signature has
    # been specified.
    if TypeCastSignature.is_return_element(args[-1]):
        sigs = args
    else:
        # Last element needs to be a function
        fn = args[-1]
        if not callable(fn): raise ValueError("Invalid call to decorator")

        # if exactly one element then use function annonations
        if len(args) == 1:
            sigs = _get_annotations(fn,True)
        else:
            sigs = args[:-1]

    # A decorator function that adjusts for the given signature
    def _sig_decorate(func):
        s = TypeCastSignature(*sigs)
        return s.wrap_method(func)

    # If no function and sig then called as a decorator with arguments
    if not fn and sigs: return _sig_decorate

    return _sig_decorate(fn)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
