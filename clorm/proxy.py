'''A proxy metaclass for building proxy objects. It is instantiated by
specifying a class to be to be proxied as a parent class with ProxyMetaClass as
the metaclass. This creates a proxy base class for that type of object. Note:
this subverts the subclass mechanism as it does not actually create a subclass
of the proxy class. The proxy class is replaced with object as the parent.

This is to be used for proxying clingo.Control, clingo.SolveHandle, and
clingo.Model objects.

Note: some ideas and code have been copied from:
https://code.activestate.com/recipes/496741-object-proxying/

'''

import functools


# ------------------------------------------------------------------------------
# Determine if an attribute name has the pattern of a magic method (ie. is
# callable and has name of the form __XXX__. Ideally, would like to have a
# system function that tells me the list of magic methods. But this should be
# good enough.
# ------------------------------------------------------------------------------

def _poss_magic_method(name,value):
    if not callable(value): return False
    if not name.startswith("__"): return False
    if not name.endswith("__"): return False
    if len(name) <= 4: return False
    if name[2] == '_': return False
    if name[-3] == '_': return False
    return True


# ------------------------------------------------------------------------------
# List of python special methods and some special cases that need to be handled
# ------------------------------------------------------------------------------

_proxy_special_names = [
    '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
    '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
    '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
    '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
    '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
    '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
    '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
    '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
    '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
    '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
    '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
    '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
    '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
    '__truediv__', '__xor__', 'next',
]

def _proxy_getattribute__(self, name):
    return getattr(object.__getattribute__(self, "_obj"), name)
def _proxy__delattr__(self, name):
    delattr(object.__getattribute__(self, "_obj"), name)
def _proxy__setattr__(self, name, value):
    setattr(object.__getattribute__(self, "_obj"), name, value)
def _proxy__nonzero__(self):
    return bool(object.__getattribute__(self, "_obj"))
def _proxy__str__(self):
    return str(object.__getattribute__(self, "_obj"))
def _proxy__repr__(self):
    return repr(object.__getattribute__(self, "_obj"))

# ------------------------------------------------------------------------------
# Make proxy member functions and properties
# ------------------------------------------------------------------------------
def _proxy_function_wrapper(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        return fn(self._proxied, *args, **kwargs)
    return wrapper

def _proxy_property_wrapper(name):
    def wrapper(self):
        return self._proxied.__getattribute__(name)
    return property(wrapper)

# Constructor for every Predicate sub-class
def init_proxy(proxy, *args, **kwargs):
    PrClass = proxy._proxied_cls
    if "proxied_" in kwargs:
        if len(args) != 0 and len(kwargs) != 1:
            raise ValueError(("Invalid initialisation: the 'proxied_' argument "
                              "cannot be combined with other arguments"))
        proxy._proxied = kwargs["proxied_"]
        if not isinstance(proxy._proxied, PrClass):
            raise TypeError(("Invalid proxied object {} not of expected type "
                             "{}").format(proxy._proxied, proxied_class))
    else:
        proxy._proxied = PrClass(*args,**kwargs)

def _proxy_return_proxied(self):
    return self._proxied

# ------------------------------------------------------------------------------
# The proxy metaclass
# ------------------------------------------------------------------------------
class ProxyMetaClass(type):

    def __new__(meta, name, bases, dct):
        if len(bases) != 1:
            raise TypeError("ProxyMetaClass requires exactly one parent class")
        PrClass = bases[0]
        bases = (object,)

        ignore=["_init__", "__new__"]

        # Note: if a constructor is provided then it should call init_proxy
        # manually. Also setup a _proxied_cls attribute.
        if "__init__" not in dct: dct["__init__"] = init_proxy
        if "_proxied_cls" in dct:
            raise TypeError(("ProxyMetaClass cannot proxy a class with a "
                             "\"_proxied_cls\" attribute: {}").format(PrClass))
        dct["_proxied_cls"] = PrClass

        # Mirror the attributes of the class handling the special methods
        for key,value in PrClass.__dict__.items():
            if key in ignore: continue
            if key in dct: continue
            if callable(value):
                dct[key]=_proxy_function_wrapper(value)
            else:
                dct[key]=_proxy_property_wrapper(key)

        return super(ProxyMetaClass, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

