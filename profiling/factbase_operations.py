#!/usr/bin/env python

#------------------------------------------------------------------------------
# Instantiating a FactBase with lots of elements
#------------------------------------------------------------------------------

from clorm import Predicate, ComplexTerm, ConstantField, IntegerField, FactBase, ph1_
from clingo import Function,Number

import cProfile
import pstats
from pstats import SortKey
#------------------------------------------------------------------------------
# A simple data model
#------------------------------------------------------------------------------

class P(Predicate):
    a=IntegerField
    b=ConstantField

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def create_p_list():
    tmp=[]
    for a in range(1,500000): tmp.append(P(a,"blah"))
    return tmp

def make_fb(p_list):
    return FactBase(p_list)

def query_fb(fb,n):
    return list(fb.select(P).where(P.a == ph1_).get(n))

def make_indexed_fb(p_list):
    return FactBase(p_list,indexes=[P.a])

def main():
    p_list = create_p_list()
    pr1=cProfile.Profile()
    pr1.enable()
    fb = make_fb(p_list)
    tmp1=query_fb(fb,10000)
    pr1.disable()

    pr2=cProfile.Profile()
    pr2.enable()
    fb=make_indexed_fb(p_list)
    tmp2=query_fb(fb,10000)
    pr2.disable()

    print("\n=====================================================")
    print("Creating and querying a non-indexed FactBase\n")
    ps = pstats.Stats(pr1)
    ps.strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats('fb_add',10)
    ps.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE).print_stats('orm',10)
    ps.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE).print_stats('oset',10)

    print("\n=====================================================")
    print("Creating and querying an indexed FactBase\n")
    ps = pstats.Stats(pr2)
    ps.strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats('fb_add',10)
    ps.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE).print_stats('orm',10)
    ps.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE).print_stats('oset',10)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

