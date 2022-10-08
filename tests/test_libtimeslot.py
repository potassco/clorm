# ------------------------------------------------------------------------------
# Unit tests for the timeslot library
# ------------------------------------------------------------------------------

import datetime
import math
import unittest

from clorm import IntegerField, clingo
from clorm.lib.timeslot import Granularity, Range, TimeField, TimeSlot

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

__all__ = [
    "LibTimeSlotTimeFieldTestCase",
    "LibTimeSlotGranularityTestCase",
    "LibTimeSlotTestCase",
]


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class LibTimeSlotTimeFieldTestCase(unittest.TestCase):

    # --------------------------------------------------------------------------
    # Make sure TimeField does what we expect
    # --------------------------------------------------------------------------
    def test_timefield(self):
        tm1 = datetime.time(hour=12, minute=34)
        tm1_raw = clingo.String("12:34")
        self.assertEqual(TimeField.pytocl(tm1), tm1_raw)
        self.assertEqual(TimeField.cltopy(tm1_raw), tm1)

        tm2 = datetime.time(hour=2)
        tm2_raw = clingo.String("02:00")
        self.assertEqual(TimeField.pytocl(tm2), tm2_raw)
        self.assertEqual(TimeField.cltopy(tm2_raw), tm2)


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class LibTimeSlotGranularityTestCase(unittest.TestCase):
    def test_granularity_bad(self):
        with self.assertRaises(ValueError) as ctx:
            gran = Granularity(minutes=75)
        with self.assertRaises(ValueError) as ctx:
            gran = Granularity(minutes=125)

    def test_granularity_15min(self):
        gran = Granularity(minutes=15)
        self.assertEqual(gran.minutes(), 15)
        self.assertEqual(gran.num_per_day(), 4 * 24)
        self.assertEqual(datetime.timedelta(minutes=15), gran.num_to_timedelta(1))
        self.assertEqual(datetime.timedelta(minutes=45), gran.num_to_timedelta(3))
        td1 = datetime.timedelta(minutes=15)
        td2 = datetime.timedelta(minutes=16)
        td3 = datetime.timedelta(hours=1, minutes=31)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td1)), 1)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td2)), 2)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td3)), 7)

    def test_granularity_75min(self):
        gran = Granularity(minutes=45)
        self.assertEqual(gran.minutes(), 45)
        self.assertEqual(gran.num_per_day(), int(60 / 45 * 24))
        self.assertEqual(datetime.timedelta(minutes=45), gran.num_to_timedelta(1))
        self.assertEqual(datetime.timedelta(minutes=90), gran.num_to_timedelta(2))
        td1 = datetime.timedelta(minutes=0)
        td2 = datetime.timedelta(hours=1, minutes=31)
        td3 = datetime.timedelta(hours=3)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td1)), 0)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td2)), 3)
        self.assertEqual(math.ceil(gran.timedelta_to_num(td3)), 4)


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class LibTimeSlotTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    # Make sure EnumDate does what we expect
    # --------------------------------------------------------------------------
    def test_timeslotrange_init(self):

        # Test 12 hour timeslots - 12*60 minutes
        gran1 = Granularity(hours=12)
        tsr1 = Range(granularity=gran1)
        self.assertEqual(tsr1.num_timeslots(), 2)
        ts1 = TimeSlot(idx=0, start=datetime.time(hour=0, minute=0))
        ts2 = TimeSlot(idx=1, start=datetime.time(hour=12, minute=0))
        self.assertEqual([ts1, ts2], tsr1.range())
        self.assertEqual(2, len(tsr1.cl_range()))

        # Test 4 hour timeslots - 4*60 minutes
        gran2 = Granularity(hours=4)
        tsr2 = Range(granularity=gran2)
        self.assertEqual(tsr2.num_timeslots(), 6)
        ts1 = TimeSlot(idx=0, start=datetime.time(hour=0, minute=0))
        ts2 = TimeSlot(idx=1, start=datetime.time(hour=4, minute=0))
        ts3 = TimeSlot(idx=2, start=datetime.time(hour=8, minute=0))
        ts4 = TimeSlot(idx=3, start=datetime.time(hour=12, minute=0))
        ts5 = TimeSlot(idx=4, start=datetime.time(hour=16, minute=0))
        ts6 = TimeSlot(idx=5, start=datetime.time(hour=20, minute=0))
        self.assertEqual([ts1, ts2, ts3, ts4, ts5, ts6], tsr2.range())
        self.assertEqual(6, len(tsr2.cl_range()))

        # Test 15 min timeslots
        gran3 = Granularity(minutes=15)
        tsr2 = Range(granularity=gran3)
        self.assertEqual(tsr2.num_timeslots(), 4 * 24)
        self.assertEqual(tsr2.cl_num_timeslots(), IntegerField.pytocl(4 * 24))

        # Test 1 min timeslots
        gran4 = Granularity(minutes=1)
        tsr3 = Range(granularity=gran4)
        self.assertEqual(tsr3.num_timeslots(), 60 * 24)
        self.assertEqual(tsr3.cl_num_timeslots(), IntegerField.pytocl(60 * 24))

    def test_round_ceil_and_floor(self):
        gran = Granularity(minutes=30)
        rng = Range(gran)
        t1 = datetime.time(hour=0)
        t2 = datetime.time(hour=0, minute=30)
        t3 = datetime.time(hour=1, minute=0)
        t4 = datetime.time(hour=1, minute=30)
        t5 = datetime.time(hour=1, minute=48)
        t5_2 = datetime.time(hour=2, minute=0)

        c_1 = rng.timeslot_ceil(t1)
        c_2 = rng.timeslot_ceil(t2)
        c_3 = rng.timeslot_ceil(t3)
        c_4 = rng.timeslot_ceil(t4)
        c_5 = rng.timeslot_ceil(t5)
        self.assertEqual(c_1, TimeSlot(idx=0, start=t1))
        self.assertEqual(c_2, TimeSlot(idx=1, start=t2))
        self.assertEqual(c_3, TimeSlot(idx=2, start=t3))
        self.assertEqual(c_4, TimeSlot(idx=3, start=t4))
        self.assertEqual(c_5, TimeSlot(idx=4, start=t5_2))

        f_1 = rng.timeslot_floor(t1)
        f_2 = rng.timeslot_floor(t2)
        f_3 = rng.timeslot_floor(t3)
        f_4 = rng.timeslot_floor(t4)
        f_5 = rng.timeslot_floor(t5)
        self.assertEqual(f_1, TimeSlot(idx=0, start=t1))
        self.assertEqual(f_2, TimeSlot(idx=1, start=t2))
        self.assertEqual(f_3, TimeSlot(idx=2, start=t3))
        self.assertEqual(f_4, TimeSlot(idx=3, start=t4))
        self.assertEqual(f_5, TimeSlot(idx=3, start=t4))

        t1 = datetime.time(hour=0, minute=44)
        t2 = datetime.time(hour=0, minute=46)
        f = datetime.time(hour=0, minute=30)
        c = datetime.time(hour=1, minute=00)
        r_1 = rng.timeslot_floor(t1)
        r_2 = rng.timeslot_ceil(t1)
        r_3 = rng.timeslot_round(t1)
        r_4 = rng.timeslot_round(t2)
        self.assertEqual(r_1, TimeSlot(idx=1, start=f))
        self.assertEqual(r_2, TimeSlot(idx=2, start=c))
        self.assertEqual(r_3, TimeSlot(idx=1, start=f))
        self.assertEqual(r_4, TimeSlot(idx=2, start=c))

        cl_r_1 = rng.cl_timeslot_floor(TimeField.pytocl(t1))
        cl_r_2 = rng.cl_timeslot_ceil(TimeField.pytocl(t1))
        cl_r_3 = rng.cl_timeslot_round(TimeField.pytocl(t1))
        cl_r_4 = rng.cl_timeslot_round(TimeField.pytocl(t2))
        self.assertEqual(cl_r_1, TimeSlot(idx=1, start=f).raw)
        self.assertEqual(cl_r_2, TimeSlot(idx=2, start=c).raw)
        self.assertEqual(cl_r_3, TimeSlot(idx=1, start=f).raw)
        self.assertEqual(cl_r_4, TimeSlot(idx=2, start=c).raw)

    # --------------------------------------------------------------------------
    # Check that the docstring are the same
    # --------------------------------------------------------------------------
    def _test_docstrings(self):
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
