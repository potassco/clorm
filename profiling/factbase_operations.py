#!/usr/bin/env python

#------------------------------------------------------------------------------
# Instantiating a FactBase with lots of elements
#------------------------------------------------------------------------------

from clorm import Predicate, ComplexTerm, ConstantField, IntegerField, FactBase, ph1_
from clingo import Function,Number

from clorm import _FactSet

import time
import cProfile
import pstats
from pstats import SortKey

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def runcall_wrapper(func,*args,**kwargs):
    pr=cProfile.Profile()
    pr.enable()
    res=func(*args,**kwargs)
    pr.disable()
    return res,pr


class Profiler(object):
    def __init__(self,msg):
        self._msg=msg
        self._calls=[]
        self._justified=0

    def __call__(self,msg,func,*args,**kwargs):
        self._justified=max(len(msg)+3, self._justified)
        starttime = time.process_time()
        res=func(*args,**kwargs)
        endtime = time.process_time()
        self._calls.append((msg,endtime-starttime))
        return res

    @property
    def justified(self): return self._justified

    def print_stats(self,justified=0):
        if justified < self._justified: justified = self._justified
        print("\n=====================================================")
        print("{}".format(self._msg))
        if not self._calls:
            print(" -------- No functions profiled -----------\n")
            return
        total=0.0
        for msg,cputime in self._calls:
            print("{} : {:.3f}".format(msg.ljust(justified),cputime))
            total += cputime
        print("{} : {:.3f}".format("Total time".ljust(justified),total))


def profcall(msg,func,*args,**kwargs):
    starttime = time.process_time()
#    res,pr = runcall_wrapper(func,*args,*kwargs)
    res=func(*args,**kwargs)
    endtime = time.process_time()
    print("{} : {:.3f}".format(msg.ljust(40),endtime-starttime))
    return res

#------------------------------------------------------------------------------
# A simple data model
#------------------------------------------------------------------------------

class P(Predicate):
    a=IntegerField
    b=ConstantField


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def create_p_list1():
    tmp=[]
    for a in range(1,500000): tmp.append(P(a,"blah"))
    return tmp

def create_p_list2():
    tmp=[]
    for a in range(100000,300000): tmp.append(P(a,"blah"))
    return tmp

def make_fbs(p_list1,p_list2):
    fb1=FactBase(p_list1)
    fb2=FactBase()
    fb2.add(p_list2)
    return fb2,fb2

def make_indexed_fbs(p_list1,p_list2):
    fb1=FactBase(p_list1,indexes=[P.a])
    fb2=FactBase(indexes=[P.a])
    fb2.add(p_list2)
    return fb2,fb2

def query_fb(fb,n):
    return list(fb.select(P).where(P.a == ph1_).get(n))

g_plist1 = create_p_list1()
g_plist2 = create_p_list2()

def run(indexed):
    if indexed:
        pr=Profiler("Profiling creating and querying an indexed FactBase")
        fb1,fb2 = pr("Making two fact bases", make_indexed_fbs,g_plist1,g_plist2)
    else:
        pr=Profiler("Profiling creating and querying a non-indexed FactBase")
        fb1,fb2 = pr("Making two fact bases", make_fbs,g_plist1,g_plist2)

    tmp1=pr("Querying a fact base", query_fb,fb1,10000)
    pr("Union operation",fb1.union,fb2)
    pr("Intersection operation",fb1.intersection,fb2)
    pr("Difference operation",fb1.difference,fb2)
    pr("Symmetric difference operation",fb1.symmetric_difference,fb2)

    return pr

def main():
    print("\nProfiling FactBase built on using FactSet: {}".format(_FactSet))

    # Profile the non-index and index fact bases
    pr1 = run(indexed=False)
#    pr2 = run(indexed=True)

    # Print out the profiling numbers
#    justified=max(pr1.justified,pr2.justified)
    justified=0
    pr1.print_stats(justified=justified)
#    pr2.print_stats(justified=justified)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

