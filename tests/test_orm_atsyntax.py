# ------------------------------------------------------------------------------
# Unit tests for Clorm ORM @-syntax integration (calling Python from ASP).
#
# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import calendar
import datetime
import unittest
from typing import Tuple

from clingo import Function, Number, String
from clingo import __version__ as clingo_version

# Official Clorm API imports
# Official Clorm API imports
from clorm.orm import (
    ComplexTerm,
    ConstantField,
    ContextBuilder,
    IntegerField,
    StringField,
    TypeCastSignature,
    make_function_asp_callable,
    make_method_asp_callable,
)

# Implementation imports
from clorm.orm.atsyntax import _get_annotations

from .support import check_errmsg

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "TypeCastSignatureTestCase",
    "ContextBuilderTestCase",
]

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class TypeCastSignatureTestCase(unittest.TestCase):
    def setUp(self):
        class DateField(StringField):
            pytocl = lambda dt: datetime.datetime.strftime(dt, "%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s, "%Y%m%d").date()

        class DowField(ConstantField):
            pytocl = lambda dt: calendar.day_name[dt.weekday()].lower()

        class EDate(ComplexTerm):
            idx = IntegerField()
            date = DateField()

            class Meta:
                name = "edate"

        self.DateField = DateField
        self.DowField = DowField
        self.EDate = EDate

    # --------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_signature(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        sig1 = TypeCastSignature(DateField)  # returns a single date
        sig2 = TypeCastSignature([DateField])  # returns a list of dates
        sig3 = TypeCastSignature(DateField, DowField)  # takes a date and returns the day or week

        sig4 = TypeCastSignature(EDate.Field, EDate.Field)  # takes an EDate and returns an EDate

        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [int])
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [DateField, DateField])

        date1 = datetime.date(2018, 1, 1)
        date2 = datetime.date(2019, 2, 2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        # Test simple output and list output

        def getdate1():
            return date1

        def getdates():
            return [date1, date2]

        cl_getdate1 = sig1.wrap_function(getdate1)
        cl_getdates = sig2.wrap_function(getdates)
        self.assertEqual(cl_getdate1(), String("20180101"))
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Use decoractor mode

        @sig3.wrap_function
        def getdow(dt):
            return dt

        result = getdow(String("20180101"))
        self.assertEqual(result, Function("monday", []))

        # Test a ComplexTerm input and output
        @sig4.wrap_function
        def getedate(indate):
            return indate

        self.assertEqual(getedate(edate1.raw), edate1.raw)
        self.assertEqual(getedate(edate2.raw), edate2.raw)

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self, x, y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = sig2.wrap_method(get_pair)

        t = Tmp(date1, date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])

    # --------------------------------------------------------------------------
    # Test the extended signatures with tuples
    # --------------------------------------------------------------------------

    def test_signature_with_tuples(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField), (IntegerField, DateField))
        sig2 = TypeCastSignature(DateField, [(IntegerField, DateField)])

        @sig1.wrap_function
        def test_sig1(pair):
            return (pair[0], pair[1])

        @sig2.wrap_function
        def test_sig2(dt):
            return [(1, dt), (2, dt)]

        s_raw = String("20180101")
        t1_raw = Function("", [Number(1), s_raw])
        t2_raw = Function("", [Number(2), s_raw])

        #        result = test_sig1(t1_raw)
        self.assertEqual(test_sig1(t1_raw), t1_raw)
        self.assertEqual(test_sig2(s_raw), [t1_raw, t2_raw])

    # --------------------------------------------------------------------------
    # Test using function annotations and reporting better errors
    # --------------------------------------------------------------------------
    def test_get_annotations_errors(self):

        IF = IntegerField

        with self.assertRaises(TypeError) as ctx:

            def bad() -> IF:
                return 1

            s = _get_annotations(bad, True)
        check_errmsg("Cannot ignore", ctx)

        with self.assertRaises(TypeError) as ctx:

            def bad(a: IF, b: IF):
                return 1

            s = _get_annotations(bad)
        check_errmsg("Missing function", ctx)

        with self.assertRaises(TypeError) as ctx:

            def bad(a, b) -> IF:
                return 1

            s = _get_annotations(bad)
        check_errmsg("Missing type cast", ctx)

        with self.assertRaises(TypeError) as ctx:

            def bad(a: IF, b) -> IF:
                return 1

            s = _get_annotations(bad)
        check_errmsg("Missing type cast", ctx)

    # --------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_make_function_asp_callable(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        date1 = datetime.date(2018, 1, 1)
        date2 = datetime.date(2019, 2, 2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        def getdate1():
            return date1

        def getdates():
            return [date1, date2]

        # Test wrapper as a normal function and specifying a signature
        cl_getdate1 = make_function_asp_callable(DateField, getdate1)
        self.assertEqual(cl_getdate1(), String("20180101"))

        cl_getdates = make_function_asp_callable([DateField], getdates)
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Test wrapper as a decorator and specifying a signature
        @make_function_asp_callable(DateField)
        def getdate1():
            return date1

        self.assertEqual(getdate1(), String("20180101"))

        @make_function_asp_callable([DateField])
        def getdates():
            return [date1, date2]

        self.assertEqual(getdates(), [String("20180101"), String("20190202")])

        @make_function_asp_callable
        def getdates2(x: DateField, y: EDate.Field) -> [DateField]:
            """GETDATES2"""
            return [date1, date2]

        self.assertEqual(
            getdates2(String("20180101"), edate1.raw), [String("20180101"), String("20190202")]
        )
        self.assertEqual(getdates2.__doc__, """GETDATES2""")

        # Test wrapper as a decorator and use python type annotations
        @make_function_asp_callable
        def method(x: int, y: str) -> Tuple[int, int]:
            return (x, int(y))

        self.assertEqual(method(Number(42), String("24")), Function("", [Number(42), Number(24)]))

        with self.assertRaises(TypeError) as ctx:

            @make_function_asp_callable
            def getdates3(x, y):
                return [date1, date2]

        with self.assertRaises(TypeError) as ctx:

            @make_function_asp_callable
            def getdates4(x: DateField, y: DateField):
                return [date1, date2]

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self, x, y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = make_method_asp_callable([DateField], get_pair)

            @make_method_asp_callable
            def get_pair2(self) -> [DateField]:
                return [self._x, self._y]

        t = Tmp(date1, date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])
        self.assertEqual(t.get_pair2(), [String("20180101"), String("20190202")])

    def test_make_function_asp_callable_with_tuples(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField), (IntegerField, DateField))
        sig2 = TypeCastSignature(DateField, [(IntegerField, DateField)])

        @make_function_asp_callable
        def test_sig1(pair: (IntegerField, DateField)) -> (IntegerField, DateField):
            return (pair[0], pair[1])

        @make_function_asp_callable
        def test_sig2(dt: DateField) -> [(IntegerField, DateField)]:
            return [(1, dt), (2, dt)]

        s_raw = String("20180101")
        t1_raw = Function("", [Number(1), s_raw])
        t2_raw = Function("", [Number(2), s_raw])

        #        result = test_sig1(t1_raw)
        self.assertEqual(test_sig1(t1_raw), t1_raw)
        self.assertEqual(test_sig2(s_raw), [t1_raw, t2_raw])

    # --------------------------------------------------------------------------
    # Improving the error messages generated by the wrappers
    # --------------------------------------------------------------------------
    def test_make_function_asp_callable_error_feedback(self):
        @make_function_asp_callable
        def test_sig1(v: IntegerField) -> IntegerField:
            return float(v)

        @make_function_asp_callable
        def test_sig2(v: IntegerField) -> IntegerField:
            raise ValueError("Error")

        with self.assertRaises(TypeError) as ctx:
            test_sig1(Number(1), Number(2))
        check_errmsg("test_sig1() takes 1 positional arguments but 2 ", ctx)

        if clingo_version >= "5.5.0":
            with self.assertRaises(TypeError) as ctx:
                test_sig1(Number(1))
            check_errmsg("an integer is required for output of test_sig1()", ctx)

        with self.assertRaises(ValueError) as ctx:
            test_sig2(Number(1))
        check_errmsg("Error: raised by test_sig2()", ctx)

    def test_make_method_asp_callable_error_feedback(self):
        class Tmp(object):
            def test1(self, v):
                return v

            @make_method_asp_callable
            def test_sig1(self, v: IntegerField) -> IntegerField:
                return float(v)

            @make_method_asp_callable
            def test_sig2(self, v: IntegerField) -> IntegerField:
                raise ValueError("Error")

        tmp = Tmp()

        with self.assertRaises(TypeError) as ctx:
            tmp.test_sig1(Number(1), Number(2))
        check_errmsg("test_sig1() takes 2 positional arguments but 3 ", ctx)

        if clingo_version >= "5.5.0":
            with self.assertRaises(TypeError) as ctx:
                tmp.test_sig1(Number(1))
            check_errmsg("an integer is required for output of test_sig1()", ctx)

        with self.assertRaises(ValueError) as ctx:
            tmp.test_sig2(Number(1))
        check_errmsg("Error: raised by test_sig2()", ctx)

    # --------------------------------------------------------------------------
    # Test that the input signature can be hashed
    # --------------------------------------------------------------------------
    def test_input_signature(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField), (IntegerField, DateField))
        sig2 = TypeCastSignature(DateField, [(IntegerField, DateField)])
        sigs = {}
        sigs[sig1.input_signature] = sig1
        sigs[sig2.input_signature] = sig2
        self.assertEqual(sigs[sig1.input_signature], sig1)
        self.assertEqual(sigs[sig2.input_signature], sig2)


# ------------------------------------------------------------------------------
# Tests for the ContextBuilder
# ------------------------------------------------------------------------------


class ContextBuilderTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_register(self):

        SF = StringField
        IF = IntegerField
        CF = ConstantField
        # Functions to add to the context
        def add(a: IF, b: IF) -> IF:
            return a + b

        def mirror(val: CF) -> CF:
            return val

        self.assertEqual(add(1, 4), 5)
        self.assertEqual(mirror("aname"), "aname")

        # Test the register function as a non-decorator
        cb1 = ContextBuilder()
        cb1.register(add)
        cb1.register(mirror)
        ctx1 = cb1.make_context()
        self.assertEqual(type(ctx1).__name__, "Context")
        self.assertTrue("add" in type(ctx1).__dict__)
        self.assertTrue("mirror" in type(ctx1).__dict__)

        n1 = Number(1)
        n2 = Number(2)
        n3 = Number(3)
        n4 = Number(4)
        c1 = Function("aname")
        self.assertEqual(ctx1.add(n1, n3), n4)
        self.assertEqual(ctx1.mirror(c1), c1)

        # Test registering functions but using external signatures
        def add2(a, b):
            return a + b

        def mirror2(val):
            return val

        cb2 = ContextBuilder()
        cb2.register(IF, IF, IF, add2)
        cb2.register(CF, CF, mirror2)
        ctx2 = cb2.make_context("Ctx2")
        self.assertEqual(type(ctx2).__name__, "Ctx2")
        self.assertEqual(ctx2.add2(n1, n3), n4)
        self.assertEqual(ctx2.mirror2(c1), c1)

        # Test the register function as a decorator
        cb3 = ContextBuilder()

        @cb3.register
        def add2(a: IF, b: IF) -> IF:
            return a + b

        self.assertEqual(add2(1, 2), 3)

        @cb3.register(IF, IF, IF)
        def add4(a, b):
            return a + b

        self.assertEqual(add4(1, 2), 3)

        ctx3 = cb3.make_context()
        self.assertEqual(ctx3.add2(n1, n2), n3)
        self.assertEqual(ctx3.add4(n1, n2), n3)

        # Test the register function in decorator mode where the function
        # returns a list.
        cb4 = ContextBuilder()

        @cb4.register
        def arange1(start: IF, end: IF) -> [IF]:
            return list(range(start, end))

        self.assertEqual(arange1(1, 2), [1])

        @cb4.register(IF, IF, [IF])
        def arange2(start, end):
            return list(range(start, end))

        self.assertEqual(arange1(1, 2), [1])

        @cb4.register([IF])
        def fixedrange():
            return list(range(1, 2))

        self.assertEqual(fixedrange(), [1])

        # Must sure we can register to return a list of tuples (bug issue #42)
        @cb4.register([(IF, IF)])
        def fixedrange2():
            return [(1, 1)]

        self.assertEqual(fixedrange2(), [(1, 1)])

        @cb4.register_name("blah", [(IF, IF)])
        def fixedrange3():
            return [(1, 1)]

        self.assertEqual(fixedrange3(), [(1, 1)])

        ctx4 = cb4.make_context()
        self.assertEqual(ctx4.arange1(n1, n2), [n1])
        self.assertEqual(ctx4.arange2(n1, n2), [n1])
        self.assertEqual(ctx4.fixedrange(), [n1])

    def test_register_name(self):
        SF = StringField
        IF = IntegerField
        CF = ConstantField

        n1 = Number(1)
        n2 = Number(2)
        n3 = Number(3)
        n4 = Number(4)
        s1 = String("ab")
        s2 = String("cd")
        s3 = String("abcd")
        c1 = Function("ab", [])
        c2 = Function("cd", [])
        c3 = Function("abcd", [])
        # Test the register_name as a decorator
        cb1 = ContextBuilder()

        @cb1.register_name("addi")  # use function annotations
        def add1(a: IF, b: IF) -> IF:
            return a + b  # external signature

        self.assertEqual(add1(1, 2), 3)

        @cb1.register_name("adds", SF, SF, SF)
        def add2(a, b):
            return a + b

        self.assertEqual(add2("ab", "cd"), "abcd")

        # Non-decorator call - re-using a function but with a different signature
        cb1.register_name("addc", CF, CF, CF, add1)

        # Non-decorator call - setting a function with the function annotation
        cb1.register_name("addi_alt", add1)

        ctx1 = cb1.make_context()
        self.assertEqual(ctx1.addi(n1, n2), n3)
        self.assertEqual(ctx1.addi_alt(n1, n2), n3)
        self.assertEqual(ctx1.adds(s1, s2), s3)
        self.assertEqual(ctx1.addc(c1, c2), c3)

        # Things that should fail
        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(ctx1.addc(s1, s2), s3)

        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(ctx1.addc(s1, s2), c3)

        # Fails since add2 has no function annotations
        with self.assertRaises(TypeError) as ctx:
            cb1.register_name("addo", add2)

        # Function name already assigned
        with self.assertRaises(ValueError) as ctx:
            cb1.register_name("addi", add1)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
