
import sys
from typing import Any, TypeVar, Type, Optional, cast, Tuple, Union
from clingo import Symbol
from .noclingo import NoSymbol

_T0 = TypeVar("_T0", bound=Any)
_T1 = TypeVar("_T1", bound=Any)
_T2 = TypeVar("_T2", bound=Any)
_T3 = TypeVar("_T3", bound=Any)
_T4 = TypeVar("_T4", bound=Any)


AnySymbol = Union[Symbol, NoSymbol]


# copied from https://github.com/samuelcolvin/pydantic/blob/master/pydantic/typing.py
if sys.version_info < (3, 8):
    from typing_extensions import Annotated

    def get_origin(t: Type[Any]) -> Optional[Type[Any]]:
        if type(t).__name__ in {'AnnotatedMeta', '_AnnotatedAlias'}:
            # weirdly this is a runtime requirement, as well as for mypy
            return cast(Type[Any], Annotated)
        return getattr(t, '__origin__', None)
else:
    from typing import get_origin, get_args


if sys.version_info < (3, 7):
    def get_args(t: Type[Any]) -> Tuple[Any, ...]:
        """Simplest get_args compatibility layer possible.
        The Python 3.6 typing module does not have `_GenericAlias` so
        this won't work for everything. In particular this will not
        support the `generics` module (we don't support generic models in
        python 3.6).
        """
        if type(t).__name__ in {'AnnotatedMeta', '_AnnotatedAlias'}:
            return t.__args__ + t.__metadata__
        return getattr(t, '__args__', ())

elif sys.version_info < (3, 8):
    from typing import _GenericAlias, Callable

    def get_args(t: Type[Any]) -> Tuple[Any, ...]:
        """Compatibility version of get_args for python 3.7.
        Mostly compatible with the python 3.8 `typing` module version
        and able to handle almost all use cases.
        """
        if type(t).__name__ in {'AnnotatedMeta', '_AnnotatedAlias'}:
            return t.__args__ + t.__metadata__
        if isinstance(t, _GenericAlias):
            res = t.__args__
            if t.__origin__ is Callable and res and res[0] is not Ellipsis:
                res = (list(res[:-1]), res[-1])
            return res
        return getattr(t, '__args__', ())