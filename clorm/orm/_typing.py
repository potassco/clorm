from __future__ import annotations

import inspect
import sys
from inspect import FrameInfo
from typing import Any, Dict, ForwardRef, Optional, Tuple, Type, TypeVar, Union, _eval_type, cast

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
        if type(t).__name__ in {"AnnotatedMeta", "_AnnotatedAlias"}:
            # weirdly this is a runtime requirement, as well as for mypy
            return cast(Type[Any], Annotated)
        return getattr(t, "__origin__", None)

else:
    from typing import get_args, get_origin


if sys.version_info < (3, 7):

    def get_args(t: Type[Any]) -> Tuple[Any, ...]:
        """Simplest get_args compatibility layer possible.
        The Python 3.6 typing module does not have `_GenericAlias` so
        this won't work for everything. In particular this will not
        support the `generics` module (we don't support generic models in
        python 3.6).
        """
        if type(t).__name__ in {"AnnotatedMeta", "_AnnotatedAlias"}:
            return t.__args__ + t.__metadata__
        return getattr(t, "__args__", ())

elif sys.version_info < (3, 8):
    from typing import Callable, _GenericAlias

    def get_args(t: Type[Any]) -> Tuple[Any, ...]:
        """Compatibility version of get_args for python 3.7.
        Mostly compatible with the python 3.8 `typing` module version
        and able to handle almost all use cases.
        """
        if type(t).__name__ in {"AnnotatedMeta", "_AnnotatedAlias"}:
            return t.__args__ + t.__metadata__
        if isinstance(t, _GenericAlias):
            res = t.__args__
            if t.__origin__ is Callable and res and res[0] is not Ellipsis:
                res = (list(res[:-1]), res[-1])
            return res
        return getattr(t, "__args__", ())


if sys.version_info < (3, 9):
    from ast import literal_eval

    def _strip_quoted_annotations(annotation: str) -> str:
        """Strip quotes around any annotations.

        This is needed because the _eval_type() function for Python 3.8 and 3.7 doesn't
        handle a ForwardRef that contains a quoted string.

        """
        try:
            output = literal_eval(annotation)
            return output if isinstance(output, str) else annotation
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            return annotation


def print_dict(adict):
    for k, v in adict.items():
        print(f"{k} => {v}")


def resolve_annotations(
    raw_annotations: Dict[str, Type[Any]],
    module_name: Optional[str] = None,
    locals_: Dict[str, Any] = None,
) -> Dict[str, Type[Any]]:
    """
    Taken from https://github.com/pydantic/pydantic/blob/1.10.X-fixes/pydantic/typing.py#L376
    with some modifications for handling when the first _eval_type() call fails.

    Resolve string or ForwardRef annotations into type objects if possible.
    """
    base_locals: Dict[str, Type[Any]] = dict(locals_) if locals_ else {}
    base_globals: Optional[Dict[str, Any]] = None
    if module_name:
        try:
            module = sys.modules[module_name]
        except KeyError:
            # happens occasionally, see https://github.com/pydantic/pydantic/issues/2363
            pass
        else:
            base_globals = module.__dict__

    annotations = {}
    frameinfos: Union[list[FrameInfo], None] = None
    for name, value in raw_annotations.items():
        if isinstance(value, str):

            # Strip quoted string annotions for Python 3.7 and 3.8
            if sys.version_info < (3, 9):
                value = _strip_quoted_annotations(value)

            # Turn the string type annotation into a ForwardRef for processing
            if (3, 10) > sys.version_info >= (3, 9, 8) or sys.version_info >= (3, 10, 1):
                value = ForwardRef(value, is_argument=False, is_class=True)
            else:
                value = ForwardRef(value, is_argument=False)
        try:
            type_ = _eval_type(value, base_globals, base_locals)

        except NameError:
            # The type annotation could refer to a definition at a non-global scope so build
            # the locals from the calling context. We reuse the same set of locals for
            # multiple annotations.
            if frameinfos is None:
                frameinfos = inspect.stack()
                if len(frameinfos) < 4:
                    raise RuntimeError(
                        'Cannot resolve field "{name}" with type annotation "{value}"'
                    )
                frameinfos = frameinfos[3:]
            type_ = None
            count = 0
            while frameinfos:
                try:
                    type_ = _eval_type(value, base_globals, base_locals)
                    break
                except NameError:
                    finfo = frameinfos.pop(0)
                    base_locals.update(finfo.frame.f_locals)
            if type_ is None:
                raise RuntimeError(
                    f'Cannot resolve field "{name}" with type annotation "{value}"'
                )
        annotations[name] = type_
    return annotations
