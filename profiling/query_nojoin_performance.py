#!/usr/bin/env python

#------------------------------------------------------------------------------
# Instantiating a FactBase with lots of elements
#------------------------------------------------------------------------------

from clorm import Predicate, ComplexTerm, ConstantField, IntegerField, FactBase
import clorm
from clingo import Function,Number

import time
import cProfile
import pstats
from pstats import SortKey

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

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
        print("\n".ljust(justified+10,'='))
        print("{}".format(self._msg))
        if not self._calls:
            print(" -------- No functions profiled -----------\n")
            return
        total=0.0
        for msg,cputime in self._calls:
            print("{}: {:.3f}".format(msg.ljust(justified),cputime))
            total += cputime
        print("{}: {:.3f}".format("Total time".ljust(justified),total))


#------------------------------------------------------------------------------
# A data model
#------------------------------------------------------------------------------

class P(Predicate):
    anum=IntegerField
    atuple=(IntegerField,ConstantField)

class Q(Predicate):
    anum=IntegerField
    ap=P.Field


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

def create_facts(num):
    return [Q(a,P(a,(a,"blah"))) for a in range(0,num)]

def run_select(s):
    if clorm.__version__ >= "2.0.0":
        print("{}\n".format(s.query_plan()))
        return s.run().count()
    else:
        return s.count()

def query_conj(fb):
    s=fb.select(Q).where((Q.ap.atuple[0] < 1000) & (Q.anum == 1000))
    run_select(s)

def query_disj(fb):
    s=fb.select(Q).where((Q.anum == 2000) | (Q.anum == 1000))
    run_select(s)


g_facts=None

def run_fact_querying(num):
    global g_facts
    def go():
        global g_facts
        g_facts = create_facts(num)
    pr=Profiler("Timing for fact creation and querying")
    msg1 = "Intstantiating {} new fact instances".format(num)
    pr(msg1, go)
    fb1 = pr("Adding facts to non-indexed FactBase", lambda : FactBase(g_facts))
    fb2 = pr("Adding facts to indexed FactBase",
             lambda : FactBase(g_facts,indexes=[Q.anum,Q.ap.atuple[0]]))
    c1 = pr("Conjunctive query non-indexed FactBase", lambda : query_conj(fb1))
    c2 = pr("Conjunctive Query indexed FactBase", lambda : query_conj(fb2))
    c1 = pr("Disjunctive query non-indexed FactBase", lambda : query_disj(fb1))
    c2 = pr("Disjunctive Query indexed FactBase", lambda : query_disj(fb2))
    return pr


def main():
    print("\nProfiling Querying FactBase")

    # Profile the non-index and index fact bases
#    pr1 = run_fact_querying(50000)
    pr1 = run_fact_querying(500000)
    justified=0
    pr1.print_stats(justified=justified)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

