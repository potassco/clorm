"""contains clorm specific types"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    ConstantStr = str
else:
    class ConstantStr(str):
        pass