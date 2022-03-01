#--------------------------------------------------------------------------------
# JSON Encoder/Decoder for clorm.Predicate and clingo.Symbol objects
#
# Note: the JSON encoding of the clingo.Symbol objects is not the same as
# running clingo with the ``--outf=2`` argument. The output here is intended to
# be easily machine processable whereas the clingo output would require parsing
# to regenerate the original symbol objects.
# --------------------------------------------------------------------------------
from collections.abc import Mapping
import clingo
import json
from .orm import *

__all__ = [
    'symbol_encoder',
    'symbol_decoder',
    'FactBaseCoder'
]

def _raise(obj):
    otype = type(obj)
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

    def stypestr(stype):
        st2str = {
            clingo.SymbolType.Infimum : "Infimum",
            clingo.SymbolType.Supremum : "Supremum",
            clingo.SymbolType.String : "String",
            clingo.SymbolType.Number : "Number",
            clingo.SymbolType.Function : "Function"}
        return st2str[stype]

    # A clingo.Symbol object
    js = {}
    js["clingo.SymbolType"] = stypestr(s.type)
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
        js["arguments"] = [symbol_encoder(a) for a in s.arguments]
        js["positive"] = s.positive
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
    if not isinstance(obj, Mapping): return obj
    if "clingo.SymbolType" not in obj: return obj
    stype_str = obj["clingo.SymbolType"]
    if stype_str == "Infimum": return clingo.Infimum
    if stype_str == "Supremum": return clingo.Supremum
    if stype_str == "String": return clingo.String(obj["string"])
    if stype_str == "Number": return clingo.Number(obj["number"])
    if stype_str == "Function":
        args = [ symbol_decoder(a) for a in obj["arguments"] ]
        positive = obj["positive"]
        return clingo.Function(obj["name"], args, positive)

    # A bad encoding?
    return obj

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class FactBaseCoder(object):
    '''A JSON Encoder/Decoder for clingo.Symbols, predicate instances, and fact bases.

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
        '''Decorator to register a Predicate sub-class with the FactBaseCoder'''

        self._register_predicate(cls)
        return cls

    def encoder(self, obj):
        '''JSON Encoder for clingo.Symbol, clorm.Predicate, and clorm.FactBase.

        Call by overiding the ``default`` argument for json.dump(s)

        class Fun(Predicate):
           aint = IntegerField()

        fc = FactCoder(predicates=[Fun])
        return json.dumps([Fun(aint=1), Fun(aint2)], default=fc.encoder)

        Args:
          obj: an object to encode as json
        '''
        if isinstance(obj, clingo.Symbol): return symbol_encoder(obj)
        if isinstance(obj, FactBase):
            return {
                "clorm.FactBase" : [ str(fp) for fp in obj.indexes ],
                "facts" : [ self.encoder(fct) for fct in obj] }
        for p in self._preds:
            if isinstance(obj, p):
                return { "clorm.Predicate" : p.__name__,
                         "raw" : symbol_encoder(obj.raw) }
        _raise(obj)

    def decoder(self, obj):
        '''JSON Decoder for clingo.Symbol, clorm.Predicate, and clorm.FactBase.

        Call by overiding the ``object_hook`` argument for json.load(s)

        return json.dumps(obj, default=self.encoder)

        class Fun(Predicate):
           aint = IntegerField()

        fc = FactCoder(predicates=[Fun])
        return json.loads(json_str, object_hook=fc.encoder)

        Args:
          json_object: a json encoded object

        '''
        if not isinstance(obj, Mapping): return obj
        if "clingo.SymbolType" in obj: return symbol_decoder(obj)
        if "clorm.FactBase" in obj and "facts" in obj:
            indexes = []
            for fname in obj["clorm.FactBase"]:
                fs = fname.split('.')
                if len(fs) < 2:
                    raise ValueError(("Expecting a field '.' split for index "
                                      "{}").format(fs))
                if fs[0] not in self._name2pred:
                    raise ValueError(("Unrecognised predicate name {} not one "
                                      "of {}").format(fs, self._name2pred.keys()))
                ppath = path(self._name2pred[fs[0]])
                for key in fs[1:]: ppath = ppath[key]
                indexes.append(ppath)
            facts = [ self.decoder(f) for f in obj["facts"] ]
            return FactBase(facts=facts, indexes=indexes)
        if not "clorm.Predicate" in obj: return obj
        pname = obj["clorm.Predicate"]
        if pname not in self._name2pred: return obj
        return self._name2pred[pname]._unify(symbol_decoder(obj["raw"]))

    #-------------------------------------------------------------------------
    # Convenience functions to call the JSON encoder and decoder
    #-------------------------------------------------------------------------

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
