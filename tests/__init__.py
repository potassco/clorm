# -----------------------------------------------------------------------------
# By default being able to switch to NOCLINGO mode is disabled. But for the
# unittests we enable it.
# -----------------------------------------------------------------------------

import os

os.environ["CLORM_NOCLINGO"] = "True"

from .test_clingo import *
from .test_forward_ref import *
from .test_json import *
from .test_libdate import LibDateTestCase
from .test_libtimeslot import *
from .test_monkey import *
from .test_mypy import *
from .test_orm_atsyntax import *
from .test_orm_core import *
from .test_orm_factbase import *
from .test_orm_factcontainers import *
from .test_orm_noclingo import *
from .test_orm_query import *
from .test_orm_symbols_facts import *
from .test_util_oset import OrderedSetTestCase
from .test_util_tools import *
from .test_util_wrapper import *
