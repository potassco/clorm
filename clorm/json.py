#--------------------------------------------------------------------------------
# JSON Encoder/Decoder for clorm.Predicate and clingo.Symbol objects
#
# Note: the JSON encoding of the clingo.Symbol objects is not the same as
# running clingo with the ``--outf=2`` argument. The output here is intended to
# be easily machine processable whereas the clingo output would require parsing
# to regenerate the original symbol objects.
# --------------------------------------------------------------------------------
import clingo
import json
from .orm import *

__all__ = [
    'symbol_encoder',
    'symbol_decoder',
    'PredicateCoder'
]

def _raise(obj):
    otype = type(s)
    raise TypeError("Object of type '{}' is not JSON serializable".format(otype))

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def symbol_encoder(s):
    '''A JSON encoder for clingo.Symbol objects.

    Example usage:
    sym = clingo.Function("afact", [clingo.Number(1)])
    json_str = json.dumps(sym, default=encoder)

    Args:
      symbol(clingo.Symbol): a symbol object
    '''

    if not isinstance(s, clingo.Symbol): _raise(s)

    # A clingo.Symbol object
    js = {}
    js["clingo.SymbolType"] = str(s.type)
    if s.type == clingo.SymbolType.Infimum: return js
    if s.type == clingo.SymbolType.Supremum: return js
    if s.type == clingo.SymbolType.Number:
        js["number"] = s.number
        return js
    if s.type == clingo.SymbolType.String:
        js["string"] = s.string
        return js
    if s.type == clingo.SymbolType.Function:
        js["name"] = s.name
        js["arguments"] = s.arguments
        return js

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def symbol_decoder(obj):
    '''A JSON Decoder for clingo.Symbol objects.

    Example usage:
    symbol = json.loads(json, default=encoder)

    Args:
      obj: a JSON object
    '''

    if "clingo.SymbolType" not in obj: return obj
    stype_str = obj["clingo.SymbolType"]
    if stype_str == "Infimum": return clingo.Infimum
    if stype_str == "Supremum": return clingo.Supremum
    if stype_str == "String": return clingo.String(obj["string"])
    if stype_str == "Number": return clingo.Number(obj["number"])
    if stype_str == "Function":
        return clingo.Function(obj["name"], obj["arguments"])

    # A bad encoding?
    return obj

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class FactCoder(object):
    '''A JSON Encoder/Decoder for facts (i.e., Predicate sub-classed objects).

    Provides a helper class for encoding and decoding facts to JSON. The
    predicates of interest are passed in the constructor or can be registered
    using a decorator.

    Args:
      predicates([Predicate]): a list of predicates to handle encoding/decoding

    '''
    def __init__(self, predicates=[]):
        self._preds = []
        self._predset = set()
        self._name2pred = {}
        for p in predicates: self._register_predicate(p)

    def _register_predicate(self, cls):
        if cls in self._predset: return    # ignore if already registered
        if not issubclass(cls, Predicate):
            raise TypeError("{} is not a Predicate sub-class".format(cls))
        self._predset.add(cls)
        self._preds.append(cls)
        self._name2pred[cls.__name__] = cls

    #-------------------------------------------------------------------------
    #
    #-------------------------------------------------------------------------
    def register(self, cls):
        '''Decorator to register a Predicate sub-class with the FactCoder'''

        self._register_predicate(cls)
        return cls

    def encoder(self, obj):
        '''JSON Encoder.

        Call by overiding the ``default`` argument for json.dump(s)

        class Fun(Predicate):
           aint = IntegerField()

        fc = FactCoder(predicates=[Fun])
        return json.dumps([Fun(aint=1), Fun(aint2)], default=fc.encoder)

        Args:
          obj: an object to encode as json
        '''
        if isinstance(obj, clingo.Symbol): return symbol_encoder(obj)
        for p in self._preds:
            if isinstance(obj, p):
                js = {}
                js["clorm.Predicate"] = p.__name__
                js["raw"] = symbol_encoder(obj.raw)
                return js
        _raise(obj)

    def decoder(self, obj):
        '''JSON Decoder.

        Call by overiding the ``object_hook`` argument for json.load(s)

        return json.dumps(obj, default=self.encoder)

        class Fun(Predicate):
           aint = IntegerField()

        fc = FactCoder(predicates=[Fun])
        return json.loads(json_str, object_hook=fc.encoder)

        Args:
          json_object: a json encoded object

        '''
        if "clingo.SymbolType" in obj: return symbol_decoder(obj)
        if not "clorm.Predicate" in obj: return obj
        pname = obj["clorm.Predicate"]
        if pname not in self._name2pred: return obj
        return self._name2pred[pname](raw=obj["raw"])

    def dumps(self, obj, indent=None, sort_keys=False):
        '''A convenience function for calling json.dumps'''
        return json.dumps(obj, indent=indent,
                          sort_keys=sort_keys, default=self.encoder)

    def dump(self, obj, fp, indent=None, sort_keys=False):
        '''A convenience function for calling json.dump'''
        return json.dump(obj, fp, indent=indent,
                         sort_keys=sort_keys, default=self.encoder)

    def loads(self, json_str):
        '''A convenience function for calling json.loads'''
        return json.loads(json_str, object_hook=self.decoder)

    def load(self, fp):
        '''A convenience function for calling json.load'''
        return json.load(fp, object_hook=self.decoder)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
