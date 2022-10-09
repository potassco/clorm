# ------------------------------------------------------------------------------
# Unit tests for the bool library
# ------------------------------------------------------------------------------


import unittest

from clorm.lib.boolean import BooleanField, StrictBooleanField
from clorm.orm.noclingo import Number, String
from tests.support import check_errmsg


class LibBoolTestCase(unittest.TestCase):

    # --------------------------------------------------------------------------
    # Make sure BooleanField does what we expect
    # --------------------------------------------------------------------------
    def test_booleanfield(self):
        symstr = Number(0)
        self.assertEqual(type(BooleanField.cltopy(symstr)), bool)
        self.assertEqual(BooleanField.cltopy(symstr), False)
        self.assertEqual(BooleanField.pytocl(0), symstr)

        symstr = String("false")
        self.assertEqual(type(BooleanField.cltopy(symstr)), bool)
        self.assertEqual(BooleanField.cltopy(symstr), False)

        self.assertEqual(BooleanField.pytocl("false"), Number(0))
        self.assertEqual(BooleanField.pytocl("TrUe"), Number(1))
        self.assertEqual(BooleanField.pytocl("on"), Number(1))
        self.assertEqual(BooleanField.pytocl("off"), Number(0))

        with self.assertRaises(TypeError) as ctx:
            BooleanField.cltopy(String("2"))
        check_errmsg("value '2'", ctx)

    # --------------------------------------------------------------------------
    # Make sure StrictBooleanField does what we expect
    # --------------------------------------------------------------------------
    def test_strictbooleanfield(self):
        symstr = Number(1)
        self.assertEqual(type(StrictBooleanField.cltopy(symstr)), bool)
        self.assertEqual(StrictBooleanField.cltopy(symstr), True)
        self.assertEqual(StrictBooleanField.pytocl(True), symstr)

        with self.assertRaises(TypeError) as ctx:
            StrictBooleanField.cltopy(Number(2))
        check_errmsg("value must be either", ctx)
