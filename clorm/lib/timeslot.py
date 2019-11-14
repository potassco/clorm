'''A library of Python timeslot functions and terms for use within an ASP
   program. When reasoning with time it is often unnecessary (and expensive) to
   reason at the minute (or smaller) granularity. Instead it is often useful to
   reason in multi-minute time blocks, such as 15 minute blocks.

   This library provides a flexible mechanism to define timeslots and the
   provides functions for converting times to timeslots. It also provides ASP
   callable functions. The limitation is that the time granurality is minute
   based and the must divide a day evenly (e.g., 15 minute blocks).

   Note: functions that are ASP callable have a prefix ``cl_``.

   .. code-block:: none

      date(@cl_date_range("2018-01-01", "2018-01-10")).

   This will generate a number of ``date/1`` facts, each containing a date
   encoded string between the desired two dates.

'''

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

import datetime
import math
from ..orm import ComplexTerm, IntegerField, StringField,\
    ConstantField, make_function_asp_callable, make_method_asp_callable

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
class TimeField(StringField):
    '''A Clorm TimeField that converts to and from a Python datetime.time
       object. Encodes time as a string in "HH:MM" format.

    '''
    def _cltopy(timestr):
        dtstr = "2000-01-01 {}".format(timestr)
        return datetime.datetime.strptime(dtstr,"%Y-%m-%d %H:%M").time()
    cltopy = _cltopy

    pytocl = lambda tm: tm.strftime("%H:%M")

#------------------------------------------------------------------------------
# Granularity for a timeslot
#------------------------------------------------------------------------------

class Granularity(object):
    MINUTES_PER_HOUR=60
    MINUTES_PER_DAY=24*MINUTES_PER_HOUR

    def __init__(self, hours=0, minutes=0):

        # Calculate the granularity in minutes
        tmp = hours*Granularity.MINUTES_PER_HOUR + minutes
        td = datetime.timedelta(minutes=tmp)
        if Granularity.MINUTES_PER_DAY % tmp != 0:
            raise ValueError(("Granularity of {} does not evenly divide 24 "
                              "hours".format(td)))
        self._minutes = tmp
        self._timedelta = datetime.timedelta(minutes=self._minutes)

    def num_per_day(self):
        return int(Granularity.MINUTES_PER_DAY/self._minutes)

    def minutes(self):
        return self._minutes

    def timedelta(self):
        return self._timedelta

    def num_to_minutes(self, num):
        return self._minutes*num

    def num_to_timedelta(self, num):
        return datetime.timedelta(minutes=(self._minutes*num))

    def minutes_to_num(self, minutes):
        return minutes/self._minutes

    def timedelta_to_num(self, delta):
        '''Converts timedelta to num intervals (returns a float).'''
        delta_mins = delta.total_seconds()/60.0
        return delta_mins/self._minutes

    # --------------------------------------------------------------------------
    # Generate some wrapper functions
    # --------------------------------------------------------------------------
    cl_num_per_day = make_method_asp_callable(IntegerField, num_per_day)
    cl_minutes = make_method_asp_callable(IntegerField, minutes)
    cl_num_to_minutes = make_method_asp_callable(IntegerField, IntegerField, num_to_minutes)
    cl_minutes_to_num = make_method_asp_callable(IntegerField, IntegerField, minutes_to_num)

#------------------------------------------------------------------------------
# TimeSlot is a tuple containing an index and a time object.
#------------------------------------------------------------------------------

class TimeSlot(ComplexTerm):
    '''An enumerated complex term for encoding time slots.

    '''
    idx = IntegerField()
    start = TimeField()
    class Meta: is_tuple=True

#------------------------------------------------------------------------------
# An enumerated date range class
#------------------------------------------------------------------------------

class Range(object):
    '''A class to generate a timeslots of a given granularity

    '''
    ZERO_TIME=datetime.time(hour=0,minute=0,second=0)

    def __init__(self, granularity):
        self._granularity = granularity

        num_timeslots = self._granularity.num_per_day()
        self._starttime_to_timeslot = {}
        self._timeslots = []
        currdt = datetime.datetime.combine(datetime.date.today(), Range.ZERO_TIME)
        for idx in range(0, num_timeslots):
            ts = TimeSlot(idx=idx, start=currdt.time())
            currdt += self._granularity.timedelta()
            self._timeslots.append(ts)
            self._starttime_to_timeslot[ts.start] = ts

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------

    @property
    def granularity(self):
        return self._granularity

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------

    def num_timeslots(self):
        return self._granularity.num_per_day()

    def range(self):
        return list(self._timeslots)

    def timeslot(self, idx):
        return self._timeslots[idx]

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------

    def _timeslot_partial_idx(self, time):
        ct = datetime.datetime.combine(datetime.date.today(), time)
        zt = datetime.datetime.combine(datetime.date.today(), Range.ZERO_TIME)
        delta = ct - zt
        delta_mins = delta.total_seconds()/60
        return delta_mins/self._granularity.minutes()

    def timeslot_round(self, time):
        idx = round(self._timeslot_partial_idx(time))
        return self.timeslot(idx)

    def timeslot_ceil(self, time):
        idx = math.ceil(self._timeslot_partial_idx(time))
        return self.timeslot(idx)

    def timeslot_floor(self, time):
        idx = math.floor(self._timeslot_partial_idx(time))
        return self.timeslot(idx)

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    cl_range = make_method_asp_callable([TimeSlot.Field], range)
    cl_num_timeslots = make_method_asp_callable(IntegerField, num_timeslots)
    cl_timeslot = make_method_asp_callable(IntegerField, TimeSlot.Field, timeslot)
    cl_timeslot_round = make_method_asp_callable(TimeField, TimeSlot.Field, timeslot_round)
    cl_timeslot_ceil = make_method_asp_callable(TimeField, TimeSlot.Field, timeslot_ceil)
    cl_timeslot_floor = make_method_asp_callable(TimeField, TimeSlot.Field, timeslot_floor)

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Generate some wrapper functions
#------------------------------------------------------------------------------


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
