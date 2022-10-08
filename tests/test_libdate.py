# ------------------------------------------------------------------------------
# Unit tests for the peewee based data model
# ------------------------------------------------------------------------------

import datetime
import unittest

from clorm import IntegerField, clingo
from clorm.lib.date import (
    DateField,
    EnumDate,
    EnumDateRange,
    cl_date_range,
    cl_dow,
    date_range,
    dow,
)

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class LibDateTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Make sure DateField does what we expect
    # --------------------------------------------------------------------------
    def test_datefield(self):
        dt = datetime.date(2017, 5, 16)
        raw = clingo.String("2017-05-16")
        self.assertEqual(DateField.pytocl(dt), raw)
        self.assertEqual(DateField.cltopy(raw), dt)

    # --------------------------------------------------------------------------
    # Make sure EnumDate does what we expect
    # --------------------------------------------------------------------------
    def test_enumdate(self):
        rawstr = clingo.String("2017-05-16")
        rawnum = clingo.Number(1)
        rawtuple = clingo.Function("", [rawnum, rawstr])
        ed = EnumDate(idx=1, date=datetime.date(2017, 5, 16))

        self.assertEqual(EnumDate.Field.pytocl(ed), rawtuple)
        self.assertEqual(EnumDate.Field.cltopy(rawtuple), ed)

    # --------------------------------------------------------------------------
    # Make sure the date functions behave correctly
    # --------------------------------------------------------------------------
    def test_dates(self):

        firstdate = datetime.date(2018, 1, 1)
        lastdate = datetime.date(2018, 1, 5)

        dates1 = [
            datetime.date(2018, 1, 1),
            datetime.date(2018, 1, 2),
            datetime.date(2018, 1, 3),
            datetime.date(2018, 1, 4),
        ]
        self.assertEqual(date_range(firstdate, lastdate), dates1)

        dates2 = [datetime.date(2018, 1, 1), datetime.date(2018, 1, 3)]
        self.assertEqual(date_range(firstdate, lastdate, 2), dates2)

        cl_firstdate = DateField.pytocl(firstdate)
        cl_lastdate = DateField.pytocl(lastdate)
        cl_2 = IntegerField.pytocl(2)

        cl_dates1 = [DateField.pytocl(d) for d in dates1]
        cl_dates2 = [DateField.pytocl(d) for d in dates2]

        self.assertEqual(cl_date_range(cl_firstdate, cl_lastdate), cl_dates1)
        self.assertEqual(cl_date_range(cl_firstdate, cl_lastdate, cl_2), cl_dates2)

        # Test the day-of-week function
        self.assertEqual(dow(firstdate), "monday")
        self.assertEqual(cl_dow(cl_firstdate), clingo.Function("monday", []))

    # --------------------------------------------------------------------------
    # Make sure the enumdate functions behave correctly
    # --------------------------------------------------------------------------
    def test_enumdates(self):

        firstdate = datetime.date(2018, 1, 1)
        lastdate = datetime.date(2018, 1, 5)
        datecount = 4

        dates1 = [
            EnumDate(idx=0, date=datetime.date(2018, 1, 1)),
            EnumDate(idx=1, date=datetime.date(2018, 1, 2)),
            EnumDate(idx=2, date=datetime.date(2018, 1, 3)),
            EnumDate(idx=3, date=datetime.date(2018, 1, 4)),
        ]
        dates2 = [
            EnumDate(idx=0, date=datetime.date(2018, 1, 1)),
            EnumDate(idx=1, date=datetime.date(2018, 1, 3)),
        ]

        cl_firstdate = DateField.pytocl(firstdate)
        cl_lastdate = DateField.pytocl(lastdate)
        cl_2 = IntegerField.pytocl(2)
        cl_4 = IntegerField.pytocl(4)

        edr1 = EnumDateRange(start=firstdate, stop=lastdate)
        edr2 = EnumDateRange(start=firstdate, count=2, step=2)

        self.assertEqual(edr1.enumdate_range(), dates1)
        self.assertEqual(edr2.enumdate_range(), dates2)
        self.assertEqual(edr1.last(), dates1[-1])

        rawdates1 = [EnumDate.Field.pytocl(ed) for ed in dates1]
        rawdates2 = [EnumDate.Field.pytocl(ed) for ed in dates2]

        self.assertEqual(edr1.cl_enumdate_range(), rawdates1)
        self.assertEqual(edr2.cl_enumdate_range(), rawdates2)

        # Test the day-of-week function
        self.assertEqual(edr1.dow(dates1[0]), "monday")
        self.assertEqual(edr1.cl_dow(rawdates1[0]), clingo.Function("monday", []))

    # --------------------------------------------------------------------------
    # Check that the docstring are the same
    # --------------------------------------------------------------------------
    def test_docstrings(self):
        self.assertEqual(dow.__doc__, cl_dow.__doc__)
        self.assertEqual(date_range.__doc__, cl_date_range.__doc__)

        Edr = EnumDateRange
        self.assertEqual(Edr.dow.__doc__, Edr.cl_dow.__doc__)
        self.assertEqual(Edr.enumdate_range.__doc__, Edr.cl_enumdate_range.__doc__)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
