"""Predicate sub-class function templates.

Some of the functions of a Predicate sub-class are generated dynamically using
an `exec()` call. This file contains some template code snippets and functions
to help apply these templates.

"""
from typing import Dict

# ------------------------------------------------------------------------------
# Helper functions for PredicateMeta class to create a Predicate
# class constructor.
# ------------------------------------------------------------------------------

def expand_template(template: str, **kwargs: Dict[str, str]):
    """Expand the template by substituting the arguments.

    If the argument contains multiple lines then extra spaces are added to each
    line to preserve the correct indentation.

    """
    # Add spaces to each line of some multi-text input
    def add_spaces(num, text):
        space = " " * num
        out = []
        for idx, line in enumerate(text.splitlines()):
            if idx == 0:
                out = [line]
            else:
                out.append(space + line)
        return "\n".join(out)

    if not template:
        return ''
    lines = template.expandtabs(4).splitlines()
    outlines = []
    for line in lines:
        start = line.find("{%")
        if start == -1:
            outlines.append(line)
            continue
        end = line.find("%}", start)
        if end == -1:
            raise ValueError("Bad template expansion in {line}")
        keyword = line[start+2:end]
        text = add_spaces(start, kwargs[keyword])
        line = line[0:start] + text + line[end+2:]
        outlines.append(line)
    return "\n".join(outlines)


PREDICATE_TEMPLATE = r"""
def __init__(self,
             {{%args_signature%}}
             *, sign: bool=True) -> None:

    self._sign = bool(sign)

    {{%sign_check%}}
    {{%check_no_defaults%}}

    # Assign defaults for missing values and apply map tuple transform for complex values
    {{%assign_defaults%}}
    {{%check_complex%}}

    self._field_values = ({{%args%}})

    # Create the raw symbol and cache the hash
    self._raw = Function("{pdefn.name}",
                         ({{%args_raw%}}),
                         self._sign)
    self._hash = hash(self._raw)

@classmethod
def _unify(cls: Type[_P], raw: AnySymbol) -> Optional[_P]:
    try:
        raw_args = raw.arguments
        if len(raw_args) != {pdefn.arity}:
            return None

        {{%sign_check_unify%}}

        if raw.name != "{pdefn.name}":
            return None

        instance = cls.__new__(cls)
        instance._raw = raw
        instance._hash = hash(raw)
        instance._sign = raw.positive
        instance._field_values = ({{%args_cltopy%}})
        return instance
    except (TypeError, ValueError):
        return None
    except AttributeError as e:
        raise ValueError((f"Cannot unify with object {{raw}} ({{type(raw)}}) as "
                          "it is not a clingo Symbol Function object"))


def __bool__(self):
    return {bool_status}

def __len__(self):
    return {pdefn.arity}


def __eq__(self, other):
    if self.__class__ == other.__class__:
        return (self._sign == other._sign) and (self._field_values == other._field_values)

    return NotImplemented

def __lt__(self, other):
    if self.__class__ == other.__class__:
        return (self._sign < other._sign) or (self._field_values < other._field_values)

    return NoImplemented
"""

PREDICATE_EQ_NON_TUPLE ="""
def __eq__(self, other):
    if self.__class__ == other.__class__:
        return (self._sign == other._sign) and (self._field_values == other._field_values)
    return False if ininstance(other, Predicate) else NotImplemented
"""

PREDICATE_EQ_TUPLE ="""
def __eq__(self, other):
    if self.__class__ == other.__class__:
        return self._field_values == other._field_values
    if isinstance(other, Predicate):
        return self._field_values == other._field_values if other._meta.is_tuple else False
    return other == self._field_values
"""

PREDICATE_CMP_NON_TUPLE=r"""
def __{name}__(self, other):
    if self.__class__ == other.__class__:
        # Note: rely on False < True (True > False) and evaluation order
        return (self._sign {op} other._sign) or (self._field_values {op} other._field_values)

    if isinstance(other, Predicate):
        return self._raw {op} other._raw

    return NotImplemented
"""

PREDICATE_CMP_TUPLE=r"""
def __{name}__(self, other):
    if self.__class__ == other.__class__:
        self._field_values {op} other._field_values

    if isinstance(other, Predicate):
        return self._raw {op} other._raw

    return other {op} self._field_values
"""

def make_predicate_cmp(name, op, is_tuple=False):
    if is_tuple:
        return PREDICATE_CMP_NON_TUPLE.format(name=name, op=op)
    return PREDICATE_CMP_TUPLE.format(name=name, op=op)




CHECK_SIGN_TEMPLATE = r"""
# Check if the sign is allowed
if self._sign != {sign}:
    raise ValueError(f"Predicate {{type(self).__name__}}"
                     f"is defined to only allow {pdefn.sign} instances")
"""

CHECK_SIGN_UNIFY_TEMPLATE = r"""
if raw.positive != {sign}:
    return None
"""

NO_DEFAULTS_TEMPLATE = r"""
# Check for missing values that have no defaults
if MISSING in ({args}):
    for arg, name in ({named_args}):
        if arg is MISSING:
            raise TypeError((f"Missing argument for field \"{{name}}\""
                             f"(which has no default value)"))
"""

ASSIGN_DEFAULT_TEMPLATE = r"""
if {arg} is MISSING:
    {arg} = {arg}_field.default
"""

ASSIGN_COMPLEX_TEMPLATE = r"""
if not isinstance({arg}, {arg}_class):
    if isinstance({arg}, tuple) or (isinstance({arg}, Predicate) and {arg}.meta.is_tuple):
        {arg} = {arg}_class(*{arg})
    else:
        raise TypeError(f"Value {{{arg}}} ({{type({arg})}}) is not a tuple")
"""

PREDICATE_UNIFY_DOCSTRING = r"""
    Unify a (raw) Symbol object with the class.

    Returns None on failure to unify otherwise returns the new fact
"""

PREDICATE_BOOL_DOCSTRING = r"""
    Returns the boolean status of the fact.

    If Predicate is declared as a tuple then it behaves like a tuple and will
return False only if there are no defined fields. Otherwise it always returns
True.
 """

PREDICATE_LEN_DOCSTRING = r"""
    Returns the number of fields in the predicate.
"""

# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
