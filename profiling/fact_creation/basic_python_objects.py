#!/usr/bin/env python

#------------------------------------------------------------------------------
# Compare different encodings of objects to see if there are any performance
# differences.
# -----------------------------------------------------------------------------

#--------------------------------------------------------------------------
# Define a context timer (https://preshing.com/20110924/timing-your-code-using-pythons-with-statement/)
#--------------------------------------------------------------------------

import time

class Timer:
    def __init__(self,name):
        self.name=name
        self.interval = 0.0

    def __enter__(self):
        self.start = time.process_time()
        return self

    def __exit__(self, *args):
        self.end = time.process_time()
        self.interval = self.end - self.start

    def __str__(self):
        return "{:3f} sec".format(self.interval)

#--------------------------------------------------------------------------
#--------------------------------------------------------------------------

class P1(object):
    def __init__(self,a,b):
        self._a = a
        self._b = b

class P2(object):
    def __init__(self,a,b):
        setattr(self,"_a",a)
        setattr(self,"_b",b)

class P3(object):
    def __init__(self,a,b):
        self._ab = (a,b)

class P4(object):
    def __init__(self,a,b):
        self._ab = [a,b]

class PS1(object):
    __slots__ = ('_a','_b')

    def __init__(self,a,b):
        self._a = a
        self._b = b

class PS3(object):
    __slots__ = ('_ab')

    def __init__(self,a,b):
        self._ab = (a,b)



# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------
def print_comparison(timer_a, timer_b):
    t_a = timer_a.interval
    t_b = timer_b.interval
    if t_a < t_b:
        print("{} is {} times faster than {}".format(
            timer_a.name,t_b/t_a,timer_b.name))
    else:
        print("{} is {} times slower than {}".format(
            timer_a.name,t_a/t_b,timer_b.name))


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------
def generate_list(name, create_single):
    a_range = 1000
    b_range = 1000

    generator_t = Timer(name)
    with generator_t:
        items = []
        for a in range(1,a_range+1):
            for b in range(1,b_range+1):
                items.append(create_single(a,b))

    return (items,generator_t)

# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------

def create_p1(a,b): return P1(a,b)
def create_p2(a,b): return P2(a,b)
def create_p3(a,b): return P3(a,b)
def create_p4(a,b): return P4(a,b)
def create_ps1(a,b): return PS1(a,b)
def create_ps3(a,b): return PS3(a,b)

# --------------------------------------------------------------------------
# Compare the time to generate a set of python objects
# --------------------------------------------------------------------------
def compare_generating_simple_objects():

    print("=============================================================")
    print("Comparing the generation of simple python object")

    # Time to generate Python P1 object
    (p1s,p1t) = generate_list("P1", create_p1)
    print("Instantating {} Python {} objects in {}".format(len(p1s), p1t.name, p1t))

    # Time to generate Python PS1 (P1 with slots) object
    (ps1s,ps1t) = generate_list("PS1", create_ps1)
    print("Instantating {} Python {} objects in {}".format(len(ps1s), ps1t.name, ps1t))

    # Time to generate Python P2 object
    (p2s,p2t) = generate_list("P2", create_p2)
    print("Instantating {} Python {} objects in {}".format(len(p2s), p2t.name, p2t))

    # Time to generate Python P1 object
    (p3s,p3t) = generate_list("P3", create_p3)
    print("Instantating {} Python {} objects in {}".format(len(p3s), p3t.name, p3t))

    # Time to generate Python PS3 (P1 with slots) object
    (ps3s,ps3t) = generate_list("PS3", create_ps3)
    print("Instantating {} Python {} objects in {}".format(len(ps3s), ps3t.name, ps3t))

    # Time to generate Python P4 object
    (p4s,p4t) = generate_list("P4", create_p4)
    print("Instantating {} Python {} objects in {}".format(len(p4s), p4t.name, p4t))

    

    print("--------------------------------------------------------\n")


#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------
def main():
    compare_generating_simple_objects()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

