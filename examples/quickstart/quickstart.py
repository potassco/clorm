#!/usr/bin/env python

from clorm import monkey

monkey.patch()  # must call this before importing clingo

from clorm import Predicate, ConstantField, IntegerField, FactBase
from clorm import ph1_

from clingo import Control


ASP_PROGRAM = "quickstart.lp"

# --------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
# --------------------------------------------------------------------------


class Driver(Predicate):
    name = ConstantField


class Item(Predicate):
    name = ConstantField


class Assignment(Predicate):
    item = ConstantField
    driver = ConstantField
    time = IntegerField


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------


def main():
    # Create a Control object that will unify models against the appropriate
    # predicates. Then load the asp file that encodes the problem domain.
    ctrl = Control(unifier=[Driver, Item, Assignment])
    ctrl.load(ASP_PROGRAM)

    # Dynamically generate the instance data
    drivers = [Driver(name=n) for n in ["dave", "morri", "michael"]]
    items = [Item(name="item{}".format(i)) for i in range(1, 6)]
    instance = FactBase(drivers + items)

    # Add the instance data and ground the ASP program
    ctrl.add_facts(instance)
    ctrl.ground([("base", [])])

    # Generate a solution - use a call back that saves the solution
    solution = None

    def on_model(model):
        nonlocal solution
        solution = model.facts(atoms=True)

    ctrl.solve(on_model=on_model)
    if not solution:
        raise ValueError("No solution found")

    # Do something with the solution - create a query so we can print out the
    # assignments for each driver.
    query = solution.query(Assignment).where(Assignment.driver == ph1_).order_by(Assignment.time)

    for d in drivers:
        assignments = list(query.bind(d.name).all())
        if not assignments:
            print("Driver {} is not working today".format(d.name))
        else:
            print("Driver {} must deliver: ".format(d.name))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
