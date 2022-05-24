'''Functions and classes to wrap existing classes. Provides a wrapper metaclass
and also a function that returns a wrapped class. The function is more flexible
as a metaclass has multiple inheritence limitations.

A wrapper metaclass for building wrapper objects. It is instantiated by
specifying a class to be to be wrapped as a parent class with WrapperMetaClass
as the metaclass. This creates a wrapped/proxy base class for that type of
object. Note: this subverts the subclass mechanism as it does not actually
create a subclass of the wrapped class. Instead it is simply used to create the
forwarding of the member functions and attributes, while the wrapped class is
replaced with object as the parent.

Note: if a constructor is provided for the wrapper then it should call
init_wrapper manually. It also sets up '_wrapped' and '_wrapped_cls' attributes
so these cannot be attributes of the wrapped class.

This metaclass is to be used for wrapping clingo.Control, clingo.SolveHandle,
and clingo.Model objects.

Note: some ideas and code have been copied from:
https://code.activestate.com/recipes/496741-object-proxying/

'''

import functools
import inspect
from typing import Any, Optional


# ------------------------------------------------------------------------------
# Make proxy member functions and properties
# ------------------------------------------------------------------------------
def _make_wrapper_function(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        func=getattr(self._wrapped,fn.__name__)
        return func(*args, **kwargs)
    return wrapper

def _make_wrapper_property(name, get_only=True):
    def getter(self):
        return getattr(self._wrapped,name)
    def setter(self,x):
        return self._wrapped.__setattr__(name,x)
    return property(getter,setter)

def _check_wrapper_object(wrapper,strict=False):
    ActualType = type(wrapper._wrapped)
    WrappedType = wrapper._wrapped_cls
    if issubclass(ActualType,WrappedType): return
    if strict:
        raise TypeError(("Invalid proxied object {} not of expected type "
                         "{}").format(wrapper._wrapped,WrappedType))

# Constructor for every Predicate sub-class
def init_wrapper(wrapper: Any, *args: Any, **kwargs: Any) -> None:
    Wrapped = wrapper._wrapped_cls
    if "wrapped_" in kwargs:
        if len(args) != 0 and len(kwargs) != 1:
            raise ValueError(("Invalid initialisation: the 'wrapped_' argument "
                              "cannot be combined with other arguments"))
        wrapper._wrapped = kwargs["wrapped_"]
        _check_wrapper_object(wrapper,strict=False)
    else:
        wrapper._wrapped = Wrapped(*args,**kwargs)

# ------------------------------------------------------------------------------
# The wrapper metaclass
# ------------------------------------------------------------------------------
class WrapperMetaClass(type):

    def __new__(meta, name, bases, dct):
        if len(bases) != 1:
            raise TypeError("ProxyMetaClass requires exactly one parent class")
        Wrapped = bases[0]
        bases = (object,)

        ignore=["__init__", "__new__", "__dict__", "__weakref__", "__setattr__",
                "__getattr__"]

        if "_wrapped_cls" in dct:
            raise TypeError(("ProxyMetaClass cannot proxy a class with a "
                             "\"_wrapped_cls\" attribute: {}").format(PrClass))
        dct["_wrapped_cls"] = Wrapped

        # Mirror the attributes of the proxied class
        for key,value in Wrapped.__dict__.items():
            if key in ignore: continue
            if key in dct: continue

            if callable(value):
                dct[key]=_make_wrapper_function(value)
            else:
                dct[key]=_make_wrapper_property(key)

        # Create the init function if none is provided
        if "__init__" not in dct: dct["__init__"] = init_wrapper

        return super(WrapperMetaClass, meta).__new__(meta, name, bases, dct)

#------------------------------------------------------------------------------
# Alternative wrapper implementation that doesn't use a metaclass. The metaclass
# version is a problem when wrapping a class that already has a metaclass.  This
# version takes a class to be wrapped and an optional override class. In then
# creates an wrapper class that has all the properties and member functions of
# the override class as well as the wrapped class (with the override class
# overriding any function/property that is common to both).
# ------------------------------------------------------------------------------


def make_class_wrapper(inputclass: type, override: Optional[type] = None) -> type:
    def getattrdoc(cls, key):
        if not cls: return None
        try:
            attr = getattr(cls,key)
            if isinstance(attr,property) or callable(attr):
                return attr.__doc__
            return None
        except:
            return None

    Wrapped = inputclass
    name = inputclass.__name__

    w_ignore=set(["__init__", "__new__",  "__del__","__weakref__", "__setattr__",
                  "__getattr__", "__module__", "__name__", "__dict__",
                  "__abstractmethods__", "__orig_bases__", "__parameters__", "_abc_impl"])
    o_ignore=set(["__module__", "__new__", "__dict__", "__weakref__", "__name__"])
    dct = {}
    if override:
        for key,value in override.__dict__.items():
            if key in o_ignore: continue
            if key == "__doc__" and not value: continue
            dct[key] = value

    if "_wrapped_cls" in dct:
        raise TypeError(("The overrides cannot contain a "
                         "\"_wrapped_cls\" attribute: {}").format(dct))
    dct["_wrapped_cls"] = Wrapped

    # Mirror the attributes of the proxied class
    for key,value in Wrapped.__dict__.items():
        if key in w_ignore: continue
        if key in dct: continue

        if key == "__doc__" and key not in dct:
            dct[key]=value
        elif callable(value):
            dct[key]=_make_wrapper_function(value)
        else:
            dct[key]=_make_wrapper_property(key)

    # Create a basic init function if none is provided
    if "__init__" not in dct: dct["__init__"] = init_wrapper

    WrapperClass = type(name,(object,),dct)

#    print("\n{}".format(name))
#    if override:
#        print ("OVERRIDE: {}".format(override.__dict__.keys()))
#    print ("WRAPPED: {}\n".format(inputclass.__dict__.keys()))
#    print("NAME: {} : {}".format(WrapperClass.__name__, WrapperClass.__dict__.keys()))

    # Now go through and add docstrings if necessary
    for key in dir(WrapperClass):
        attr = getattr(WrapperClass, key)
        if inspect.isclass(attr): continue
        if callable(attr) and attr.__doc__: continue
        doc1 = getattrdoc(override,key)
        doc2 = getattrdoc(inputclass,key)
        if doc1: attr.__doc__ = doc1
        elif doc2: attr.__doc__ = doc2

    return WrapperClass


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

