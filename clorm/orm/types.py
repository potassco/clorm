"""contains clorm specific types"""

from typing import TYPE_CHECKING, Generic, Tuple, TypeVar


if TYPE_CHECKING:
    ConstantStr = str
else:
    class ConstantStr(str):
        pass

_T = TypeVar('_T')

if TYPE_CHECKING:
    HeadList = Tuple[_T, ...]
    HeadListReversed = Tuple[_T, ...]
    TailList = Tuple[_T, ...]
    TailListReversed = Tuple[_T, ...]
else:
    class HeadList(Generic[_T]):
        pass
    class HeadListReversed(Generic[_T]):
        pass
    class TailList(Generic[_T]):
        pass
    class TailListReversed(Generic[_T]):
        pass