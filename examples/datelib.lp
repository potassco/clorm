%----------------------------------------------------------------------------------
% Use the clorm date library to define an enumerated date range and assign a
% resource to dates while the first and last date must have more resources then
% the middle dates.
% ----------------------------------------------------------------------------------

#script(python).
import datetime
from clorm import IntegerField, Predicate, FactBase, FactBaseHelper, ph1_
from clorm.clingo import Control
from clorm.lib.date import EnumDate, EnumDateRange

fbh=FactBaseHelper()

@fbh.register
class Assignment(Predicate):
    res = IntegerField()
    ed = EnumDate.Field()

AppDB = fbh.create_class("AppDB")

dr = EnumDateRange(start=datetime.date.today(), count=5)
enumdate_range=dr.cl_enumdate_range
first=dr.cl_first
last=dr.cl_last

#end.

date(@enumdate_range()).
resource(1..10).

1 { assignment(R,D) : date(D) } 1  :- resource(R).

resource_count(D, C) :- C = #count{ R : assignment(R,D)}, date(D).

middle_date(D) :- date(D), D < @last(), D > @first().
end_date(D) :- date(D), not middle_date(D).

% end dates must be assigned fewer resources than middle dates
:- end_date(D1), middle_date(D2), resource_count(D1,C1), resource_count(D2,C2), C1 >= C2.

% the difference between resource assignments must be <= 2.
:- resource_count(D1,C1), resource_count(D2,C2), C1-C2 > 2.

#show.

#script(python).

def on_model(model):
    solution = model.facts(AppDB, atoms=True, raise_on_empty=True)
    q1 = solution.select(Assignment).where(Assignment.ed == ph1_)

    for ed in dr.enumdate_range():
        print("{} => {}".format(ed.date, [a.res for a in q1.get(ed)]))


def main(ctrl_):
    ctrl = Control(control_=ctrl_)
    ctrl.ground([("base",[])])
    ctrl.solve(on_model=on_model)

#end.
