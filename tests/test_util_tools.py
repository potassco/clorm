# ------------------------------------------------------------------------------
# Unit tests for clorm.utils.tools
# ------------------------------------------------------------------------------

import unittest

from clorm.util.tools import all_equal

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "ToolsTestCase",
]


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


class ToolsTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_nonapi_all_equal(self):
        self.assertTrue(all_equal([]))
        self.assertTrue(all_equal([1]))
        self.assertTrue(all_equal([1, 1]))
        self.assertFalse(all_equal([1, 2]))
        self.assertTrue(all_equal([1, 1, 1, 1, 1, 1]))
        self.assertFalse(all_equal([1, 1, 1, 1, 1, 2]))
        self.assertFalse(all_equal(["b", "a", "b", "b"]))


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
