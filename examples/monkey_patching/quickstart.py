#!/usr/bin/env python

# --------------------------------------------------------------------------
# Clorm can "monkey patch" the official clingo library. This will replace the
# clingo.Control class with clorm.clingo.Control.
# --------------------------------------------------------------------------

from clorm import monkey

monkey.patch()  # must call this before importing clingo

from clingo import Control  # Import clingo.Control instead of clorm.clingo.Control

from clorm import ConstantField, FactBase, IntegerField, Predicate

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

    #    query=solution.select(Assignment).where(lambda x,o: x.driver == o)
    query = (
        solution.query(Driver, Assignment)
        .join(Driver.name == Assignment.driver)
        .group_by(Driver.name)
        .order_by(Assignment.time)
        .select(Assignment)
    )
    for d, aiter in query.all():
        assignments = list(aiter)
        if not assignments:
            print("Driver {} is not working today".format(d))
        else:
            print("Driver {} must deliver: ".format(d))
            for a in assignments:
                print("\t Item {} at time {}".format(a.item, a.time))


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
