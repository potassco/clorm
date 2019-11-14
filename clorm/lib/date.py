'''A library of Python date functions and terms for use within an ASP
   program. Some Clorm fields and complex terms are defined as well as functions
   to use them.

   Any function that is to be called from within an ASP program will be prefixed
   with: ``cl_``.

   .. code-block:: none

      date(@cl_date_range("2018-01-01", "2018-01-10")).

   This will generate a number of ``date/1`` facts, each containing a date
   encoded string between the desired two dates.

'''

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

import datetime
import calendar
from ..orm import ComplexTerm, IntegerField, StringField,\
    ConstantField, make_function_asp_callable, make_method_asp_callable

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
class DateField(StringField):
    '''A Clorm DateField that converts to and from a Python date and a clingo string
    encoded date.

    '''
    pytocl = lambda dt: dt.strftime("%Y-%m-%d")
    cltopy = lambda s: datetime.datetime.strptime(s,"%Y-%m-%d").date()

#------------------------------------------------------------------------------
# Enumerated Date is a tuple containing an index and a date.
#------------------------------------------------------------------------------

class EnumDate(ComplexTerm):
    '''An enumerate complex term for encode num, date pairs, where the encoded num
    maps consecutive dates within the range.

    '''
    idx = IntegerField()
    date = DateField()
    class Meta: is_tuple=True

#------------------------------------------------------------------------------
# An enumerated date range class
#------------------------------------------------------------------------------

class EnumDateRange(object):
    '''A class to generate and query dates within a range.

    Like the python range() function - it generates from a starting date to a
    stop date (but not including the stop date), incrementing by a step
    count. Also includes a test predicate - if the predicate returns true for
    the date then the date is included. For example, can use the test to skip
    weekends.

    '''

    def __init__(self, start, stop=None, step=1, test=lambda x: True, count=None):
        self._step = datetime.timedelta(days=step)
        self._dates = []

        # Make sure that both count and stop are not specified at the same time
        if count is not None and stop is not None:
            raise ValueError("'stop' and 'count' parameters are mutually-exclusive")

        idx=0
        # A start to stop
        if stop is not None:
            if start >= stop:
                raise ValueError("'start' date must be less than the 'stop' date")
            while start < stop:
                if test(start):
                    self._dates.append(EnumDate(idx=idx,date=start))
                    idx += 1
                start += self._step

        # A start with count
        else:
            if count < 1: raise ValueError("'count' must be at least 1")
            while count > 0:
                if test(start):
                    self._dates.append(EnumDate(idx=idx,date=start))
                    idx += 1
                    count -= 1
                start += self._step

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------

    def first(self):
        '''Return the first enumerated date in the range'''
        return self._dates[0]

    def last(self):
        '''Return the last enumerated date in the range'''
        return self._dates[-1]

    def enumdate_range(self):
        '''Return the list of all the enumerated dates in the range'''
        return list(self._dates)

    def dow(self, ed):
        '''Return the day of the week for an enumerated date'''
        if not isinstance(ed, EnumDate):
            raise ValueError("Not an EnumDate")
        return calendar.day_name[ed.date.weekday()].lower()

    # --------------------------------------------------------------------------
    # Generate some wrapper functions
    # --------------------------------------------------------------------------
    cl_first = make_method_asp_callable(EnumDate.Field, first)
    cl_last = make_method_asp_callable(EnumDate.Field, last)
    cl_enumdate_range = make_method_asp_callable([EnumDate.Field], enumdate_range)
    cl_dow = make_method_asp_callable(EnumDate.Field, ConstantField, dow)


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------


class DateRange(object):
    '''A class to generate and query dates within a range.

    Like the python range() function - it generates from a starting date to a
    stop date (but not including the stop date), incrementing by a step
    count. Also includes a test predicate - if the predicate returns true for
    the date then the date is included. For example, can use the test to skip
    weekends.

    '''

    def __init__(self, start, stop=None, step=1, test=lambda x: True, count=None):
        self._edr = EnumDateRange(start=start,stop=stop,step=step,
                                  test=test,count=count)



    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------

    def first(self):
        '''Return the first date in the range'''
        return self._edr.first[1]

    def last(self):
        '''Return the last date in the range'''
        return self._edr.last[1]

    def date_range(self):
        '''Return the list of all the dates in the range'''
        return [ dt for idx, dt in self._edr.enumdate_range() ]

    def dow(self, dt):
        '''Return the day of the week for a date'''
        return calendar.day_name[dt.weekday()].lower()

    # --------------------------------------------------------------------------
    # Generate some wrapper functions
    # --------------------------------------------------------------------------
    cl_first = make_method_asp_callable(DateField, first)
    cl_last = make_method_asp_callable(DateField, last)
    cl_date_range = make_method_asp_callable([DateField], date_range)
    cl_dow = make_method_asp_callable(DateField, ConstantField, dow)

#------------------------------------------------------------------------------
# date_range takes a start and end date and a step (default 1)
# ------------------------------------------------------------------------------
def date_range(start, stop, step=1):
    """Generate dates within a range, with optional day step counter"""
    dtrange = DateRange(start=start, stop=stop, step=step)
    return dtrange.date_range()

#------------------------------------------------------------------------------
# dow - callable by python - returns the day of the week
#------------------------------------------------------------------------------

def dow(dt):
    """Return the day of the week for a date"""
    return calendar.day_name[dt.weekday()].lower()

#------------------------------------------------------------------------------
# Function signatures to generate ASP callable functions
#------------------------------------------------------------------------------
cl_date_range = make_function_asp_callable(
    DateField, DateField, IntegerField, [DateField], date_range)
cl_dow = make_function_asp_callable(DateField, ConstantField, dow)


#------------------------------------------------------------------------------
# Generate some wrapper functions
#------------------------------------------------------------------------------

