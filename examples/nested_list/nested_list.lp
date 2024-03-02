%----------------------------------------------------------------------------------
% Meaningless example but to show the use of ASP nested lists
% ----------------------------------------------------------------------------------

hlist(list1, (1,(2,(3,())))).
hlist(list2, (1,(2,(3,(4,()))))).

#script(python)

from clorm.clingo import Control
from clorm import Predicate, ConstantStr, HeadList

#--------------------------------------------------------------------------
# Map the list
#--------------------------------------------------------------------------

class HList(Predicate, name="hlist"):
    name: ConstantStr
    thelist: HeadList[int]

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

def main(ctrl_):
    ctrl = Control(control_=ctrl_, unifier=[HList])

    nl = HList("newlist", [4,3,2,1])
    nl.thelist[2] = 4
    # Ground the ASP program and solve
    solution=None
    ctrl.add_facts([nl])
    ctrl.ground([("base",[])])

    with ctrl.solve(yield_=True) as sh:
        for m in sh:
            solution=m.facts(atoms=True)
    if not solution:
        raise ValueError("No solution found")

    # Query the solution
    for name, thelist in solution.query(HList).all():
        print(f"{name} => {thelist}")
#end.
