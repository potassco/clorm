%----------------------------------------------------------------------------------
% Domain encoding for a simple scheduling problem. Drivers need to make
% deliveries.  Every driver has a fixed base cost and every delivery has a
% cost. We also need deliveries within a time limit.
% ----------------------------------------------------------------------------------


time(1..4).

1 { assignment(I, D, T) : driver(D), time(T) } 1 :- item(I).
:- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

working_driver(D) :- assignment(_,D,_).

#minimize { 1@2,D : working_driver(D) }.
#minimize { T@1,D : assignment(_,D,T) }.


#script(python)

from clorm.clingo import Control
from clorm import Predicate, ConstantField, IntegerField, FactBase
from clorm import ph1_


#--------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
#--------------------------------------------------------------------------

class Driver(Predicate):
    name=ConstantField

class Item(Predicate):
    name=ConstantField

class Assignment(Predicate):
    item=ConstantField
    driver=ConstantField
    time=IntegerField

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

def main(ctrl_):
    # For better integration with Clorm wrap the clingo.Control object with a
    # clorm.clingo.Control object and pass the unifier list of predicates that
    # are used to unify the symbols and predicates.
    ctrl = Control(control_=ctrl_, unifier=[Driver,Item,Assignment])

    # Dynamically generate the instance data
    drivers = [ Driver(name=n) for n in ["dave", "morri", "michael" ] ]
    items = [ Item(name="item{}".format(i)) for i in range(1,6) ]
    instance = FactBase(drivers + items)

    # Add the instance data and ground the ASP program
    ctrl.add_facts(instance)
    ctrl.ground([("base",[])])

    # Generate a solution - use a call back that saves the solution
    solution=None
    def on_model(model):
        nonlocal solution
        solution = model.facts(atoms=True)

    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")

    # Do something with the solution - create a query so we can print out the
    # assignments for each driver.
    query=solution.select(Assignment).where(Assignment.driver == ph1_).order_by(Assignment.time)
    for d in drivers:
        assignments = query.get(d.name)
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))

#end.
