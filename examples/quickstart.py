#!/usr/bin/env python
import sys,os
PARENT_DIR=os.path.abspath("..")
sys.path.insert(0,PARENT_DIR)

from clorm import monkey; monkey.patch() # must call this before importing clingo

from clorm import Predicate, ConstantField, IntegerField, FactBase, FactBaseHelper
from clorm import ph1_

from clingo import Control, parse_program

#------------------------------------------------------
# A Logic program
#------------------------------------------------------

logic_program='''
flies(X) :- bird(X), not penguin(X).
'''
#------------------------------------------------------
# The data model
#------------------------------------------------------

with FactBaseHelper() as fbh:
    class Bird(Predicate):
        name=ConstantField()

    class Penguin(Predicate):
        name=ConstantField()

    class Flies(Predicate):
        name=ConstantField()

    class AnimalFB(FactBase):
        predicates = [Bird,Penguin,Flies]
        indexes = [Flies.name]

AnimalFB = fbh.create_class("AnimalFB")

#------------------------------------------------------
#
#------------------------------------------------------

def on_model(model):
    # To show that the Model wrapper copies the original
    for a in model.symbols(atoms=True): print("ATOM: {}".format(a))
    if model.contains(Bird("tweety")): print("YES")

    print("========== MODEL: START ==============")
    fb = model.facts(AnimalFB, atoms=True)

    query=fb.select(Flies).where(Flies.name == ph1_)
    for b in fb.select(Bird).get():
        if len(list(query.get(b.name))):
            print("{} is a flying bird".format(b.name))
        else:
            print("{} is a non-flying bird".format(b.name))
    print("========== MODEL: END ==============")

#------------------------------------------------------
#
#------------------------------------------------------

def main():
    ctrl = Control()
    with ctrl.builder() as b:
        parse_program(logic_program, lambda stmt: b.add(stmt))

    f1=Bird("tweety")
    f2=Bird("tux")
    f3=Penguin("tux")
    inputs=AnimalFB([f1,f2,f3])

    ctrl.add_facts(inputs)
    ctrl.ground([("base",[])])
    ctrl.solve(on_model=on_model)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()


