from __future__ import annotations

import inspect
import sys
from inspect import FrameInfo
from typing import (
    Any,
    Dict,
    ForwardRef,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    _eval_type,
    cast,
    get_args,
    get_origin,
)

from clingo import Symbol

from .noclingo import NoSymbol

_T0 = TypeVar("_T0", bound=Any)
_T1 = TypeVar("_T1", bound=Any)
_T2 = TypeVar("_T2", bound=Any)
_T3 = TypeVar("_T3", bound=Any)
_T4 = TypeVar("_T4", bound=Any)


AnySymbol = Union[Symbol, NoSymbol]


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

            # Turn the string type annotation into a ForwardRef for processing
            if (3, 10) > sys.version_info >= (3, 9, 8) or sys.version_info >= (3, 10, 1):
                value = ForwardRef(value, is_argument=False, is_class=True)
            else:
                value = ForwardRef(value, is_argument=False)
        try:
            if sys.version_info < (3, 13):
                type_ = _eval_type(value, base_globals, base_locals)
            else:
                type_ = _eval_type(value, base_globals, base_locals, type_params=())

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
