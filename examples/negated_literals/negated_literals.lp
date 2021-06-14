% -----------------------------------------------------------------------------
% This example shows how to use negated atoms with Clorm. The declared predicate
% class can contain an inner Meta class which specifies if it is restricted to
% unifying with only positive or negative literals (see class B_pos and B_neg
% respectively). By default it will unify with both positive and negative
% literals (see class A).
% -----------------------------------------------------------------------------

 { a(1..2); b(1..2) }.

-b(N) :- a(N).
-a(N) :- b(N).

c(-a(N)) :- -a(N).

#script(python)

from clorm import IntegerField, Predicate
from clorm.clingo import Control, Function, Number

class A(Predicate):
  n = IntegerField

class B_pos(Predicate):
  n = IntegerField
  class Meta:
    name = "b"
    sign = True

class B_neg(Predicate):
  n = IntegerField
  class Meta:
    name = "b"
    sign = False

class C(Predicate):
  a = A.Field

def on_model(model):
    print("\n==================================")
    fb = model.facts(atoms=True)

    # print all facts
    print("All: {}".format(fb))

    # query for the positive A facts
    q=fb.select(A).where(A.sign == True)
    print("Positive A: {}".format(q.get()))

    # query for the positive A facts
    q=fb.select(A).where(A.sign == False)
    print("Negative A: {}".format(q.get()))

    # query for the all B_pos facts (which must be positive)
    q=fb.select(B_pos)
    print("Positive B: {}".format(q.get()))

    # query for the C facts (which contain a )
    q=fb.select(C)
    print("C (negative terms): {}".format(q.get()))
    print("==================================\n")

def main(ctrl_):

  ctrl = Control(control_=ctrl_, unifier=[A,B_pos,B_neg,C])
  ctrl.ground([("base",[])])
  ctrl.solve(on_model=on_model)

#end.
#show.
