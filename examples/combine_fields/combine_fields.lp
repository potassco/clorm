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
from enum import Enum
from clorm import Predicate, ConstantStr, combine_fields
from clorm import ph1_
from typing import Union

#--------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
#--------------------------------------------------------------------------

class Status(ConstantStr, Enum):
    ON="on"
    OFF="off"

class Time(Predicate):
    time: int

class Light(Predicate):
    status: Status

class RobotLocation(Predicate, name="robotlocation"):
    robot: ConstantStr
    location: ConstantStr

#FluentField=combine_fields([Light.Field,RobotLocation.Field])

class Init(Predicate):
    fluent: Union[Light, RobotLocation]

class Holds(Predicate):
    fluent: Union[Light, RobotLocation]
    time: int

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

def main(ctrl_):
    ctrl = Control(control_=ctrl_, unifier=[Time,Holds])

    # Some initial state
    initstate=[Init(Light(Status.ON)),Init(RobotLocation("roby","kitchen"))]

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
    query=solution.query(Time,Holds).join(Time.time == Holds.time)\
                                    .group_by(Time.time).select(Holds.fluent)
    for t,fiter in query.all():
        print("Time: {}".format(t))
        for f in fiter:
            if isinstance(f,Light): print("\tLight is: {}".format(f.status))
            elif isinstance(f,RobotLocation): print("\tRobot {} is at {}".format(f.robot,f.location))
#end.
