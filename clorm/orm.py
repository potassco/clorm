# -----------------------------------------------------------------------------
# ORM provides a Object Relational Mapper type model for specifying non-logical
# symbols (ie., predicates/complex-terms and fields)
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
import itertools
import clingo
import typing
import re

# ------------------------------------------------------------------------------
# In order to implement FactBase I originally used the built in 'set'
# class. However this uses the hash value, which for Predicate instances uses
# the underlying clingo.Symbol.__hash__() function. This in-turn depends on the
# c++ std::hash function. Like the Python standard hash function this uses
# random seeds at program startup which means that between successive runs of
# the same program the ordering of the set can change. This is bad for producing
# deterministic ASP solving. So using an OrderedSet instead.

from .util import OrderedSet as _FactSet

#_FactSet=set                                # The Python standard set class. Note
                                           # fails some unit tests because I'm
                                           # testing for the ordering.

# Note: Some other 3rd party libraries that were tried but performanced worse on
# a basic FactBase creation process:
#
#from ordered_set import OrderedSet as _FactSet

#from orderedset import OrderedSet as _FactSet   # Note: broken implementation so
                                               # fails some unit tests - union
                                               # operator only accepts a single
                                               # argument

#from blist import sortedset as _FactSet
#from sortedcontainers import SortedSet as _FactSet
# ------------------------------------------------------------------------------

__all__ = [
    '_FactSet',
    'RawField',
    'IntegerField',
    'StringField',
    'ConstantField',
    'SimpleField',
    'Placeholder',
    'Predicate',
    'ComplexTerm',
    'FactBase',
    'SymbolPredicateUnifier',
    'ContextBuilder',
    'Select',
    'Delete',
    'TypeCastSignature',
    'refine_field',
    'combine_fields',
    'simple_predicate',
    'desc',
    'asc',
    'unify',
    'path',
    'hashable_path',
    'ph_',
    'ph1_',
    'ph2_',
    'ph3_',
    'ph4_',
    'not_',
    'and_',
    'or_',
    'make_function_asp_callable',
    'make_method_asp_callable'
    ]

#------------------------------------------------------------------------------
# Global
#------------------------------------------------------------------------------
#g_logger = logging.getLogger(__name__)

# A compiled regular expression for matching an ASP constant term
g_constant_term_regex = re.compile("^_*[a-z][A-Za-z0-9_']*$")

#------------------------------------------------------------------------------
# A _classproperty decorator. (see
# https://stackoverflow.com/questions/3203286/how-to-create-a-read-only-class-property-in-python)
#------------------------------------------------------------------------------
class _classproperty(object):
    def __init__(self, getter):
        self.getter= getter
    def __get__(self, instance, owner):
        return self.getter(owner)

#------------------------------------------------------------------------------
# A descriptor for late initialisation of a read-only value. Helpful for delayed
# initialisation in metaclasses where an object needs to be created in the
# metaclass' __new__() call but can only be assigned in the __init__() call
# because the object needs to refer to the class being created in the
# metaclass. The assign() function can be called only once.
# ------------------------------------------------------------------------------
class _lateinit(object):
    def __init__(self,name):
        self._name = name
        self._value=None

    def assign(self, value):
        if self._value is not None:
            raise RuntimeError(("Error trying to reset the value for write-once "
                                "property {}").format(self._name))
        self._value=value

    def __get__(self, instance, owner):
        return self._value


#------------------------------------------------------------------------------
# PredicatePath class and supporting metaclass and functions. The PredicatePath
# is crucial to the Clorm API because it implements the intuitive syntax for
# referring to elements of a fact; the sign as well as the fields and sub-fields
# (eg., Pred.sign, Pred.a.b or Pred.a[0]).
#
# When the API user refers to a field (or sign) of a Predicate sub-class they
# are redirected to the corresponding PredicatePath object of that predicate
# sub-class.
#
# Overview of how it works:
#
# Every Predicate sub-class has an attribute for every field of a predicate as
# well as providing a index lookup by position. Every non-tuple Predicate also
# has a sign attribute to say whether the fact/term is positive or negative.
#
# So, for each Predicate sub-class a corresponding PredicatePath sub-class is
# created that contains all these elements; defined as attributes and indexed
# items. An instance of this PredicatePath is created for each Predicate; which
# forms the root of a tree linking to to other PredicatePath (base or
# sub-classes) that represent the sub-paths. The leaves of the tree are base
# PredicatePath class objects while the non-leaf elements are sub-classes of
# PredicatePath.
#
# The result of building the PredicatePath tree is that each element of the tree
# encodes the path from the root node to that element. This is then used as a
# mechanism for forming queries and extracting components from facts.
#
# PredicatePath overloads the boolean comparison operators to return a
# functor. This provides the mechanism to construct "where" clauses that form
# part of a query. For example, the statement "P.a.b == 2" is overloaded to
# return a functor that takes any P instance p and checks whether p.a.b == 2.
#
# ------------------------------------------------------------------------------

def _define_predicate_path_subclass(predicate_class):
    class_name = predicate_class.__name__ + "_PredicatePath"
    return type(class_name, (PredicatePath,), { "_predicate_class" : predicate_class })

class _PredicatePathMeta(type):
    def __new__(meta, name, bases, dct):

        # For the base class don't do anything else
        if name == "PredicatePath":
            return super(_PredicatePathMeta, meta).__new__(meta, name, bases, dct)

        # Note: _predicate_class must be defined when creating a subclass.
        predicate_class = dct["_predicate_class"]
        if not predicate_class:
            raise AttributeError(("The \"_predicate_class\" member variable was not "
                                  "specified for {}").format(name))

        # Maintain a lookup of the fields that are complex.
        ct_classes = {}
        dct["_complexterm_classes"] = ct_classes

        def _make_lookup_functor(key):
            return lambda self: self._subpath[key]

        # Create an attribute for each predicate class field that returns an instance
        # of a pathbuilder for each attribute
        for fa in predicate_class.meta:
            dct[fa.name] = property(_make_lookup_functor(fa.name))
            ct_class = fa.defn.complex
            if ct_class: ct_classes[fa.name] = ct_class

        # If the corresponding Predicate is not a tuple then we need to create a
        # "sign" attribute.
        if not predicate_class.meta.is_tuple:
            dct["sign"] = property(_make_lookup_functor("sign"))

        # The appropriate fields have been created
        return super(_PredicatePathMeta, meta).__new__(meta, name, bases, dct)


class PredicatePath(object, metaclass=_PredicatePathMeta):
    '''PredicatePath implements the intuitive query syntax.

    PredicatePath provides a specification for refer to elements of a fact; both
    the sign as well as the fields and sub-fields of that fact (eg., Pred.sign,
    Pred.a.b or Pred.a[0]).

    When the API user refers to a field (or sign) of a Predicate sub-class they
    are redirected to the corresponding PredicatePath object of that predicate
    sub-class.

    While instances of this class (and sub-classes) are externally exposed
    through the API, users should not explicitly instantiate instances
    themselves.

    PredicatePath subclasses provide attributes and indexed items for refering
    to sub-paths. When a user specifies 'Pred.a.b.c' the Predicate class 'Pred'
    seemslessly passes off to an associated PredicatePath object, which then
    returns a path corresponding to the specifications.

    Fields can be specified either by name through a chain of attributes or
    using the overloaded __getitem__ array function which allows for name or
    positional argument specifications.

    The other important aspect of the PredicatePath is that it overloads the
    boolean operators to return a Comparator functor. This is what allows for
    query specifications such as 'Pred.a.b == 2' or 'Pred.a.b == ph1_'

    Because the name 'meta' is a Clorm keyword and can't be used as a field name
    it is used as a property referring to an internal class with functions for
    use by the internals of the library. API users should not use this property.

    '''

    #--------------------------------------------------------------------------
    # An inner class that provides a hashable variant of a path. Because
    # PredicatePath co-ops the boolean comparision operators to return a
    # functor, rather than doing the normal behaviour of comparing two objects,
    # therefore it cannot be hashable (which required __eq__() __ne__() to work
    # properly). But we want to be able to use paths in a set or as a dictionary
    # key. So we provide a separate class to do this. The `path` property will
    # return the original (non-hashable) path.
    # --------------------------------------------------------------------------
    class Hashable(object):
        def __init__(self, path):
            self._path = path

        @property
        def path(self):
            return self._path

        def __hash__(self):
            return hash(self._path._pathseq)

        def __eq__(self, other):
            if not isinstance(other, self.__class__): return NotImplemented
            return self._path._pathseq == other._path._pathseq

        def __ne__(self, other):
            result = self.__eq__(other)
            if result is NotImplemented: return NotImplemented
            return not result

        def __str__(self):
            return str(self._path)

        def __repr__(self):
            return self.__str__()

    #--------------------------------------------------------------------------
    # An inner class to provide some useful functions in a sub-namespace. Need
    # this to avoid creating name conflicts, since each sub-class will have
    # attributes that mirror the field names of the associated
    # Predicate/Complex-term.  Internal API use only.
    # --------------------------------------------------------------------------

    class Meta(object):
        def __init__(self, parent):
            self._parent = parent

        #--------------------------------------------------------------------------
        # Properties of the parent PredicatePath instance
        # --------------------------------------------------------------------------
        @property
        def hashable(self):
            return self._parent._hashable

        # --------------------------------------------------------------------------
        # Is this a leaf path
        # --------------------------------------------------------------------------
        @property
        def is_leaf(self):
            return not hasattr(self, '_predicate_class')

        # --------------------------------------------------------------------------
        # Is this a root path (ie. the path corresponds to a predicate definition)
        # --------------------------------------------------------------------------
        @property
        def is_root(self):
            return len(self._parent._pathseq) == 1

        # --------------------------------------------------------------------------
        # Is this a path corresponding to a "sign" attribute
        # --------------------------------------------------------------------------
        @property
        def is_sign(self):
            return self._parent._pathseq[-1] == "sign"

        # --------------------------------------------------------------------------
        # Return the Predicate sub-class that is the root of this path
        # --------------------------------------------------------------------------
        @property
        def predicate(self):
            return self._parent._pathseq[0]

        #--------------------------------------------------------------------------
        # get the RawField instance associated with this path. If the path is a
        # root path or a sign path then it won't have an associated field so
        # will return None
        # --------------------------------------------------------------------------
        @property
        def field(self):
            return self._parent._field

        # --------------------------------------------------------------------------
        # All the subpaths of this path
        #--------------------------------------------------------------------------
        @property
        def subpaths(self):
            return self._parent._allsubpaths

        #--------------------------------------------------------------------------
        # Functions that do something with the parent PredicatePath instance
        #--------------------------------------------------------------------------

        #--------------------------------------------------------------------------
        # Return an OrderBy object for specifying sorting in ascending or
        # descending order. Used by the Select query.
        # --------------------------------------------------------------------------
        def asc(self):
            return OrderBy(self._parent, asc=True)
        def desc(self):
            return OrderBy(self._parent, asc=False)

        #--------------------------------------------------------------------------
        # Resolve (extract the component) the path wrt a fact
        # --------------------------------------------------------------------------
        def resolve(self, fact):
            pseq = self._parent._pathseq
            if type(fact) != pseq[0]:
                raise TypeError("{} is not of type {}".format(fact, pseq[0]))
            value = fact
            for name in pseq[1:]: value = value.__getattribute__(name)
            return value

    #--------------------------------------------------------------------------
    # Return the underlying meta object with useful functions
    # Internal API use only
    #--------------------------------------------------------------------------
    @property
    def meta(self):
        return self._meta

    #--------------------------------------------------------------------------
    # Takes a pathseq - which is a sequence where the first element must be a
    # Predicate class and subsequent elements are strings refering to
    # attributes.
    #--------------------------------------------------------------------------
    def __init__(self, pathseq):
        self._meta = PredicatePath.Meta(self)
        self._pathseq = tuple(pathseq)
        self._subpath = {}
        self._allsubpaths = tuple([])
        self._field = self._get_field()
        self._hashable = PredicatePath.Hashable(self)

        if not pathseq or not inspect.isclass(pathseq[0]) or \
           not issubclass(pathseq[0], Predicate):
            raise TypeError("Invalid path sequence for PredicatePath: {}".format(pathseq))

        # If this is a leaf path (instance of the base PredicatePath class) then
        # there will be no sub-paths so nothing else to do.
        if not hasattr(self, '_predicate_class'): return

        # Iteratively build the tree of PredicatePaths corresponding to the
        # searchable elements. Elements corresponding to non-complex terms will
        # have leaf PredicatePaths while the complex ones will have appropriate
        # sub-classed PredicatePaths.
        for fa in self._predicate_class.meta:
            name = fa.name
            idx = fa.index
            if name in self._complexterm_classes:
                path_cls = self._complexterm_classes[name].meta.path_class
            else:
                path_cls = PredicatePath
            path = path_cls(list(self._pathseq) + [name])
            self._subpath[name] = path
            self._subpath[idx] = path

        # Add the sign if it's not a tuple
        if not self._predicate_class.meta.is_tuple:
            self._subpath["sign"] = PredicatePath(list(self._pathseq) + ["sign"])

        # A list of the unique subpaths
        self._allsubpaths = tuple([sp for key,sp in self._subpath.items() \
                                   if not isinstance(key,int)])

    #--------------------------------------------------------------------------
    # Helper function to compute the field of the path (or None if not exists)
    # --------------------------------------------------------------------------
    def _get_field(self):
        if len(self._pathseq) <= 1: return None
        if self._pathseq[-1] == "sign": return None
        predicate = self._pathseq[0]
        for name in self._pathseq[1:]:
            field = predicate.meta[name].defn
            if field.complex: predicate = field.complex
        return field

    #--------------------------------------------------------------------------
    # A PredicatePath instance is a functor that resolves a fact wrt the path
    # --------------------------------------------------------------------------
    def __call__(self, fact):
        return self._meta.resolve(fact)

    #--------------------------------------------------------------------------
    # Get all field path builder corresponding to an index
    # --------------------------------------------------------------------------
    def __getitem__(self, key):
        try:
            return self._subpath[key]
        except:
            if self.meta.is_leaf:
                raise KeyError("Leaf path {} has no sub-paths".format(self))
            msg = "{} is not a valid positional argument for {}"
            raise KeyError(msg.format(key, self._predicate_class))

    #--------------------------------------------------------------------------
    # Overload the boolean operators to return a functor
    #--------------------------------------------------------------------------
    def __eq__(self, other):
        return PredicatePathComparator(operator.eq, self, other)
    def __ne__(self, other):
        return PredicatePathComparator(operator.ne, self, other)
    def __lt__(self, other):
        return PredicatePathComparator(operator.lt, self, other)
    def __le__(self, other):
        return PredicatePathComparator(operator.le, self, other)
    def __gt__(self, other):
        return PredicatePathComparator(operator.gt, self, other)
    def __ge__(self, other):
        return PredicatePathComparator(operator.ge, self, other)

    #--------------------------------------------------------------------------
    # String representation
    # --------------------------------------------------------------------------

    def __str__(self):
        if len(self._pathseq) == 1: return self._pathseq[0].__name__

        tmp = ".".join(self._pathseq[1:])
        return self._pathseq[0].__name__ + "." + tmp

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# API function to return the PredicatePath for the predicate class itself. This
# is the best way to support syntax such as "Pred == ph1_" in a query without
# trying to do strange overloading of the class comparison operator.
# ------------------------------------------------------------------------------

def path(arg):
    '''Return the field path corresponding to a predicate.'''
    if inspect.isclass(arg) and issubclass(arg, Predicate):
        return arg.meta.path
    raise TypeError("{} is not a Predicate class".format(arg))

#------------------------------------------------------------------------------
# API function to return the PredicatePath.Hashable instance for a path
# ------------------------------------------------------------------------------

def hashable_path(arg):
    '''Return a PredicatePath.Hashable instance for a path or Predicate sub-class.

    A hashable path can be used in a set or dictionary key. If the argument is a
    path then returns the hashable version (the original path can be accessed
    from the hashable's "path" property). If the argument is a Predicate
    sub-class then returns the hashable path corresponding to the root path for
    that predicate class.

    '''
    if inspect.isclass(arg) and issubclass(arg, Predicate):
        return arg.meta.path.meta.hashable
    elif isinstance(arg, PredicatePath):
        return arg.meta.hashable
    raise TypeError(("Invalid argument {} (type: {}). Expecting a Predicate sub-class "
                     "or path").format(arg, type(arg)))

#------------------------------------------------------------------------------
# Helper function to check if a second set of keys is a subset of a first
# set. If it is not it returns the unrecognised keys. Useful for checking a
# function that uses **kwargs.
# ------------------------------------------------------------------------------

def _check_keys(validkeys, inputkeys):
    if not inputkeys.issubset(validkeys): return inputkeys-validkeys
    return set([])



#------------------------------------------------------------------------------
# RawField class captures the definition of a logical term ("which we will call
# a field") between python and clingo.
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

def _rfm_constructor(self, *args, **kwargs):
    # Check the match between positional and keyword arguments
    if "default" in kwargs and len(args) > 0:
        raise TypeError(("Field constructor got multiple values for "
                         "argument 'default'"))
    if "index" in kwargs and len(args) > 1:
        raise TypeError(("Field constructor got multiple values for "
                         "argument 'index'"))
    if len(args) > 2:
        raise TypeError(("Field constructor takes from 0 to 2 positional"
                         "arguments but {} given").format(len(args)))

    # Check for bad positional arguments
    badkeys = _check_keys(set(["default","index"]), set(kwargs.keys()))
    if badkeys:
        mstr = "Field constructor got unexpected keyword arguments: "
        if len(badkeys) == 1:
            mstr = "Field constructor got an unexpected keyword argument: "
        raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

    if "default" in kwargs: self._default = (True, kwargs["default"])
    elif len(args) > 0: self._default = (True, args[0])
    else: self._default = (False,None)

    if "index" in kwargs: self._index = kwargs["index"]
    elif len(args) > 1: self._index = args[1]
    else: self._index=False

    if not self._default[0]: return
    dval = self._default[1]

    # Check that the default is a valid value. If the default is a callable then
    # we can't do this check because it could break a counter type procedure.
    if not callable(dval):
        try:
            self.pytocl(dval)
        except (TypeError,ValueError):
            raise TypeError("Invalid default value \"{}\" for {}".format(
                dval, type(self).__name__))

class _RawFieldMeta(type):
    def __new__(meta, name, bases, dct):

        # Add a default initialiser if one is not already defined
        if "__init__" not in dct:
            dct["__init__"] = _rfm_constructor

        dct["_fpb"] = _lateinit("{}._fpb".format(name))

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
        def _raise_cltopy_nie(cls,v):
            msg=("'{}' is only partially specified and has no "
                 "Clingo to Python (cltopy) conversion").format(name)
            raise NotImplementedError(msg)
        def _raise_pytocl_nie(cls,v):
            msg=("'{}' is only partially specified and has no "
                 "Python to Clingo (cltopy) conversion").format(name)
            raise NotImplementedError(msg)

        if "cltopy" in dct:
            dct["cltopy"] = classmethod(_make_cltopy(dct["cltopy"]))
        else:
            dct["cltopy"] = classmethod(_raise_cltopy_nie)

        if "pytocl" in dct:
            dct["pytocl"] = classmethod(_make_pytocl(dct["pytocl"]))
        else:
            dct["pytocl"] = classmethod(_raise_pytocl_nie)


        # For complex-terms provide an interface to the underlying complex term
        # object
        if "complex" in dct:
            dct["complex"] = _classproperty(dct["complex"])
        else:
            dct["complex"] = _classproperty(lambda cls: None)
#            dct["complex"] = _classproperty(None)

        return super(_RawFieldMeta, meta).__new__(meta, name, bases, dct)

    def __init__(cls, name, bases, dct):

        return super(_RawFieldMeta, cls).__init__(name, bases, dct)

#------------------------------------------------------------------------------
# Field definitions. All fields have the functions: pytocl, cltopy,
# and unifies, and the properties: default and has_default
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

    Note: the ``cltopy`` and ``pytocl`` functions are legitmately allowed to
    throw either a ``TypeError`` or ``ValueError`` exception when provided with
    bad input. These exceptions will be treated as a failure to unify when
    trying to unify clingo symbols to facts. However, any other exception is
    passed through as a genuine error.  This should be kept in mind if you are
    writing your own field class.

    Example:
       .. code-block:: python

           import datetime

           class DateField(StringField):
                     pytocl = lambda dt: dt.strftime("%Y%m%d")
                     cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()


       Because ``DateField`` sub-classes ``StringField``, rather than
       sub-classing ``RawField`` directly, it forms a longer data translation
       chain:

         clingo symbol object -- RawField -- StringField -- DateField -- python date object

       Here the ``DateField.cltopy`` is called at the end of the chain of
       translations, so it expects a Python string object as input and outputs a
       date object. ``DateField.pytocl`` does the opposite and inputs a date
       object and is expected to output a Python string object.

    Args:

      default: A default value (or function) to be used when instantiating a
       ``Predicate`` or ``ComplexTerm`` object. If a Python ``callable`` object is
       specified (i.e., a function or functor) then it will be called (with no
       arguments) when the predicate/complex-term object is instantiated.

      index (bool): Determine if this field should be indexed by default in a
        ``FactBase```. Defaults to ``False``.

    """

    @classmethod
    def cltopy(cls, v):
        """Called when translating data from Clingo to Python"""
        return v

    @classmethod
    def pytocl(cls, v):
        """Called when translating data from Python to Clingo"""
        return v

    @classmethod
    def unifies(cls, v):
        """Returns whether a `Clingo.Symbol` can be unified with this type of term"""
        try:
            cls.cltopy(v)
        except (TypeError,ValueError):
            return False
        return True

    # Internal property - not part of official API
    @_classproperty
    def complex(cls):
        return None

    @property
    def has_default(self):
        """Returns whether a default value has been set"""
        return self._default[0]

    @property
    def default(self):
        """Returns the default value for the field (or ``None`` if no default was set).

        Note: 1) if a function was specified as the default then testing
        ``default`` will call this function and return the value, 2) if your
        RawField sub-class allows a default value of ``None`` then you need to
        check the ``has_default`` property to distinguish between no default
        value and a ``None`` default value.

        """
        if not self._default[0]: return None
        if callable(self._default[1]): return self._default[1]()
        return self._default[1]

    @property
    def index(self):
        """Returns whether this field should be indexed by default in a `FactBase`"""
        return self._index

#------------------------------------------------------------------------------
# StringField and IntegerField are simple sub-classes of RawField
#------------------------------------------------------------------------------

class StringField(RawField):
    """A field to convert between a Clingo.String object and a Python string."""

    def cltopy(raw):
        if raw.type != clingo.SymbolType.String:
            raise TypeError("Object {0} is not a clingo.String symbol")
        return raw.string

    pytocl = lambda v: clingo.String(v)

class IntegerField(RawField):
    """A field to convert between a Clingo.Number object and a Python integer."""
    def cltopy(raw):
        if raw.type != clingo.SymbolType.Number:
            raise TypeError("Object {0} is not a clingo.Number symbol")
        return raw.number

    pytocl = lambda v: clingo.Number(v)

#------------------------------------------------------------------------------
# ConstantField is more complex than basic string or integer because the value
# can be negated. A heavy handed way to deal with this would be to create a
# unary ComplexTerm subclass for every constant string value. But this is an
# expensive way of dealing with the boundary case of negated constants that will
# be used rarely (I've never seen it used in the wild).
#
# Instead we encode this as a string with a minus first symbol. The disadvantage
# of this approach is that detecting complementary terms will need to be done
# manually. But I think this is a good trade-off since it is very unusual to use
# negated terms in general and negated constants in particular.
# ------------------------------------------------------------------------------

class ConstantField(RawField):
    """A field to convert between a simple ``Clingo.Function`` object and a Python
    string.

    Note: currently ``ConstantField`` treats a string with a starting "-" as a
    negated constant. In hindsight this was a mistake and is now
    *deprecated*. While I don't think anyone actually used this functionality
    (since it was never documented) nevertheless I will keep it there until the
    Clorm version 2.0 release.

    """
    def cltopy(raw):
        if   (raw.type != clingo.SymbolType.Function or
              not raw.name or len(raw.arguments) != 0):
            raise TypeError("Object {0} is not a Simple symbol")
        return raw.name if raw.positive else "-{}".format(raw.name)

    def pytocl(v):
        if not isinstance(v,str):
            raise TypeError("Value '{}' is not a string".format(v))
        if v.startswith('-'): return clingo.Function(v[1:],[],False)
        return clingo.Function(v,[])


#------------------------------------------------------------------------------
# A SimpleField can handle any simple term (constant, string, integer).
#------------------------------------------------------------------------------

class SimpleField(RawField):
    """A class that represents a field corresponding to any simple term: *string*,
    *constant*, or *integer*.

    Converting from an ASP string, constant, or integer will produce the
    expected Python string or integer object. However, since ASP strings and
    constants both map to Python strings therefore converting from Python to ASP
    is less straightforward. In this case it uses a regular expression to
    determine if the string matches an ASP constant or if it should be treated
    as a quoted string.

    Because of this potential for ambiguity it is often better to use the
    distinct ``IntegerField``, ``ConstantField``, and ``StringField`` classes
    rather than the ``SimpleField`` class.

    """
    def cltopy(raw):
        if raw.type == clingo.SymbolType.String:
            return raw.string
        elif raw.type == clingo.SymbolType.Number:
            return raw.number
        elif raw.type == clingo.SymbolType.Function:
            if len(raw.arguments) == 0 and raw.positive:
                return raw.name
        raise TypeError("Not a simple term (string/constant/integer)")

    def pytocl(value):
        if isinstance(value,int):
            return clingo.Number(value)
        elif not isinstance(value,str):
            raise TypeError("No translation to a simple term")
        if g_constant_term_regex.match(value):
            return clingo.Function(value,[])
        else:
            return clingo.String(value)

#------------------------------------------------------------------------------
# refine_field is a function that creates a sub-class of a RawField (or RawField
# sub-class). It restricts the set of allowable values based on a functor or an
# explicit set of values.
# ------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# Helper function to define a sub-class of a RawField (or sub-class) that
# restricts the allowable values.
# ------------------------------------------------------------------------------

# Support for refine_field
def _refine_field_functor(subclass_name, field_class, valfunc):
    def _test_value(v):
        if not valfunc(v):
            raise TypeError(("Invalid value \"{}\" for {} (restriction of "
                             "{})").format(v, subclass_name, field_class.__name__))
        return v

    return type(subclass_name, (field_class,),
                { "pytocl": _test_value,
                  "cltopy": _test_value})

# Support for refine_field
def _refine_field_collection(subclass_name, field_class, values):
    # Check that the values are all valid
    for v in values:
        try:
            out = field_class.pytocl(v)
        except (TypeError,ValueError):
            raise TypeError("Invalid value \"{}\" for {}".format(
                v, field_class.__name__))

    # Now define the restricted pytocl and cltopy functions
    fs = frozenset(values)
    def _test_value(v):
        if v not in fs:
            raise TypeError(("Invalid value \"{}\" for {} (restriction of "
                             "{})").format(v, subclass_name, field_class.__name__))
        return v

    return type(subclass_name, (field_class,),
                { "pytocl": _test_value,
                  "cltopy": _test_value})

def refine_field(*args):
    """Factory function that returns a field sub-class with restricted values.

    A helper factory function to define a sub-class of a RawField (or sub-class)
    that restricts the allowable values. For example, if you have a constant in
    a predicate that is restricted to the days of the week ("monday", ...,
    "sunday"), you then want the Python code to respect that restriction and
    throw an error if the user enters the wrong value (e.g. a spelling error
    such as "wednsday"). Restrictions are also useful for unification if you
    want to unify based on some specific value.

    Example:
       .. code-block:: python

           WorkDayField = refine_field("WorkDayField", ConstantField,
              ["monday", "tuesday", "wednesday", "thursday", "friday"])

          class WorksOn(Predicate):
              employee = ConstantField()
              workday = WorkdDayField()

    Instead of a passing a list of values the last parameter can also be a
    function/functor. If the last parameter is callable then it is treated as a
    function that takes a field value and returns true if it is a valid value.

    Example:
       .. code-block:: python

           PosIntField = refine_field("PosIntField", NumberField,
              lambda x : x >= 0)

    The function must be called using positional arguments with either 2 or 3
    arguments. For the 3 argument case a class name is specified for the name of
    the new field. For the 2 argument case an anonymous field class name is
    automatically generated.

    Example:
       .. code-block:: python

           WorkDayField = refine_field(ConstantField,
              ["monday", "tuesday", "wednesday", "thursday", "friday"])

    Args:
       optional subclass_name: new sub-class name (anonymous if none specified).
       field_class: the field that is being sub-classed
       values|functor: a list of values or a functor to determine validity

    """
    largs = len(args)
    if largs == 2:
        field_class = args[0]
        values = args[1]
        subclass_name = field_class.__name__ + "_Restriction"
    elif largs == 3:
        subclass_name = args[0]
        field_class = args[1]
        values = args[2]
    else:
        raise TypeError("refine_field() missing required positional arguments")

    if not inspect.isclass(field_class) or not issubclass(field_class,RawField):
        raise TypeError("{} is not a subclass of RawField".format(field_class))

    if callable(values):
        return _refine_field_functor(subclass_name, field_class, values)
    else:
        return _refine_field_collection(subclass_name, field_class, values)



#------------------------------------------------------------------------------
# combine_fields is a function that creates a sub-class of RawField that
# combines existing RawField subclasses. It is the mirror of the refine_field
# helper function.
# ------------------------------------------------------------------------------

def combine_fields(*args):
    """Factory function that returns a field sub-class that combines other fields

    A helper factory function to define a sub-class of RawField that combines
    other RawField subclasses. The subclass is defined such that it's
    ``pytocl()`` (respectively ``cltopy()``) function tries to return the value
    returned by the underlying sub-field's ``pytocl()`` ( (respectively
    ``cltopy()``) function. If the first sub-field fails then the second is
    called, and so on until there are no matching sub-fields. If there is no
    match then a TypeError is raised.

    Example:
       .. code-block:: python

       MixedField = combine_fields("MixedField",[ConstantField,IntegerField])

    Args:
       optional subclass_name: new sub-class name (anonymous if none specified).
       field_subclasses: the fields to combine

    """

    # Deal with the optional subclass name
    largs=len(args)
    if largs == 1:
        subclass_name="AnonymousCombinedRawField"
        fields=args[0]
    elif largs == 2:
        subclass_name=args[0]
        fields=args[1]
    else:
        raise TypeError("combine_fields() missing or invalid arguments")

    # Must combine at least two fields otherwise it doesn't make sense
    for f in fields:
        if not inspect.isclass(f) or not issubclass(f,RawField):
            raise TypeError("{} is not RawField or a sub-class".format(f))
    if len(fields) < 2:
        raise TypeError("Must specify at least two fields to combine")

    fields=tuple(fields)
    def _pytocl(v):
        for f in fields:
            try:
                return f.pytocl(v)
            except (TypeError, ValueError):
                pass
        raise TypeError("No combined pytocl() match for value {}".format(v))

    def _cltopy(r):
        for f in fields:
            try:
                return f.cltopy(r)
            except (TypeError, ValueError):
                pass
        raise TypeError("No combined cltopy() match for clingo symbol {}".format(r))

    return type(subclass_name, (RawField,),
                { "pytocl": _pytocl,
                  "cltopy": _cltopy})

#------------------------------------------------------------------------------
# Specification of an ordering over a field of a predicate/complex-term
#------------------------------------------------------------------------------
class OrderBy(object):
    def __init__(self, path, asc):
        self._path = path
        self.asc = asc
    def compare(self, a,b):
        va = self._path(a)
        vb = self._path(b)
        if  va == vb: return 0
        if self.asc and va < vb: return -1
        if not self.asc and va > vb: return -1
        return 1

    @property
    def path(self):
        return self._path

    def __str__(self):
        return "OrderBy(path={},asc={})".format(self._path, self.asc)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Helper functions to return a OrderBy in descending and ascending order. Input
# is a PredicatePath. The ascending order function is provided for completeness
# since the order_by parameter will treat a path as ascending order by default.
# ------------------------------------------------------------------------------
def desc(path):
    return path.meta.desc()
def asc(path):
    return path.meta.asc()

#------------------------------------------------------------------------------
# FieldAccessor - a Python descriptor (similar to a property) to access the
# value associated with a field. It has a __get__ overload to return the data of
# the field if the function is called from an instance, but if called by the
# class then returns the appropriate PredicatePath (that can be used to specify
# a query).
# ------------------------------------------------------------------------------
class FieldAccessor(object):
    def __init__(self, name, index, defn):
        self._name = name
        self._index = index
        self._defn = defn
        self._parent_cls = None

    @property
    def name(self): return self._name

    @property
    def index(self): return self._index

    @property
    def defn(self): return self._defn

    @property
    def parent(self): return self._parent_cls

    @parent.setter
    def parent(self, pc):
        if self._parent_cls:
            raise RuntimeError(("Trying to reset the parent for a "
                                "FieldAccessor doesn't make sense"))
        self._parent_cls = pc

    def __get__(self, instance, owner=None):
        if not instance:
            # Return the PredicatePath object corresponding to this field
            return self.parent.meta.path[self._index]

        if not isinstance(instance, self._parent_cls):
            raise TypeError(("field {} doesn't match type "
                             "{}").format(self, type(instance).__name__))
        return instance._field_values[self._index]

    def __set__(self, instance, value):
        raise AttributeError(("Cannot modify {}.{}: field values are "
                              "read-only").format(self.parent.__name__, self.name))

#------------------------------------------------------------------------------
# SignAccessor - a Python descriptor to access the sign value of a
# Predicate instance. It has a __get__ overload to return the value of
# the sign if the function is called from an instance, but if called by the
# class then returns the appropriate PredicatePath (that can be used to
# specify a query).
# ------------------------------------------------------------------------------

class SignAccessor(object):
    def __init__(self):
        self._parent_cls = None

    @property
    def parent(self): return self._parent_cls

    @parent.setter
    def parent(self, pc):
        if self._parent_cls:
            raise RuntimeError(("Trying to reset the parent for a "
                                "SignAccessor doesn't make sense"))
        self._parent_cls = pc

    def __get__(self, instance, owner=None):
        if not instance:
            # Return the PredicatePath object corresponding to this sign
            return self.parent.meta.path.sign

        if not isinstance(instance, self._parent_cls):
            raise TypeError(("sign {} doesn't match type "
                             "{}").format(self, type(instance).__name__))
        return instance._raw.positive

    def __set__(self, instance, value):
        raise AttributeError(("Cannot modify {}.sign: sign and field values "
                              "are read-only").format(self.parent.__name__))


#------------------------------------------------------------------------------
# Helper function to cleverly handle a field definition. If the input is an
# instance of a RawField then simply return the object. If it is a subclass of
# RawField then return an instantiation of the object. If it is a tuple then
# treat it as a recursive definition and return an instantiation of a
# dynamically created complex-term corresponding to a tuple (with the class name
# ClormAnonTuple).
# ------------------------------------------------------------------------------

def _get_field_defn(defn):
    errmsg = ("Unrecognised field definition object '{}'. Expecting: "
              "1) RawField (sub-)class, 2) RawField (sub-)class instance, "
              "3) a tuple containing a field definition")

    # If we get a RawField (sub-)class then return an instance with default init
    if inspect.isclass(defn):
        if not issubclass(defn,RawField): raise TypeError(errmsg.format(defn))
        return defn()

    # Simplest case of a RawField instance
    if isinstance(defn,RawField): return defn

    # Expecting a tuple and treat it as a recursive definition
    if not isinstance(defn, tuple): raise TypeError(errmsg.format(defn))

    # NOTE: I was using a dict rather than OrderedDict which just happened to
    # work. Apparently, in Python 3.6 this was an implmentation detail and
    # Python 3.7 it is a language specification (see:
    # https://stackoverflow.com/questions/1867861/how-to-keep-keys-values-in-same-order-as-declared/39537308#39537308).
    # However, since Clorm is meant to be Python 3.5 compatible change this to
    # use an OrderedDict.
    # proto = { "arg{}".format(i+1) : _get_field_defn(d) for i,d in enumerate(defn) }
    proto = collections.OrderedDict([("arg{}".format(i+1), _get_field_defn(d))
                                     for i,d in enumerate(defn)])
    proto['Meta'] = type("Meta", (object,), {"is_tuple" : True, "_anon" : True})
    ct = type("ClormAnonTuple", (Predicate,), proto)
    return ct.Field()


#------------------------------------------------------------------------------
# Return the list of field_paths associated with a predicate (ignoring the base
# predicate path itself).
# ------------------------------------------------------------------------------
def _get_paths(predicate):
    def get_subpaths(path):
        paths=[]
        for subpath in path.meta.subpaths:
            paths.append(subpath)
            paths.extend(get_subpaths(subpath))
        return paths

    return get_subpaths(path(predicate))

#------------------------------------------------------------------------------
# Return the list of field_paths that are specified as indexed
#------------------------------------------------------------------------------
def _get_paths_for_default_indexed_fields(predicate):
    def is_indexed(path):
        field = path.meta.field
        if field and field.index: return True
        return False
    return filter(is_indexed, _get_paths(predicate))

# ------------------------------------------------------------------------------
# Determine if an attribute name has the pattern of an official attribute
# (ie.  has name of the form __XXX__).
# ------------------------------------------------------------------------------

def _magic_name(name):
    if not name.startswith("__"): return False
    if not name.endswith("__"): return False
    if len(name) <= 4: return False
    if name[2] == '_': return False
    if name[-3] == '_': return False
    return True

#------------------------------------------------------------------------------
# The Predicate base class and supporting functions and classes
# ------------------------------------------------------------------------------

#--------------------------------------------------------------------------
# One PredicateDefn object for each Predicate sub-class
#--------------------------------------------------------------------------
class PredicateDefn(object):

    """Encapsulates some meta-data for a Predicate definition.

    Each Predicate class will have a corresponding PredicateDefn object that specifies some
    introspective properties of the predicate/complex-term.

    """

    def __init__(self, name, field_accessors, anon=False,sign=None):
        self._name = name
        self._byidx = tuple(field_accessors)
        self._byname = { f.name : f for f in field_accessors }
        self._arity = len(self._byidx)
        self._anon = anon
        self._key2canon = { f.index : f.name for f in field_accessors }
        self._key2canon.update({f.name : f.name for f in field_accessors })
        self._parent_cls = None
        self._indexed_fields = ()
        self._sign = sign

    @property
    def name(self):
        """Returns the string name of the predicate or complex term"""
        return self._name

    @property
    def arity(self):
        """Returns the arity of the predicate"""
        return self._arity

    @property
    def sign(self):
        """Returns the sign that this Predicate signature can unify against

           If the sign is ``True`` then this Predicate definition will only
           unify against positive literals. If the sign is ``False`` then it
           will only unify against negative literals, and if ``None`` then it
           will unify against either positive or negative literals.

        """
        return self._sign

    @property
    def is_tuple(self):
        """Returns true if the definition corresponds to a tuple"""
        return self.name == ""

    # Not sure if this property serves any useful purpose - but it probably
    # shouldn't be user accessible so shouldn't be documented.
    @property
    def anonymous(self):
        return self._anon

    def canonical(self, key):
        """Returns the canonical name for a field"""
        return self._key2canon[key]

    def keys(self):
        """Returns the names of fields"""
        return self._byname.keys()

    @property
    def indexes(self):
        """Return the list of fields that have been specified as indexed"""
        return self._indexed_fields

    @indexes.setter
    def indexes(self,indexed_fields):
        if self._indexed_fields:
            raise RuntimeError(("Trying to reset the indexed fields for a "
                                "PredicateDefn doesn't make sense"))
        self._indexed_fields = tuple(indexed_fields)

    # Internal property
    @property
    def parent(self):
        """Return the Predicate/Complex-term associated with this definition"""
        return self._parent_cls

    # Internal property
    @parent.setter
    def parent(self, pc):
        if self._parent_cls:
            raise RuntimeError(("Trying to reset the parent for a "
                                "PredicateDefn doesn't make sense"))
        self._parent_cls = pc
        self._path_class = _define_predicate_path_subclass(pc)
        self._path = self._path_class([pc])

    # Internal property
    @property
    def path(self): return self._path

    # Internal property
    @property
    def path_class(self): return self._path_class

    def __len__(self):
        '''Returns the number of fields'''
        return len(self._byidx)

    def __getitem__(self, key):
        '''Find a field by position index or by name'''
        try:
            idx = int(key)
            return self._byidx[idx]
        except ValueError as e:
            return self._byname[key]

    def __iter__(self):
        return iter(self._byidx)

# ------------------------------------------------------------------------------
# Helper function that performs some data conversion on a value to make it match
# a field's input. If the value is a tuple and the field definition is a
# complex-term then it tries to create an instance corresponding to the
# tuple. Otherwise simply returns the value.
# ------------------------------------------------------------------------------

def _preprocess_field_value(field_defn, v):
    predicate_cls = field_defn.complex
    if not predicate_cls: return v
    mt = predicate_cls.meta
    if isinstance(v, predicate_cls): return v
    if (mt.is_tuple and isinstance(v,Predicate) and v.meta.is_tuple) or \
       isinstance(v, tuple):
        if len(v) != len(mt):
            raise ValueError(("mis-matched arity between field {} (arity {}) and "
                             " value (arity {})").format(field_defn, len(mt), len(v)))
        return predicate_cls(*v)
    else:
        return v

# ------------------------------------------------------------------------------
# Helper functions for PredicateMeta class to create a Predicate
# class constructor.
# ------------------------------------------------------------------------------

# Construct a Predicate via an explicit (raw) clingo.Symbol object
def _predicate_init_by_raw(self, **kwargs):
    if len(kwargs) != 1:
        raise ValueError("Invalid combination of keyword arguments")
    raw = kwargs["raw"]
    self._raw = raw
    try:
        cls=type(self)
        if raw.type != clingo.SymbolType.Function: raise ValueError()
        arity=len(raw.arguments)
        if raw.name != cls.meta.name: raise ValueError()
        if arity != cls.meta.arity: raise ValueError()
        if cls.meta.sign is not None and cls.meta.sign != raw.positive: raise ValueError()
        self._field_values = [ f.defn.cltopy(raw.arguments[f.index]) for f in self.meta ]
    except (TypeError,ValueError):
        raise ValueError(("Failed to unify clingo.Symbol object {} with "
                          "Predicate class {}").format(raw, cls.__name__))

# Construct a Predicate via the field keywords
def _predicate_init_by_keyword_values(self, **kwargs):
    argnum=0
    self._field_values = []
    clingoargs = []
    for f in self.meta:
        if f.name in kwargs:
            v= _preprocess_field_value(f.defn, kwargs[f.name])
            argnum += 1
        elif f.defn.has_default:
            # Note: must be careful to get the default value only once in case
            # it is a function with side-effects.
            v = _preprocess_field_value(f.defn, f.defn.default)
        else:
            raise TypeError(("Missing argument for field \"{}\" (which has no "
                             "default value)").format(f.name))

        # Set the value for the field
        self._field_values.append(v)
        clingoargs.append(f.defn.pytocl(v))

    # Calculate the sign of the literal and check that it matches the allowed values
    if "sign" in kwargs:
        sign = bool(kwargs["sign"])
        argnum += 1
    else:
        sign = True

    if len(kwargs) > argnum:
        args=set(kwargs.keys())
        expected=set([f.name for f in self.meta])
        raise TypeError(("Unexpected keyword arguments for \"{}\" constructor: "
                          "{}").format(type(self).__name__, ",".join(args-expected)))
    if self.meta.sign is not None:
        if sign != self.meta.sign:
            raise ValueError(("Predicate {} is defined to only allow {} signed "
                              "instances").format(self.__class__, self.meta.sign))

    # Create the raw clingo.Symbol object
    self._raw = clingo.Function(self.meta.name, clingoargs, sign)

# Construct a Predicate using keyword arguments
def _predicate_init_by_positional_values(self, *args, **kwargs):
    argc = len(args)
    arity = len(self.meta)
    if argc != arity:
        raise ValueError("Expected {} arguments but {} given".format(argc,arity))

    clingoargs = []
    self._field_values = []
    for f in self.meta:
        v = _preprocess_field_value(f.defn, args[f.index])
        self._field_values.append(v)
        clingoargs.append(f.defn.pytocl(v))

    # Calculate the sign of the literal and check that it matches the allowed values
    sign = bool(kwargs["sign"]) if "sign" in kwargs else True
    if self.meta.sign is not None and sign != self.meta.sign:
        raise ValueError(("Predicate {} is defined to only allow {} "
                          "instances").format(type(self).__name__, self.meta.sign))

    # Create the raw clingo.Symbol object
    self._raw = clingo.Function(self.meta.name, clingoargs, sign)

# Constructor for every Predicate sub-class
def _predicate_constructor(self, *args, **kwargs):
    if len(args) > 0:
        if len(kwargs) > 1 or (len(kwargs) == 1 and "sign" not in kwargs):
            raise ValueError(("Invalid Predicate initialisation: only \"sign\" is a "
                             "valid keyword argument when combined with positional "
                              "arguments: {}").format(kwargs))
        _predicate_init_by_positional_values(self, *args,**kwargs)
    elif "raw" in kwargs:
        _predicate_init_by_raw(self, **kwargs)
    else:
        _predicate_init_by_keyword_values(self, **kwargs)

def _predicate_base_constructor(self, *args, **kwargs):
    raise TypeError(("Predicate/ComplexTerm must be sub-classed"))

#------------------------------------------------------------------------------
# Metaclass constructor support functions to create the fields
#------------------------------------------------------------------------------

# Generate a default predicate name from the Predicate class name.
def _predicatedefn_default_predicate_name(class_name):

    # If first letter is lower-case then do nothing
    if class_name[0].islower(): return class_name

    # Otherwise, replace any sequence of upper-case only characters that occur
    # at the beginning of the string or immediately after an underscore with
    # lower-case equivalents. The sequence of upper-case characters can include
    # non-alphabetic characters (eg., numbers) and this will still be treated as
    # a single sequence of upper-case characters.  This covers basic naming
    # conventions: camel-case, snake-case, and acronyms.

    output=""
    incap=True
    for c in class_name:
        if c == '_': output += c ; incap = True ; continue
        if not c.isalpha(): output += c ; continue
        if not incap: output += c ; continue
        if c.isupper(): output += c.lower() ; continue
        else: output += c ; incap = False ; continue

    return output

# Detect a class definition for a ComplexTerm
def _is_complexterm_declaration(name,obj):
    if not inspect.isclass(obj): return False
    if not issubclass(obj,ComplexTerm): return False
    return obj.__name__ == name

# build the metadata for the Predicate - NOTE: this funtion returns a
# PredicateDefn instance but it also modified the dct paramater to add the fields. It
# also checks to make sure the class Meta declaration is error free: 1) Setting
# a name is not allowed for a tuple, 2) Sign controls if we want to allow
# unification against a positive literal only, a negative literal only or
# both. Sign can be True/False/None. By default sign is None (meaning both
# positive/negative) unless it is a tuple then it is positive only.

def _make_predicatedefn(class_name, dct):

    # Set the default predicate name
    pname = _predicatedefn_default_predicate_name(class_name)
    anon = False
    sign = None
    is_tuple = False

    if "Meta" in dct:
        metadefn = dct["Meta"]
        if not inspect.isclass(metadefn):
            raise TypeError("'Meta' attribute is not an inner class")

        # What has been defined
        name_def = "name" in metadefn.__dict__
        is_tuple_def = "is_tuple" in metadefn.__dict__
        sign_def = "sign" in metadefn.__dict__

        if name_def : pname = metadefn.__dict__["name"]
        if is_tuple_def : is_tuple = bool(metadefn.__dict__["is_tuple"])
        if "_anon" in metadefn.__dict__:
            anon = metadefn.__dict__["_anon"]

        if name_def and not pname:
            raise ValueError(("Empty 'name' attribute is invalid. Use "
                              "'is_tuple=True' if you want to define a tuple."))
        if name_def and is_tuple:
            raise ValueError(("Cannot specify a 'name' attribute if "
                              "'is_tuple=True' has been set"))
        elif is_tuple: pname = ""

        if is_tuple: sign = True       # Change sign default if is tuple

        if "sign" in  metadefn.__dict__: sign = metadefn.__dict__["sign"]
        if sign is not None: sign = bool(sign)

        if is_tuple and not sign:
            raise ValueError(("Tuples cannot be negated so specifying "
                              "'sign' is None or False is invalid"))

    reserved = set(["meta", "raw", "clone", "sign", "Field"])

    # Generate the fields - NOTE: this relies on dct being an OrderedDict()
    # which is true from Python 3.5+ (see PEP520
    # https://www.python.org/dev/peps/pep-0520/)
    fas= []
    idx = 0

    for fname, fdefn in dct.items():

        # Ignore entries that are not field declarations
        if fname == "Meta": continue
        if _magic_name(fname): continue
        if _is_complexterm_declaration(fname, fdefn): continue

        if fname in reserved:
            raise ValueError(("Error: invalid field name: '{}' "
                              "is a reserved keyword").format(fname))
        if fname.startswith('_'):
            raise ValueError(("Error: field names cannot start with an "
                              "underscore: {}").format(fname))
        try:
            fd = _get_field_defn(fdefn)
            fa = FieldAccessor(fname, idx, fd)
            dct[fname] = fa
            fas.append(fa)
            idx += 1
        except TypeError as e:
            raise TypeError("Error defining field '{}': {}".format(fname,str(e)))

    # Create the "sign" attribute - must be assigned a parent in the metaclass
    # __init__() call.
    dct["sign"] = SignAccessor()

    # Now create the PredicateDefn object
    return PredicateDefn(name=pname,field_accessors=fas, anon=anon,sign=sign)

# ------------------------------------------------------------------------------
# Define a RawField sub-class that corresponds to a Predicate/ComplexTerm
# sub-class. This RawField sub-class will convert to/from a complex-term
# instances and clingo symbol objects.
# ------------------------------------------------------------------------------

def _define_field_for_predicate(cls):
    if not issubclass(cls, Predicate):
        raise TypeError(("Class {} is not a Predicate/ComplexTerm "
                         "sub-class").format(cls))

    field_name = "{}Field".format(cls.__name__)
    def _pytocl(v):
        if isinstance(v,cls): return v.raw
        if isinstance(v,tuple):
            if len(v) != len(cls.meta):
                raise ValueError(("incorrect values to unpack (expected "
                                  "{})").format(len(cls.meta)))
            try:
                v = cls(*v)
                return v.raw
            except Exception:
                raise TypeError(("Failed to unify tuple {} with complex "
                                  "term {}").format(v,cls))
        raise TypeError("Value {} ({}) is not an instance of {}".format(v,type(v),cls))

    def _cltopy(v):
        return cls(raw=v)

    field = type(field_name, (RawField,),
                 { "pytocl": _pytocl, "cltopy": _cltopy,
                   "complex": lambda self: cls})
    return field

#------------------------------------------------------------------------------
# A Metaclass for the Predicate base class
#------------------------------------------------------------------------------
class _PredicateMeta(type):

    #--------------------------------------------------------------------------
    # Allocate the new metaclass
    #--------------------------------------------------------------------------
    def __new__(meta, name, bases, dct):
        if name == "Predicate":
            dct["_predicate"] = None
            dct["__init__"] = _predicate_base_constructor
            return super(_PredicateMeta, meta).__new__(meta, name, bases, dct)

        # Create the metadata AND populate dct - the class dict (including the fields)

        # Set the _meta attribute and constuctor
        dct["_meta"] = _make_predicatedefn(name, dct)
        dct["__init__"] = _predicate_constructor
        dct["_field"] = _lateinit("{}._field".format(name))

        parents = [ b for b in bases if issubclass(b, Predicate) ]
        if len(parents) == 0:
            raise TypeError("Internal bug: number of Predicate bases is 0!")
        if len(parents) > 1:
            raise TypeError("Multiple Predicate sub-class inheritance forbidden")

        return super(_PredicateMeta, meta).__new__(meta, name, bases, dct)

    def __init__(cls, name, bases, dct):
        if name == "Predicate":
            return super(_PredicateMeta, cls).__init__(name, bases, dct)

        # Set a RawField sub-class that converts to/from cls instances
        dct["_field"].assign(_define_field_for_predicate(cls))

        md = dct["_meta"]
        # The property attribute for each field can only be created in __new__
        # but the class itself does not get created until after __new__. Hence
        # we have to set the pointer within the field back to the this class
        # here. Similar argument applies for generating the field indexes
        md.parent = cls
        for field in md:
            dct[field.name].parent = cls
        md.indexes=_get_paths_for_default_indexed_fields(cls)

        # Assign the parent for the SignAccessor
        dct["sign"].parent = cls

        return super(_PredicateMeta, cls).__init__(name, bases, dct)

    # A Predicate subclass is an instance of this meta class. So to
    # provide querying of a Predicate subclass Blah by a positional
    # argument we need to implement __getitem__ for the metaclass.
    def __getitem__(self, idx):
        return self.meta.path[idx]

    def __iter__(self):
        return iter([self[k] for k in self.meta.keys()])

#------------------------------------------------------------------------------
# A base non-logical symbol that all predicate/complex-term declarations must
# inherit from. The Metaclass creates the magic to create the fields and the
# underlying clingo.Symbol object.
# ------------------------------------------------------------------------------

class Predicate(object, metaclass=_PredicateMeta):
    """Encapsulates an ASP predicate or complex term in an easy to access object.

    This is the heart of the ORM model for defining the mapping of a complex
    term or predicate to a Python object. ``ComplexTerm`` is simply an alias for
    ``Predicate``.

    Example:
       .. code-block:: python

           class Booking(Predicate):
               date = StringField(index = True)
               time = StringField(index = True)
               name = StringField(default = "relax")

           b1 = Booking("20190101", "10:00")
           b2 = Booking("20190101", "11:00", "Dinner")

    Field names can be any valid Python variable name subject to the following
    restrictions:

    - it cannot start with a "_", or
    - it cannot be be one of the following reserved words: "meta", "raw",
      "clone", or "Field".

    The constructor creates a predicate instance (i.e., a *fact*) or complex
    term. If the ``raw`` parameter is used then it tries to unify the supplied
    Clingo.Symbol with the class definition, and will raise a ValueError if it
    fails to unify.

    Args:
      **kwargs:

         - if a single named parameter ``raw`` is specified then it will try to
           unify the parameter with the specification, or
         - named parameters corresponding to the field names.

    """

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def __init__(self):
        raise NotImplementedError(("Class {} can only be instantiated through a "
                                   "sub-class").format(self.__name__))


    #--------------------------------------------------------------------------
    # Properties and functions for Predicate
    #--------------------------------------------------------------------------

    # Get the underlying clingo.Symbol object
    @property
    def raw(self):
        """Returns the underlying clingo.Symbol object"""
        return self._raw

#    # Get the sign of the literal
#    @property
#    def sign(self):
#        """Returns the sign of the predicate instance"""
#        return self._raw.positive

    @_classproperty
    def Field(cls):
        """A RawField sub-class corresponding to a Field for this class."""
        return cls._field

    # Clone the object with some differences
    def clone(self, **kwargs):
        """Clone the object with some differences.

        For any field name that is not one of the parameter keywords the clone
        keeps the same value. But for any field listed in the parameter keywords
        replace with specified new value.
        """

        # Sanity check
        clonekeys = set(kwargs.keys())
        objkeys = set(self.meta.keys())
        diffkeys = clonekeys - objkeys
        diffkeys.discard("sign")

        if diffkeys:
            raise ValueError("Unknown field names: {}".format(diffkeys))

        # Get the arguments for the new object
        cloneargs = {}
        if "sign" in clonekeys: cloneargs["sign"] = kwargs["sign"]
        for field in self.meta:
            if field.name in kwargs:
                cloneargs[field.name] = kwargs[field.name]
            else:
                cloneargs[field.name] = self._field_values[field.index]
                kwargs[field.name] = self._field_values[field.index]

        # Create the new object
        return type(self)(**cloneargs)

    #--------------------------------------------------------------------------
    # Class methods and properties
    #--------------------------------------------------------------------------

    # Get the metadata for the Predicate definition
    @_classproperty
    def meta(cls):
        """The meta data (definitional information) for the Predicate/Complex-term"""
        return cls._meta

    # Returns whether or not a clingo.Symbol object can unify with this
    # Predicate
    @classmethod
    def _unifies(cls, raw):
        if raw.type != clingo.SymbolType.Function: return False

        if raw.name != cls.meta.name: return False
        if len(raw.arguments) != len(cls.meta): return False

        if cls.meta.sign is not None:
            if cls.meta.sign != raw.positive: return False

        for idx, field in enumerate(cls.meta):
            if not field.defn.unifies(raw.arguments[idx]): return False
        return True

    # Factory that returns a unified Predicate object
    @classmethod
    def _unify(cls, raw):
        return cls(raw=raw)

    #--------------------------------------------------------------------------
    # Overloaded index operator to access the values and len operator
    #--------------------------------------------------------------------------

    def __iter__(self):
        # The number of parameters in a predicate are always small so convenient
        # to generate a list of values rather than have a specialised iterator.
        return iter([self[idx] for idx in range(0,len(self))])

    def __getitem__(self, idx):
        """Allows for index based access to field elements."""
        return self.meta[idx].__get__(self)

    def __bool__(self):
        '''Behaves like a tuple: returns False if the predicate/complex-term has no elements'''
        return len(self.meta) > 0

    def __len__(self):
        '''Returns the number of fields in the object'''
        return len(self.meta)

    #--------------------------------------------------------------------------
    # Overload the unary minus operator to return the complement of this literal
    # (if its positive return a negative equivaent and vice-versa)
    # --------------------------------------------------------------------------
    def __neg__(self):
        return self.clone(sign=not self.sign)

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

        # Negative literals are less than positive literals
        if self.raw.positive != other.raw.positive:
            return self.raw.positive < other.raw.positive

        # compare each field in order
        for idx in range(0,len(self._meta)):
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

        # Positive literals are greater than negative literals
        if self.raw.positive != other.raw.positive:
            return self.raw.positive > other.raw.positive

        # compare each field in order
        for idx in range(0,len(self._meta)):
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
        """Returns the Predicate as the string representation of the raw
        clingo.Symbol.
        """
        return str(self.raw)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# Predicate and ComplexTerm are simply aliases for Predicate.
#------------------------------------------------------------------------------

ComplexTerm=Predicate

#------------------------------------------------------------------------------
# A function for defining Predicate sub-classes containing only RawField
# parameters. Useful when debugging ASP code and you just want to use the class
# for easy display/printing.
# ------------------------------------------------------------------------------

def simple_predicate(*args):
    """Factory function to define a predicate with only RawField arguments.

    A helper factory function that takes a name and an arity and returns a
    predicate class that is suitable for unifying with predicate instances of
    that name and arity. It's parameters are all specified as RawFields.

    This function is useful for debugging ASP programs. There may be some
    auxillary predicates that you aren't interested in extracting their values
    but instead you simply want to print them to the screen in some order.

    The function must be called using positional arguments with either 2 or 3
    arguments. For the 3 argument case a class name is specified for the name of
    the new predicate. For the 2 argument case an anonymous predicate class name
    is automatically generated.

    Args:
       optional subclass_name: new sub-class name (anonymous if none specified).
       name: the name of the predicate to match against
       arity: the arity for the predicate

    """
    largs = len(args)
    if largs == 2:
        subclass_name = "ClormAnonPredicate"
        name = args[0]
        arity = args[1]
    elif largs == 3:
        subclass_name = args[0]
        name = args[1]
        arity = args[2]
    else:
        raise TypeError("simple_predicate() missing required positional arguments")

    # Use an OrderedDict to ensure the correct order of the field arguments
    proto = collections.OrderedDict([("arg{}".format(i+1), RawField())
                                     for i in range(0,arity)])
    proto['Meta'] = type("Meta", (object,),
                         {"name" : name, "is_tuple" : False, "_anon" : True})
    return type("ClormAnonPredicate", (Predicate,), proto)

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Fact comparator: is a function that determines if a fact (i.e., predicate
# instance) satisfies some property or condition. Any function that takes a
# single fact as an argument and returns a bool is a fact comparator. However,
# we define a few special types by inheriting from Comparator:
# PredicatePathComparator, BoolComparator, StaticComparator.
# ------------------------------------------------------------------------------

# A helper function to return a simplified version of a fact comparator
def _simplify_fact_comparator(comparator):
    try:
        return comparator.simplified()
    except:
        if isinstance(comparator, bool):
            return StaticComparator(comparator)
        return comparator

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
    # None could be a legitimate value so cannot use it to test for default
    def __init__(self, name, *args, **kwargs):
        self._name = name
        # Check for unexpected arguments
        badkeys = _check_keys(set(["default"]), set(kwargs.keys()))
        if badkeys:
            mstr = "Named placeholder unexpected keyword arguments: "
            raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

        # Check the match between positional and keyword arguments
        if "default" in kwargs and len(args) > 0:
            raise TypeError(("Named placeholder got multiple values for "
                             "argument 'default'"))
        if len(args) > 1:
            raise TypeError(("Named placeholder takes from 0 to 2 positional"
                             "arguments but {} given").format(len(args)+1))

        # Set the keyword argument
        if "default" in kwargs: self._default = (True, kwargs["default"])
        else: self._default = (False,None)

    @property
    def name(self):
        return self._name
    @property
    def has_default(self):
        return self._default[0]
    @property
    def default(self):
        return self._default[1]
    def __str__(self):
        tmpstr = "" if not self._default[0] else ",{}".format(self._default[1])
        return "ph_(\"{}\"{})".format(self._name, tmpstr)
    def __repr__(self):
        return self.__str__()

class _PositionalPlaceholder(Placeholder):
    def __init__(self, posn):
        self._posn = posn
    @property
    def posn(self):
        return self._posn
    def __str__(self):
        return "ph{}_".format(self._posn+1)
    def __repr__(self):
        return self.__str__()

#def ph_(value,default=None):

def ph_(value, *args, **kwargs):
    ''' A function for building new placeholders, either named or positional.'''

    badkeys = _check_keys(set(["default"]), set(kwargs.keys()))
    if badkeys:
        mstr = "ph_() unexpected keyword arguments: "
        raise TypeError("{}{}".format(mstr,",".join(sorted(badkeys))))

    # Check the match between positional and keyword arguments
    if "default" in kwargs and len(args) > 0:
        raise TypeError("ph_() got multiple values for argument 'default'")
    if len(args) > 1:
        raise TypeError(("ph_() takes from 0 to 2 positional"
                         "arguments but {} given").format(len(args)+1))

    # Set the default argument
    if "default" in kwargs: default = default = (True, kwargs["default"])
    elif len(args) > 0: default = (True, args[0])
    else: default = (False,None)

    try:
        idx = int(value)
    except ValueError:
        # It's a named placeholder
        nkargs = { "name" : value }
        if default[0]: nkargs["default"] = default[1]
        return _NamedPlaceholder(**nkargs)

    # Its a positional placeholder
    if default[0]:
        raise TypeError("Positional placeholders don't support default values")
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
# whether it satisfies some condition (with possible substitutions specified as
# arguments).
# ------------------------------------------------------------------------------

class Comparator(abc.ABC):

    @abc.abstractmethod
    def __call__(self,fact, *args, **kwargs):
        pass

    @abc.abstractmethod
    def placeholders(self):
        pass

    @abc.abstractmethod
    def hashable_paths(self):
        pass

    def __and__(self,other):
        return BoolComparator(operator.and_,self,other)
    def __or__(self,other):
        return BoolComparator(operator.or_,self,other)
    def __rand__(self,other):
        return BoolComparator(operator.and_,self,other)
    def __ror__(self,other):
        return BoolComparator(operator.or_,self,other)
    def __invert__(self):
        return BoolComparator(operator.not_,self)

#------------------------------------------------------------------------------
# A Fact comparator functor that returns a static value
#------------------------------------------------------------------------------

class StaticComparator(Comparator):
    def __init__(self, value):
        self._value=bool(value)
    def __call__(self,fact, *args, **kwargs):
        return self._value
    def simpified(self):
        return self
    def placeholders(self): return set([])
    def hashable_paths(self): return set([])
    @property
    def value(self):
        return self._value
    def __str__(self):
        if self._value: return "True"
        return "False"
    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# A fact comparator functor that tests whether a fact satisfies a comparision
# with the value of some predicate's fields.
#
# Note: instances of PredicatePathComparator are constructed by calling the comparison
# operator for Field objects.
# ------------------------------------------------------------------------------
class PredicatePathComparator(Comparator):
    def __init__(self, compop, arg1, arg2):
        self._compop = compop
        self._arg1 = arg1
        self._arg2 = arg2
        self._static = False

        if not isinstance(arg1, PredicatePath):
            raise TypeError(("Internal error: argument 1 is not "
                             "a PredicatePath {}").format(arg1))

        # Comparison is trivial if the objects are identical or semantically
        # equivalent. If so return a static identity comparison 1 op 1
        if arg1 is arg2:
            self._static = True
            self._value = compop(1,1)
        elif isinstance(arg2, PredicatePath) and arg1 is arg2:
            self._static = True
            self._value = compop(1,1)

    def __call__(self, fact, *args, **kwargs):
        if self._static: return self._value

        # Get the value of an argument (resolving placeholder)
        def getargval(arg):
            if isinstance(arg, PredicatePath): return arg(fact)
            elif isinstance(arg, _PositionalPlaceholder): return args[arg.posn]
            elif isinstance(arg, _NamedPlaceholder): return kwargs[arg.name]
            else: return arg

        # Get the values of the two arguments and then calculate the operator
        v1 = self._arg1(fact)
        v2 = getargval(self._arg2)

        # As much as possible check that the types should match - ie if the
        # first value is a complex term type then the second value should also
        # be of the same type. However, if the first value is a complex term and
        # the second is a tuple then we can try to convert the tuple into
        # complex term object of the first type.
        tryconv = False
        if type(v1) != type(v2):
            if isinstance(v1, Predicate):
                tryconv = True
                if isinstance(v2, Predicate) and v1.meta.name != v2.meta.name:
                    raise TypeError(("Incompatabile type comparison of "
                                     "{} and {}").format(v1,v2))
        if tryconv:
            try:
                v2 = type(v1)(*v2)
            except:
                raise TypeError(("Incompatabile type comparison of "
                                 "{} and {}").format(v1,v2))
        # Return the result of comparing the two values
        return self._compop(v1,v2)

    def simplified(self):
        if self._static: return StaticComparator(self._value)
        return self

    def placeholders(self):
        if isinstance(self._arg2, Placeholder): return set([self._arg2])
        return set([])

    def hashable_paths(self):
        tmp=set([])
        if isinstance(self._arg1, PredicatePath): tmp.add(self._arg1.meta.hashable)
        if isinstance(self._arg2, PredicatePath): tmp.add(self._arg2.meta.hashable)
        return tmp

    def indexable(self):
        if self._static: return None
        if isinstance(self._arg2, PredicatePath): return None
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

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# A fact comparator that is a boolean operator over other Fact comparators
# ------------------------------------------------------------------------------

class BoolComparator(Comparator):
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
            if isinstance(sarg, StaticComparator):
                if self._boolop == operator.not_: return StaticComparator(not sarg.value)
                if self._boolop == operator.and_ and not sarg.value: return sarg
                if self._boolop == operator.or_ and sarg.value: return sarg
            else:
                newargs.append(sarg)
        # Now see if we can simplify the combination of the arguments
        if not newargs:
            if self._boolop == operator.and_: return StaticComparator(True)
            if self._boolop == operator.or_: return StaticComparator(False)
        if self._boolop != operator.not_ and len(newargs) == 1:
            return newargs[0]
        # If we get here there then there is a real boolean comparison
        return BoolComparator(self._boolop, *newargs)

    def placeholders(self):
        tmp = set([])
        for a in self._args:
            if isinstance(a, Comparator): tmp.update(a.placeholders())
        return tmp

    def hashable_paths(self):
        tmp = set([])
        for a in self._args:
            if isinstance(a, Comparator): tmp.update(a.hashable_paths())
        return tmp

    @property
    def boolop(self): return self._boolop

    @property
    def args(self): return self._args

    def __str__(self):
        if self._boolop == operator.not_: opstr = "not_"
        elif self._boolop == operator.and_: opstr = "and_"
        elif self._boolop == operator.or_: opstr = "or_"
        else: opstr = "<unknown>"
        argsstr=", ".join([str(a) for a in self._args])
        return "{}({})".format(opstr,argsstr)

    def __repr__(self):
        return self.__str__()

# ------------------------------------------------------------------------------
# Functions to build BoolComparator instances
# ------------------------------------------------------------------------------

def not_(*conditions):
    return BoolComparator(operator.not_,*conditions)
def and_(*conditions):
    return BoolComparator(operator.and_,*conditions)
def or_(*conditions):
    return BoolComparator(operator.or_,*conditions)

#------------------------------------------------------------------------------
# _FactIndex indexes facts by a given field
#------------------------------------------------------------------------------

class _FactIndex(object):
    def __init__(self, path):
        try:
            self._path = path
            self._predicate = self._path.meta.predicate
            self._keylist = []
            self._key2values = {}
        except:
            raise TypeError("{} is not a valid PredicatePath object".format(path))

    @property
    def path(self):
        return self._path

    def add(self, fact):
        if not isinstance(fact, self._predicate):
            raise TypeError("{} is not a {}".format(fact, self._predicate))
        key = self._path(fact)

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
        if not isinstance(fact, self._predicate):
            raise TypeError("{} is not a {}".format(fact, self._predicate))
        key = self._path(fact)

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
        ``ph4_`` and correspond to the 1st to 4th arguments of the ``get``,
        ``get_unique`` or ``count`` function call.

        Args:
          expressions: one or more comparison expressions.

        """
        pass

    @abc.abstractmethod
    def order_by(self, *fieldorder):
        """Provide an ordering over the results."""
        pass

    @abc.abstractmethod
    def get(self, *args, **kwargs):
        """Return all matching entries."""
        pass

    @abc.abstractmethod
    def get_unique(self, *args, **kwargs):
        """Return the single matching entry. Raises ValueError otherwise."""
        pass

    @abc.abstractmethod
    def count(self, *args, **kwargs):
        """Return the number of matching entries."""
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
# Helper function to check a where clause for errors
#------------------------------------------------------------------------------
def _check_where_clause(where, ptype):
    # Note: the expression may not be a Comparator, in which case at least check
    # that it is a function/functor
    try:
        hashable_paths = where.hashable_paths()

        for p in hashable_paths:
            if p.path.meta.predicate != ptype:
                msg = ("'where' expression contains path '{}' that doesn't match "
                       "predicate type '{}'").format(p.path, ptype.__name__)
                raise TypeError(msg)

    except AttributeError:
        if not callable(where):
            raise TypeError("'{}' object is not callable".format(type(where).__name__))


#------------------------------------------------------------------------------
# A selection over a _FactMap
#------------------------------------------------------------------------------

class _Select(Select):

    def __init__(self, factmap):
        self._factmap = factmap
        self._index_priority = { path.meta.hashable: idx \
                                 for (idx,path) in enumerate(factmap.indexes) }
        self._where = None
        self._indexable = None
        self._key = None

    def where(self, *expressions):
        if self._where:
            raise TypeError("cannot specify 'where' multiple times")
        if not expressions:
            raise TypeError("empty 'where' expression")
        elif len(expressions) == 1:
            self._where = _simplify_fact_comparator(expressions[0])
        else:
            self._where = _simplify_fact_comparator(and_(*expressions))

        self._indexable = self._primary_search(self._where)

        # Check that the where clause only refers to the correct predicate
        _check_where_clause(self._where, self._factmap.predicate)
        return self

    @property
    def has_where(self):
        return bool(self._where)

    def order_by(self, *expressions):
        if self._key:
            raise TypeError("cannot specify 'order_by' multiple times")
        if not expressions:
            raise TypeError("empty 'order_by' expression")
        field_orders = []
        for exp in expressions:
            if isinstance(exp, OrderBy): field_orders.append(exp)
            elif isinstance(exp, PredicatePath):
                field_orders.append(exp.meta.asc())
            else: raise TypeError("Invalid 'order_by' expression: {}".format(exp))

        # Check that all the paths refer to the correct predicate type
        ptype = self._factmap.predicate
        for f in field_orders:
            if f.path.meta.predicate != ptype:
                msg = ("'order_by' expression contains path '{}' that doesn't match "
                       "predicate type '{}'").format(f.path, ptype.__name__)
                raise TypeError(msg)


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
            if indexable[0].meta.hashable not in self._index_priority: return None
            return indexable

        if isinstance(where, PredicatePathComparator):
            return validate_indexable(where.indexable())
        indexable = None
        if isinstance(where, BoolComparator) and where.boolop == operator.and_:
            for arg in where.args:
                tmp = self._primary_search(arg)
                if tmp:
                    if not indexable: indexable = tmp
                    elif self._index_priority[tmp[0].meta.hashable] < \
                         self._index_priority[indexable[0].meta.hashable]:
                        indexable = tmp
        return indexable

#    @property
    def _debug(self):
        return self._indexable

    # Support function to check that arguments match placeholders and assign any
    # default values for named placeholders.
    def _resolve_arguments(self, *args, **kwargs):
        if not self._where: return kwargs
        if not isinstance(self._where, Comparator): return kwargs
        new_kwargs = {}
        placeholders = self._where.placeholders()
        for ph in placeholders:
            if isinstance(ph, _PositionalPlaceholder):
                if ph.posn < len(args): continue
                raise TypeError(("missing argument in {} for placeholder "
                                 "{}").format(args, ph))
            elif isinstance(ph, _NamedPlaceholder):
                if ph.name in kwargs: continue
                elif ph.has_default:
                    new_kwargs[ph.name] = ph.default
                    continue
                raise TypeError(("missing argument in {} for named "
                                 "placeholder with no default "
                                 "{}").format(kwargs, args))
            raise TypeError("unknown placeholder {} ({})".format(ph, type(ph)))

        # Add any new values
        if not new_kwargs: return kwargs
        new_kwargs.update(kwargs)
        return new_kwargs

    # Function to execute the select statement
    def get(self, *args, **kwargs):

        nkwargs = self._resolve_arguments(*args, **kwargs)

        # Function to get a value - resolving placeholder if necessary
        def get_value(arg):
            if isinstance(arg, _PositionalPlaceholder): return args[arg.posn]
            elif isinstance(arg, _NamedPlaceholder): return nkwargs[arg.name]
            else: return arg

        # If there is no index test all instances else use the index
        result = []
        if not self._indexable:
            for f in self._factmap.facts():
                if not self._where: result.append(f)
                elif self._where and self._where(f,*args,**nkwargs): result.append(f)
        else:
            findex = self._factmap.get_factindex(self._indexable[0])
            value = get_value(self._indexable[2])
            field = findex.path.meta.field
            if field:
                cmplx = field.complex
                if cmplx and isinstance(value, tuple): value = cmplx(*value)
            for f in findex.find(self._indexable[1], value):
                if self._where(f,*args,**nkwargs): result.append(f)

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

    def count(self, *args, **kwargs):
        return len(self.get(*args, **kwargs))

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
# A helper function to determine if two collections have the same elements
# (irrespective of ordering). This is useful if the underlying objects are two
# OrderedSet objects since the equality operator will also test for the same
# ordering which is something we don't want.
# ------------------------------------------------------------------------------

def _is_set_equal(s1,s2):
    if len(s1) != len(s2): return False
    for elem in s1:
        if elem not in s2: return False
    return True

#------------------------------------------------------------------------------
# A map for facts of the same type - Indexes can be built to allow for fast
# lookups based on a field value. The order that the fields are specified in the
# index matters as it determines the priority of the index.
# ------------------------------------------------------------------------------

class _FactMap(object):
    def __init__(self, ptype, indexes=[]):
        self._ptype = ptype
        self._allfacts = _FactSet()

        self._findexes = None
        self._indexes = ()
        if not issubclass(ptype, Predicate):
            raise TypeError("{} is not a subclass of Predicate".format(ptype))
        if indexes:
            self._indexes = tuple(indexes)
            self._findexes = collections.OrderedDict(
                (p.meta.hashable, _FactIndex(p)) for p in self._indexes )
            preds = set([p.meta.predicate for p in self._indexes])
            if len(preds) != 1 or preds != set([ptype]):
                raise TypeError("Fields in {} do not belong to {}".format(indexes,preds))

    def _add_fact(self,fact):
        self._allfacts.add(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.add(fact)

    def add(self, arg):
        if isinstance(arg, Predicate): return self._add_fact(arg)
        for f in arg: self._add_fact(f)

    def discard(self, fact):
        self.remove(fact, False)

    def remove(self, fact, raise_on_missing=True):
        if raise_on_missing: self._allfacts.remove(fact)
        else: self._allfacts.discard(fact)
        if self._findexes:
            for findex in self._findexes.values(): findex.remove(fact,raise_on_missing)

    @property
    def predicate(self):
        return self._ptype

    @property
    def indexes(self):
        return self._indexes

    def get_factindex(self, path):
        return self._findexes[path.meta.hashable]

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

    def pop(self):
        if not self._allfacts: raise KeyError("Cannot pop() an empty _FactMap")
        fact = next(iter(self._allfacts))
        self.remove(fact)
        return fact

    def __str__(self):
        return self.asp_str()

    def __repr__(self):
        return self.__str__()

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

    def __eq__(self,other):
        return _is_set_equal(self._allfacts,other._allfacts)

    def __ne__(self,other):
        return not _is_set_equal(self._allfacts,other._allfacts)

    def __lt__(self,other):
        return self._allfacts < other._allfacts

    def __le__(self,other):
        return self._allfacts <= other._allfacts

    def __gt__(self,other):
        return self._allfacts > other._allfacts

    def __ge__(self,other):
        return self._allfacts >= other._allfacts


    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().union(*tmpothers)
        nfm.add(tmp)
        return nfm

    def intersection(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().intersection(*tmpothers)
        nfm.add(tmp)
        return nfm

    def difference(self,*others):
        nfm = _FactMap(self.predicate, self.indexes)
        tmpothers = [o.facts() for o in others]
        tmp = self.facts().difference(*tmpothers)
        nfm.add(tmp)
        return nfm

    def symmetric_difference(self,other):
        nfm = _FactMap(self.predicate, self.indexes)
        tmp = self.facts().symmetric_difference(other)
        nfm.add(tmp)
        return nfm

    def update(self,*others):
        for f in itertools.chain(*[o.facts() for o in others]):
            self._add_fact(f)

    def intersection_update(self,*others):
        for f in set(self.facts()):
            for o in others:
                if f not in o: self.discard(f)

    def difference_update(self,*others):
        for f in itertools.chain(*[o.facts() for o in others]):
            self.discard(f)

    def symmetric_difference_update(self, other):
        to_remove=set()
        to_add=set()
        for f in self._allfacts:
            if f in other._allfacts: to_remove.add(f)
        for f in other._allfacts:
            if f not in self._allfacts: to_add.add(f)
        for f in to_remove: self.discard(f)
        for f in to_add: self._add_fact(f)

    def copy(self):
        nfm = _FactMap(self.predicate, self.indexes)
        nfm.add(self.facts())
        return nfm


#------------------------------------------------------------------------------
# Support function for printing ASP facts
#------------------------------------------------------------------------------

def _format_asp_facts(iterator,output,width):
    tmp1=""
    for f in iterator:
        fstr="{}.".format(f)
        if tmp1 and len(tmp1) + len(fstr) > width:
            print(tmp1,file=output)
            tmp1 = fstr
        else:
            tmp1 = tmp1 + " " + fstr if tmp1 else fstr
    if tmp1: print(tmp1,file=output)

#------------------------------------------------------------------------------
# A FactBase consisting of facts of different types
#------------------------------------------------------------------------------

class FactBase(object):
    """A fact base is a container for facts (i.e., Predicate sub-class instances)

    ``FactBase`` can be behave like a specialised ``set`` object, but can also
    behave like a minimalist database. It stores facts for ``Predicate`` types
    (where a predicate type loosely corresponds to a *table* in a database)
    and allows for certain fields to be indexed in order to perform more
    efficient queries.

    The initaliser can be given a collection of predicates. If it is passed
    another FactBase then it simply makes a copy (including the indexed fields).

    FactBase also has a special mode when it is passed a functor instead of a
    collection. In this case it performs a delayed initialisation. This means
    that the internal data structures are only populated when the FactBase is
    actually used. This mode is particularly useful when extracting facts from
    models. Often a program will only want to keep the data from the final model
    (for example, with optimisation we often want the best model before a
    timeout). Delayed initialisation is useful will save computation as only the
    last model will be properly initialised.

    Args:
      facts([Predicate]|FactBase|callable): a list of facts (predicate
         instances), a fact base, or a functor that generates a list of
         facts. If a functor is passed then the fact base performs a delayed
         initialisation. If a fact base is passed and no index is specified then
         an index will be created matching in input fact base.
      indexes(Field): a list of fields that are to be indexed.

    """

    #--------------------------------------------------------------------------
    # Internal member functions
    #--------------------------------------------------------------------------

    # A special purpose initialiser so that we can delayed initialisation
    def _init(self, facts=None, indexes=None):

        # flag that initialisation has taken place
        self._delayed_init = None

        # If it is delayed initialisation then get the facts
        if facts and callable(facts):
            facts = facts()
        elif facts and isinstance(facts, FactBase) and indexes is None:
            indexes = facts.indexes
        if indexes is None: indexes=[]

        # Create _FactMaps for the predicate types with indexed fields
        grouped = {}

        self._indexes = tuple(indexes)
        for path in self._indexes:
            if path.meta.predicate not in grouped: grouped[path.meta.predicate] = []
            grouped[path.meta.predicate].append(path)
        self._factmaps = { pt : _FactMap(pt, idxs) for pt, idxs in grouped.items() }

        if facts is None: return
        self._add(facts)

    # Make sure the FactBase has been initialised
    def _check_init(self):
        if self._delayed_init: self._delayed_init()  # Check for delayed init

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
                             "(or sub-class)").format(fact))
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        self._factmaps[ptype].add(fact)

    def _remove(self, fact, raise_on_missing):
        ptype = type(fact)
        if not isinstance(arg, Predicate) or ptype not in self._factmaps:
            raise KeyError("{} not in factbase".format(arg))

        return self._factmaps[ptype].delete()

    #--------------------------------------------------------------------------
    # Initiliser
    #--------------------------------------------------------------------------
    def __init__(self, facts=None, indexes=None):
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
        self._check_init()  # Check for delayed init
        return self._add(arg)

    def remove(self, arg):
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=True)

    def discard(self, arg):
        self._check_init()  # Check for delayed init
        return self._remove(arg, raise_on_missing=False)

    def pop(self):
        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items():
            if fm: return fm.pop()
        raise KeyError("Cannot pop() from an empty FactBase")

    def clear(self):
        """Clear the fact base of all facts."""

        self._check_init()  # Check for delayed init
        for pt, fm in self._factmaps.items(): fm.clear()

    #--------------------------------------------------------------------------
    # Special FactBase member functions
    #--------------------------------------------------------------------------
    def select(self, ptype):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].select()

    def delete(self, ptype):
        """Create a Select query for a predicate type."""

        self._check_init()  # Check for delayed init
        if ptype not in self._factmaps:
            self._factmaps[ptype] = _FactMap(ptype)
        return self._factmaps[ptype].delete()

    @property
    def predicates(self):
        """Return the list of predicate types that this fact base contains."""

        self._check_init()  # Check for delayed init
        return tuple([pt for pt, fm in self._factmaps.items() if fm])

    @property
    def indexes(self):
        self._check_init()  # Check for delayed init
        return self._indexes

    def facts(self):
        """Return all facts."""

        self._check_init()  # Check for delayed init
        tmp = [ fm.facts() for fm in self._factmaps.values() if fm]
        return list(itertools.chain(*tmp))

    def asp_str(self,width=0,commented=False):
        """Return a string representation of the fact base that is suitable for adding
        to an ASP program

        """
        self._check_init()  # Check for delayed init
        out = io.StringIO()

        if not commented:
            _format_asp_facts(self,out,width)
        else:
            first=True
            for fm in self._factmaps.values():
                if first: first=False
                else: print("",file=out)
                pm=fm.predicate.meta
                print("% FactBase predicate: {}/{}".format(pm.name,pm.arity),file=out)
                _format_asp_facts(fm,out,width)

        data = out.getvalue()
        out.close()
        return data



    def __str__(self):
        self._check_init()  # Check for delayed init
        tmp = ", ".join([str(f) for f in self])
        return '{' + tmp + '}'

    def __repr__(self):
        return self.__str__()

    #--------------------------------------------------------------------------
    # Special functions to support set and container operations
    #--------------------------------------------------------------------------

    def __contains__(self, fact):
        """Implemement set 'in' operator."""

        self._check_init() # Check for delayed init

        if not isinstance(fact,Predicate): return False
        ptype = type(fact)
        if ptype not in self._factmaps: return False
        return fact in self._factmaps[ptype].facts()

    def __bool__(self):
        """Implemement set bool operator."""

        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            if fm: return True
        return False

    def __len__(self):
        self._check_init() # Check for delayed init
        return sum([len(fm) for fm in self._factmaps.values()])

    def __iter__(self):
        self._check_init() # Check for delayed init

        for fm in self._factmaps.values():
            for f in fm: yield f

    def __eq__(self, other):
        """Overloaded boolean operator."""

        # If other is not a FactBase then create one
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init(); other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if self_fms.keys() != other_fms.keys(): return False

        for p, fm1 in self_fms.items():
            fm2 = other_fms[p]
            if not _is_set_equal(fm1.facts(),fm2.facts()): return False

        return True

    def __ne__(self, other):
        """Overloaded boolean operator."""
        result = self.__eq__(other)
        if result is NotImplemented: return NotImplemented
        return not result

    def __lt__(self,other):
        """Implemement set < operator."""

        # If other is not a FactBase then create one
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() ; other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if len(self_fms) > len(other_fms): return False

        known_ne=False
        for p, spfm in self_fms.items():
            if p not in other_fms: return False
            opfm = other_fms[p]
            if spfm < opfm: known_ne=True
            elif spfm > opfm: return False

        if known_ne: return True
        return False

    def __le__(self,other):
        """Implemement set <= operator."""

        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() ; other._check_init() # Check for delayed init

        self_fms = { p: fm for p,fm in self._factmaps.items() if fm }
        other_fms = { p: fm for p,fm in other._factmaps.items() if fm }
        if len(self_fms) > len(other_fms): return False

        for p, spfm in self_fms.items():
            if p not in other_fms: return False
            opfm = other_fms[p]
            if spfm > opfm: return False
        return True

    def __gt__(self,other):
        """Implemement set > operator."""
        if not isinstance(other, self.__class__): other=FactBase(other)
        return other.__lt__(self)

    def __ge__(self,other):
        """Implemement set >= operator."""
        if not isinstance(other, self.__class__): other=FactBase(other)
        return other.__le__(self)

    def __or__(self,other):
        """Implemement set | operator."""
        return self.union(other)

    def __and__(self,other):
        """Implemement set & operator."""
        return self.intersection(other)

    def __sub__(self,other):
        """Implemement set - operator."""
        return self.difference(other)

    def __xor__(self,other):
        """Implemement set ^ operator."""
        return self.symmetric_difference(other)

    def __ior__(self,other):
        """Implemement set |= operator."""
        self.update(other)
        return self

    def __iand__(self,other):
        """Implemement set &= operator."""
        self.intersection_update(other)
        return self

    def __isub__(self,other):
        """Implemement set -= operator."""
        self.difference_update(other)
        return self

    def __ixor__(self,other):
        """Implemement set ^= operator."""
        self.symmetric_difference_update(other)
        return self


    #--------------------------------------------------------------------------
    # Set functions
    #--------------------------------------------------------------------------
    def union(self,*others):
        """Implements the set union() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        for o in others: predicates.update(o._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            if p in self._factmaps:
                fb._factmaps[p] = self._factmaps[p].union(*pothers)
            else:
                fb._factmaps[p] = _FactMap(p).union(*pothers)
        return fb

    def intersection(self,*others):
        """Implements the set intersection() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        for o in others: predicates.intersection_update(o._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].intersection(*pothers)
        return fb

    def difference(self,*others):
        """Implements the set difference() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())

        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            fb._factmaps[p] = self._factmaps[p].difference(*pothers)
        return fb

    def symmetric_difference(self,other):
        """Implements the set symmetric_difference() function"""
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() # Check for delayed init
        other._check_init()

        fb=FactBase()
        predicates = set(self._factmaps.keys())
        predicates.update(other._factmaps.keys())

        for p in predicates:
            if p in self._factmaps and p in other._factmaps:
                fb._factmaps[p] = self._factmaps[p].symmetric_difference(other._factmaps[p])
            else:
                if p in self._factmaps: fb._factmaps[p] = self._factmaps[p].copy()
                fb._factmaps[p] = other._factmaps[p].copy()

        return fb

    def update(self,*others):
        """Implements the set update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        for o in others:
            for p,fm in o._factmaps.items():
                if p in self._factmaps: self._factmaps[p].update(fm)
                else: self._factmaps[p] = fm.copy()

    def intersection_update(self,*others):
        """Implements the set intersection_update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()
        num = len(others)

        predicates = set(self._factmaps.keys())
        for o in others: predicates.intersection_update(o._factmaps.keys())
        pred_to_delete = set(self._factmaps.keys()) - predicates

        for p in pred_to_delete: self._factmaps[p].clear()
        for p in predicates:
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps]
            self._factmaps[p].intersection_update(*pothers)

    def difference_update(self,*others):
        """Implements the set difference_update() function"""
        others=[o if isinstance(o, self.__class__) else FactBase(o) for o in others]
        self._check_init() # Check for delayed init
        for o in others: o._check_init()

        for p in self._factmaps.keys():
            pothers=[ o._factmaps[p] for o in others if p in o._factmaps ]
            self._factmaps[p].difference_update(*pothers)

    def symmetric_difference_update(self,other):
        """Implements the set symmetric_difference_update() function"""
        if not isinstance(other, self.__class__): other=FactBase(other)
        self._check_init() # Check for delayed init
        other._check_init()

        predicates = set(self._factmaps.keys())
        predicates.update(other._factmaps.keys())

        for p in predicates:
            if p in self._factmaps and p in other._factmaps:
                self._factmaps[p].symmetric_difference_update(other._factmaps[p])
            else:
                if p in other._factmaps: self._factmaps[p] = other._factmaps[p].copy()


    def copy(self):
        """Implements the set copy() function"""
        self._check_init() # Check for delayed init
        fb=FactBase()
        for p,fm in self._factmaps.items():
            fb._factmaps[p] = self._factmaps[p].copy()
        return fb

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# A fact generator that takes a list of predicates to unify against (order
# matters) and a set of raw clingo symbols against this list.
# ------------------------------------------------------------------------------

def _unify(predicates, symbols):
    def unify_single(cls, r):
        try:
            return cls._unify(r)
        except ValueError:
            return None

    # To make things a little more efficient use the name/arity signature as a
    # filter. However, Python doesn't have a built in multidict class, and I
    # don't want to add a dependency to an external library just for one small
    # feature, so implement a simple structure here.
    sigs = [((cls.meta.name, len(cls.meta)),cls) for cls in predicates]
    types = {}
    for sig,cls in sigs:
        if sig not in types: types[sig] = [cls]
        else: types[sig].append(cls)

    # Loop through symbols and yield when we have a match
    for raw in symbols:
        classes = types.get((raw.name, len(raw.arguments)))
        if not classes: continue
        for cls in classes:
            f = unify_single(cls,raw)
            if f:
                yield f
                break


#------------------------------------------------------------------------------
# SymbolPredicateUnifier offers a decorator interface for gathering predicate and index
# definitions to be used in defining a FactBase subclass.
# ------------------------------------------------------------------------------
class SymbolPredicateUnifier(object):
    """A fact base builder simplifies the task of unifying raw clingo.Symbol objects
    with Clorm predicates. Predicates classes are registered using the
    'register' function (which can be called as a normal function or as a class
    decorator.
    """

    def __init__(self, predicates=[], indexes=[], suppress_auto_index=False):
        self._predicates = ()
        self._indexes = ()
        self._suppress_auto_index = suppress_auto_index
        tmppreds = []
        tmpinds = []
        tmppredset = set()
        tmpindset = set()
        for pred in predicates:
                self._register_predicate(pred,tmppreds,tmpinds,tmppredset,tmpindset)
        for fld in indexes:
                self._register_index(fld,tmppreds,tmpinds,tmppredset,tmpindset)
        self._predicates = tuple(tmppreds)
        self._indexes = tuple(tmpinds)

    def _register_predicate(self, cls, predicates, indexes, predicateset, indexset):
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        if cls in predicateset: return
        predicates.append(cls)
        predicateset.add(cls)
        if self._suppress_auto_index: return

        # Add all fields (and sub-fields) that are specified as indexed
        for fp in cls.meta.indexes:
            self._register_index(fp,predicates,indexes,predicateset,indexset)

    def _register_index(self, path, predicates, indexes, predicateset, indexset):
        if path.meta.hashable in indexset: return
        if isinstance(path, PredicatePath) and path.meta.predicate in predicateset:
            indexset.add(path.meta.hashable)
            indexes.append(path)
        else:
            raise TypeError("{} is not a predicate field for one of {}".format(
                path, [ p.__name__ for p in predicates ]))

    def register(self, cls):
        if cls in self._predicates: return cls
        predicates = list(self._predicates)
        indexes = list(self._indexes)
        tmppredset = set(self._predicates)
        tmpindset = set([p.meta.hashable for p in self._indexes])
        self._register_predicate(cls,predicates,indexes,tmppredset,tmpindset)
        self._predicates = tuple(predicates)
        self._indexes = tuple(indexes)
        return cls

    def unify(self, symbols, delayed_init=False, raise_on_empty=False):
        def _populate():
            facts=list(_unify(self.predicates, symbols))
            if not facts and raise_on_empty:
                raise ValueError("FactBase creation: failed to unify any symbols")
            return facts

        if delayed_init:
            return FactBase(facts=_populate, indexes=self._indexes)
        else:
            return FactBase(facts=_populate(), indexes=self._indexes)

    @property
    def predicates(self): return self._predicates
    @property
    def indexes(self): return self._indexes

#------------------------------------------------------------------------------
# Generate facts from an input array of Symbols.  The `unifier` argument takes a
# list of predicate classes or a SymbolPredicateUnifer object to unify against
# the symbol object contained in `symbols`.
# ------------------------------------------------------------------------------

def unify(unifier,symbols,ordered=False):
    '''Unify raw symbols against a list of predicates or a SymbolPredicateUnifier.

    Symbols are tested against each predicate unifier until a match is
    found. Since it is possible to define multiple predicate types that can
    unify with the same symbol, the order of the predicates in the unifier
    matters. With the `ordered` option set to `True` a list is returned that
    preserves the order of the input symbols.

    Args:
      unifier: a list of predicate classes or a SymbolPredicateUnifier object.
      symbols: the symbols to unify.
      ordered (default: False): optional to return a list rather than a FactBase.
    Return:
      a FactBase containing the unified facts, indexed by any specified indexes,
         or a list if the ordered option is specified

    '''
    if not unifier:
        raise ValueError(("The unifier must be a list of predicates "
                          "or a SymbolPredicateUnifier"))
    if ordered:
        if isinstance(unifier, SymbolPredicateUnifier):
            unifier=unifier.predicates
        return list(_unify(unifier,symbols))
    else:
        if not isinstance(unifier, SymbolPredicateUnifier):
            unifier=SymbolPredicateUnifier(predicates=unifier)
        return unifier.unify(symbols)

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
    def _is_input_element(se):
        '''An input element must be a subclass of RawField (or an instance of a
           subclass) or a tuple corresponding to a subclass of RawField'''
        return inspect.isclass(se) and issubclass(se, RawField)

    @staticmethod
    def is_return_element(se):
        '''An output element must be a subclass of RawField or a singleton containing'''
        if isinstance(se, collections.Iterable):
            if len(se) != 1: return False
            return TypeCastSignature._is_input_element(se[0])
        return TypeCastSignature._is_input_element(se)

    def __init__(self, *sigs):
        def _validate_basic_sig(sig):
            if TypeCastSignature._is_input_element(sig): return True
            raise TypeError(("TypeCastSignature element {} must be a RawField "
                             "subclass".format(sig)))

        self._insigs = [ type(_get_field_defn(s)) for s in sigs[:-1]]
#        self._insigs = sigs[:-1]
        self._outsig = sigs[-1]

        # A tuple is a special case that we want to convert into a complex field
        if isinstance(self._outsig, tuple):
            self._outsig = type(_get_field_defn(self._outsig))
        elif isinstance(self._outsig, collections.Iterable):
            if len(self._outsig) != 1:
                raise TypeError("Return value list signature not a singleton")
            if isinstance(self._outsig[0], tuple):
                self._outsig[0] = type(_get_field_defn(self._outsig[0]))

        # Validate the signature
        for s in self._insigs: _validate_basic_sig(s)
        if isinstance(self._outsig, collections.Iterable):
            _validate_basic_sig(self._outsig[0])
        else:
            _validate_basic_sig(self._outsig)

        # Turn the signature into a tuple
        self._insigs = tuple(self._insigs)

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

    @property
    def input_signature(self): return self._insigs

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

    def __str__(self):
        insigstr=", ".join([str(s) for s in self._insigs])
        return "{} -> {}".format(insigstr, self._outsig)

    def __repr__(self):
        return self.__str__()

#------------------------------------------------------------------------------
# return and check that function has complete signature
# annotations. ignore_first is useful when dealing with member functions.
#------------------------------------------------------------------------------

def _get_annotations(fn, ignore_first=False):
    fsig = inspect.signature(fn)
    qname = fn.__qualname__
    fsigparam = fsig.parameters
    annotations = [fsigparam[s].annotation for s in fsigparam]
    if not annotations and ignore_first:
        raise TypeError(("Cannot ignore the first parameter for a function "
                         "with no arguments: {}").format(qname))

    # Make sure the return value is annotated
    if inspect.Signature.empty == fsig.return_annotation:
        raise TypeError(("Missing function return annotation: "
                         "{}").format(qname))

    # Remove any ignore first and add the return value annotation
    if ignore_first: annotations.pop(0)
    annotations.append(fsig.return_annotation)

    if inspect.Signature.empty in annotations:
        raise TypeError(("Missing type cast annotations in function "
                         "arguments: {} ").format(qname))
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
# Clingo 5.4 introduces the idea of a context to the grounding process. We want
# to make it easier to use this idea. In particular providing a builder with a
# decorator for capturing functions within a context.
# ------------------------------------------------------------------------------
def _context_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

class ContextBuilder(object):
    """Context builder simplifies the task of building grounding context for
    clingo. This is a new clingo feature for Clingo 5.4 where a context can be
    provided to the grounding function. The context encapsulates the external
    Python functions that can be called from within an ASP program.

    ``ContextBuilder`` allows arbitrary functions to be captured within a context
    and assigned a conversion signature. It also allows the function to be given
    a different name when called from within the context.

    The context builder's ``register`` and ``register_name`` member functions
    can be called as decorators or as normal functions. A useful feature of
    these functions is that when called as decorators they do not wrap the
    original function but instead return the original function and only wrap the
    function when called from within the context. This is unlike the
    ``make_function_asp_callable`` and ``make_method_asp_callable`` functions
    which when called as decorators will replace the original function with the
    wrapped version.

    Example:

    The following nonsense ASP program contains embedded python with functions
    registered with the context builder (highlighting different ways the
    register functions can be called). A context object is then created by the
    context builder and used during grounding. It will produce the answer set:

       .. code-block:: prolog

          f(5), g(6), h("abcd").

       .. code-block:: python

           f(@addi(1,4)).
           g(@addi_alt(2,4)).
           h(@adds("ab","cd")).

           #script(python).

           from clorm import IntegerField,StringField,ContextBuilder

           IF=IntegerField
           SF=StringField
           cb=ContextBuilder()

           # Uses the function annotation to define the conversion signature
           @cb.register
           def addi(a : IF, b : IF) -> IF : return a+b

           # Register with a different name
           @cb.register_name("addi_alt")
           def add2(a : IF, b : IF) -> IF : return a+b

           # Register with a different name and override the signature in the
           # function annotation
           cb._register_name("adds", SF, SF, SF, addi)

           ctx=cb.make_context()

           def main(prg):
               prg.ground([("base",[])],context=ctx)
               prg.solve()

           #end.

    """

    def __init__(self):
        self._funcs = {}

    def _add_function(self, name, sig, fn):
        if name in self._funcs:
            raise ValueError(("Function name '{}' has already been "
                              "used").format(name))
        self._funcs[name]=_context_wrapper(sig.wrap_function(fn))

    def _make_decorator(self, func_name=None, *sigargs):
        def _decorator(fn):
            if func_name: fname = func_name
            else: fname = fn.__name__
            if sigargs: args=sigargs
            else: args= _get_annotations(fn)
            s = TypeCastSignature(*args)
            self._add_function(fname, s, fn)
            return fn
        return _decorator

    def register(self, *args):
        '''Register a function with the context builder.

    Args:

      *args: the last argument must be the function to be registered. If there
        is more than one argument then the earlier arguments define the data
        conversion signature. If there are no earlier arguments then the
        signature is extracted from the function annotations.

        '''

        # Called as a decorator with no signature arguments so decorator needs
        # to use function annotations
        if len(args) == 0: return self._make_decorator()

        # Called as a decorator with signature arguments
        if TypeCastSignature.is_return_element(args[-1]):
            return self._make_decorator(None, *args)

        # Called as a decorator or normal function with no signature arguments
        if len(args) == 1:
            return self._make_decorator(None)(args[0])

        # Called as a normal function with signature arguments
        sigargs=args[:-1]
        return self._make_decorator(None,*sigargs)(args[-1])

    def register_name(self, func_name, *args):
        '''Register a function with assigning it a new name witin the context.

    Args:

      func_name: the new name for the function within the context.

      *args: the last argument must be the function to be registered. If there
        is more than one argument then the earlier arguments define the data
        conversion signature. If there are no earlier arguments then the
        signature is extracted from the function annotations.
        '''

        if not func_name: raise ValueError("Specified an empty function name")

        # Called as a decorator with no signature arguments so decorator needs
        # to use function annotations
        if len(args) == 0: return self._make_decorator(func_name)

        # Called as a decorator with signature arguments
        if TypeCastSignature.is_return_element(args[-1]):
            return self._make_decorator(func_name, *args)

        # Called as a normal function with no signature arguments so need to use
        # function annotations
        if len(args) == 1: return self._make_decorator(func_name)(args[0])

        # Called as a normal function with signature arguments
        sigargs=args[:-1]
        return self._make_decorator(func_name,*sigargs)(args[-1])

    def make_context(self, cls_name="Context"):
        '''Return a context object that encapsulates the registered functions'''

        tmp = { n : fn for n,fn in self._funcs.items() }
        return type(cls_name, (object,), tmp)()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
