%----------------------------------------------------------------------------------
% Meaningless example but to show the use of combine_fields for dealing with
% things like fluents.
% ----------------------------------------------------------------------------------

time(0..2).

holds(light(off),T+1) :- time(T+1), holds(light(on),T).
holds(light(on),T+1) :- time(T+1), holds(light(off),T).

holds(robotlocation(R,livingroom),T+1) :- time(T+1), holds(robotlocation(R,kitchen),T).
holds(robotlocation(R,study),T+1) :- time(T+1), holds(robotlocation(R,livingroom),T).
holds(robotlocation(R,kitchen),T+1) :- time(T+1), holds(robotlocation(R,study),T).

holds(F,0) :- init(F).

#script(python)

from clorm.clingo import Control
from clorm import Predicate, ComplexTerm, ConstantField, IntegerField, combine_fields
from clorm import ph1_


#--------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
#--------------------------------------------------------------------------

class Time(Predicate):
    time=IntegerField

class Light(ComplexTerm):
    status=ConstantField

class RobotLocation(ComplexTerm):
    robot=ConstantField
    location=ConstantField
    class Meta: name = "robotlocation"

FluentField=combine_fields("FluentField",[Light.Field,RobotLocation.Field])

class Init(Predicate):
    fluent=FluentField

class Holds(Predicate):
    fluent=FluentField
    time=IntegerField

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

def main(ctrl_):
    ctrl = Control(control_=ctrl_, unifier=[Time,Holds])

    # Some initial state
    initstate=[Init(Light("on")),Init(RobotLocation("roby","kitchen"))]

    # Add the initial state and ground the ASP program and solve
    solution=None
    ctrl.add_facts(initstate)
    ctrl.ground([("base",[])])

    with ctrl.solve(yield_=True) as sh:
        for m in sh:
            solution=m.facts(atoms=True)
    if not solution:
        raise ValueError("No solution found")

    # Query the solution
    fquery = solution.select(Holds).where(Holds.time == ph1_)
    for t in solution.select(Time).order_by(Time.time).get():
        print("Time: {}".format(t.time))
        for h in fquery.get(t.time):
            f = h.fluent
            if isinstance(f,Light): print("\tLight is: {}".format(f.status))
            elif isinstance(f,RobotLocation): print("\tRobot {} is at {}".format(f.robot,f.location))
#end.
