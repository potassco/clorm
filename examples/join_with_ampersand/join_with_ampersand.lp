%----------------------------------------------------------------------------------
% Domain encoding for a simple scheduling problem. Drivers need to make
% deliveries.  Every driver has a fixed base cost and every delivery has a
% cost. We also need deliveries within a time limit.
% ----------------------------------------------------------------------------------


time(1..4).

1 { assignment(I, D, T) : driver(D,_), time(T) } 1 :- item(I,_).
:- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

working_driver(D) :- assignment(_,D,_).

#minimize { 1@2,D : working_driver(D) }.
#minimize { T@1,D : assignment(_,D,T) }.


#script(python)

from clorm.clingo import Control
from clorm import Predicate, ConstantStr, FactBase
from clorm import ph1_


#--------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
#--------------------------------------------------------------------------

class Driver(Predicate):
    driverid: ConstantStr
    name: str

class Item(Predicate):
    itemid: ConstantStr
    description: str

class Assignment(Predicate):
    itemid: ConstantStr
    driverid: ConstantStr
    time: int

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

def main(ctrl_):
    # For better integration with Clorm wrap the clingo.Control object with a
    # clorm.clingo.Control object and pass the unifier list of predicates that
    # are used to unify the symbols and predicates.
    ctrl = Control(control_=ctrl_, unifier=[Driver,Item,Assignment])

    # Dynamically generate the instance data
    drivers = [
        Driver(driverid="dave", name="Dave X"),
        Driver(driverid="morri", name="Morri Y"),
        Driver(driverid="michael", name="Michael Z"),
    ]

    items = [ Item(itemid=f"item{i}", description=f"Item {i}") for i in range(1,6) ]
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
    query=solution.query(Driver, Item, Assignment)\
                  .join((Driver.driverid == Assignment.driverid) &
                        (Item.itemid == Assignment.itemid))\
                  .group_by(Driver.name)\
                  .order_by(Assignment.time)\
                  .select(Item.description, Assignment.time)
    for dname, assiter in query.all():
        print(f"Driver: {dname}:")
        for idesc, atime in assiter:
            print(f"    {atime}: {idesc}")
#end.
