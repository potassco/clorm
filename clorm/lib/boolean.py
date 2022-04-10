'''A library of Python bool functions and terms for use within an ASP
   program. 

'''


from typing import Any
from clorm.orm.core import AnySymbol, BaseField, IntegerField
from clorm.orm.noclingo import Number


BOOL_FALSE = {0, '0', 'off', 'f', 'false', 'n', 'no'}
BOOL_TRUE = {1, '1', 'on', 't', 'true', 'y', 'yes'}

def bool_validator(v: Any) -> bool:
    if v is True or v is False:
        return v
    if isinstance(v, str):
        v = v.lower()
    if v in BOOL_TRUE:
        return True
    if v in BOOL_FALSE:
        return False
    raise TypeError(f"value '{v}' could not be parsed to a boolean")

class BooleanField(BaseField):
    """A field to convert between a Clingo.Number/String object and a Python bool.
    
    Conversion failes if the value/clingo.Symbol is not one of the following:
    - a valid boolean ('True' or 'False')
    - the integers '0' or '1'
    - a 'str' which when converted to lower case in one of '0', 'off', 'f', 'false', 'n', 'no', '1', 'on', 't', 'true', 'y', 'yes'
    """

    def cltopy(symbol: AnySymbol) -> bool:
        try:
            return bool_validator(symbol.number)
        except (AttributeError, RuntimeError):
            pass
        try:
            return bool_validator(symbol.string)
        except (AttributeError, RuntimeError):
            pass
        raise TypeError(("Object '{}' ({}) is not a Number/String "
                         "Symbol").format(symbol,type(symbol)))

    def pytocl(v):
        val = int(bool_validator(v))
        return Number(val)


class StrictBooleanField(IntegerField):
    """A field to convert between a Clingo.Number object and a Python bool
    - Clingo.Number(0) will be converted to 'False'
    - Clingo.Number(1) will be converted to 'True'

    For everything else the conversion fails
    """
    def cltopy(symbol) -> bool:
        if symbol == 1:
            return True
        if symbol == 0:
            return False
        raise TypeError("value must be either '0' or '1'")

    def pytocl(v):
        if isinstance(v, bool):
            return int(v)
        raise TypeError("value is not a valid boolean")