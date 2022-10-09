#!/usr/bin/env python

# ------------------------------------------------------------------------------
# The following provides some simple timing tests to compare the performance of
# Clorm facts and factbases vs using raw Clingo symbols. Clorm is around an
# order of magnitude slower when instantiating facts. This may not be an issue
# for many/most situations when dealing with models containing 100s of facts of
# interest. But if you want to deal with 10,000 or 100,000 facts then you will
# have to think carefully about the trade-off between the Clorm abstraction and
# raw symbols.
# -----------------------------------------------------------------------------


import time

from clingo import Function, Number

from clorm import FactBase, IntegerField, Predicate, ph1_

# --------------------------------------------------------------------------
# Define a context timer (https://preshing.com/20110924/timing-your-code-using-pythons-with-statement/)
# --------------------------------------------------------------------------


class Timer:
    def __init__(self):
        self.interval = 0.0

    def __enter__(self):
        self.start = time.process_time()
        return self

    def __exit__(self, *args):
        self.end = time.process_time()
        self.interval = self.end - self.start

    def __str__(self):
        return "{:3f} sec".format(self.interval)


# --------------------------------------------------------------------------
# Define a data model - we only care about defining the input and output
# predicates.
# --------------------------------------------------------------------------


class PT(Predicate):
    a = IntegerField
    b = IntegerField(index=True)


#    b=IntegerField


class P(Predicate):
    i = (IntegerField, (IntegerField, (IntegerField, PT.Field)))


class PTS(object):
    def __init__(self, a, b):
        self._a = a
        self._b = b


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------
def print_comparison(clorm_timer, clingo_timer):
    clorm_t = clorm_timer.interval
    clingo_t = clingo_timer.interval
    if clorm_t < clingo_t:
        print("Clorm is {} times faster".format(clingo_t / clorm_t))
    else:
        print("Clorm is {} times slower".format(clorm_t / clingo_t))


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------
def generate_list(create_single):
    a_range = 400
    b_range = 400

    generator_t = Timer()
    with generator_t:
        items = []
        for a in range(1, a_range + 1):
            for b in range(1, b_range + 1):
                items.append(create_single(a, b))

    return (items, generator_t)


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------


def create_simple_symbol(a, b):
    return Function("pt", [Number(a), Number(b)])


def create_simple_fact_named(a, b):
    return PT(a=a, b=b)


def create_simple_fact_positional(a, b):
    return PT(a, b)


def create_pts_named(a, b):
    return PTS(a=a, b=b)


def create_pts_positional(a, b):
    return PTS(a, b)


def create_complex_symbol(a, b):
    return Function(
        "p",
        [
            Function(
                "",
                [
                    Number(1),
                    Function(
                        "",
                        [
                            Number(1),
                            Function("", [Number(1), Function("pt", [Number(a), Number(b)])]),
                        ],
                    ),
                ],
            )
        ],
    )


def create_complex_fact(a, b):
    return P(i=(1, (1, (1, PT(a=a, b=b)))))


# --------------------------------------------------------------------------
# Compare the time to generate a set of P instances vs the time taken to
# generate equivalent pure clingo symbols.
# --------------------------------------------------------------------------
def compare_generating_simple_facts_and_symbols():

    print("=============================================================")
    print(
        (
            "Comparing the generation of simple facts (named and positional args) "
            "vs raw clingo symbols vs a lower-bound of a simple Python object\n"
        )
    )

    # Time to generate clingo symbols
    (ssymbols, ssymbols_t) = generate_list(create_simple_symbol)
    print("Instantating {} simple Clingo symbols in {}".format(len(ssymbols), ssymbols_t))

    # Time to generate P facts
    (snfacts, snfacts_t) = generate_list(create_simple_fact_named)
    print("Instantating {} simple named Clorm facts in {}".format(len(snfacts), snfacts_t))

    (spfacts, spfacts_t) = generate_list(create_simple_fact_positional)
    print("Instantating {} simple positional Clorm facts in {}".format(len(spfacts), spfacts_t))

    # Time to generate basic python object
    (nobjects, nobjects_t) = generate_list(create_pts_named)
    print("Instantating {} basic named python objects in {}".format(len(nobjects), nobjects_t))

    # Time to generate basic python object
    (pobjects, pobjects_t) = generate_list(create_pts_positional)
    print(
        "Instantating {} basic positional python objects in {}".format(len(pobjects), pobjects_t)
    )

    #    assert ssymbols == [ f.raw for f in snfacts ]
    print("--------------------------")
    print("Clorm named vs Clingo:")
    print_comparison(snfacts_t, ssymbols_t)
    print("--------------------------")
    print("Clorm positional vs Clingo:")
    print_comparison(spfacts_t, ssymbols_t)
    print("--------------------------")
    print("Clorm named vs Python named:")
    print_comparison(snfacts_t, nobjects_t)
    print("--------------------------")
    print("Clorm positional vs Python positional:")
    print_comparison(spfacts_t, pobjects_t)
    print("--------------------------")
    print("Clorm named vs Clorm positional:")
    print_comparison(snfacts_t, spfacts_t)
    print("--------------------------")
    print("--------------------------------------------------------\n")


# --------------------------------------------------------------------------
# Compare the time to generate a set of P instances vs the time taken to
# generate equivalent pure clingo symbols.
# --------------------------------------------------------------------------
def compare_generating_complex_facts_and_symbols():

    print("=========================================================")
    print("Comparing the generation of complex facts vs raw clingo symbols\n")

    # Time to generate P facts
    (cfacts, cfacts_t) = generate_list(create_complex_fact)
    print("Instantating complex {} Clorm facts in {}".format(len(cfacts), cfacts_t))

    # Time to generate clingo symbols
    (csymbols, csymbols_t) = generate_list(create_complex_symbol)
    print("Instantating complex {} Clingo symbols in {}".format(len(csymbols), csymbols_t))

    assert csymbols == [f.raw for f in cfacts]
    print_comparison(cfacts_t, csymbols_t)
    print("--------------------------------------------------------\n")


# --------------------------------------------------------------------------
# Time to instantiate facts from raw symbols
# --------------------------------------------------------------------------
def time_to_instantiate_simple_from_raw():
    print("=========================================================")
    print("Comparing time to instantiate simple facts from a raw symbol\n")

    (symbols, symbols_t) = generate_list(create_simple_symbol)

    with Timer() as unify_timer:
        foall = [PT._unify(s) for s in symbols]
    print("Unifying {} simple symbols to a list of facts: {}".format(len(symbols), unify_timer))
    print("--------------------------------------------------------\n")


def time_to_instantiate_complex_from_raw():
    print("========================================================")
    print("Comparing time to instantiate complex facts from a raw symbol\n")

    (symbols, symbols_t) = generate_list(create_complex_symbol)

    with Timer() as unify_timer:
        foall = [P._unify(s) for s in symbols]
    print("Unifying {} complex_symbols to a list of facts: {}".format(len(symbols), unify_timer))
    print("--------------------------------------------------------\n")


# --------------------------------------------------------------------------
# Compare query times to access components of individual facts
# --------------------------------------------------------------------------
def compare_query_times():
    print("=========================================================")
    print(
        (
            "Comparing query times for different combinations of fact base vs "
            "search through raw clingo symbols\n"
        )
    )

    # Build a list of complex facts and corresponding symbols
    (facts, facts_t) = generate_list(create_complex_fact)
    symbols = [f.raw for f in facts]

    # Test time to import into a factbase with indexing
    with Timer() as fb_import_timer:
        fb = FactBase(indexes=P.meta.indexes, facts=facts)
    print("Importing {} facts to factbase: {}".format(len(fb), fb_import_timer))

    # Query
    q = 10
    # Test the time needed to do the search on the raw symbols
    with Timer() as fb_raw_search:
        r = []
        for s in symbols:
            if s.arguments[0].arguments[1].arguments[1].arguments[1].arguments[0].number <= q:
                r.append(s)
    print("Raw Symbol search: {} => {}".format(len(r), fb_raw_search))

    # Now time the FactBase query results
    q_a_posn_c = fb.query(P).where(P[0][1][1][1][0] <= ph1_)
    q_a_name_c = fb.query(P).where(P.i.arg2.arg2.arg2.a <= ph1_)
    q_b_name_c = fb.query(P).where(P.i.arg2.arg2.arg2.b <= ph1_)
    q_a_posn_l = fb.query(P).where(lambda f, a: f[0][1][1][1][0] <= a)
    q_a_name_l = fb.query(P).where(lambda f, a: f.i.arg2.arg2.arg2.a <= a)

    with Timer() as t1:
        r = list(q_a_posn_c.bind(q).all())
    print("Clorm syntax positional arguments : {} => {}".format(len(r), t1))

    with Timer() as t2:
        r = list(q_a_name_c.bind(q).all())
    print("Clorm syntax named arguments: {} => {}".format(len(r), t2))

    with Timer() as t3:
        r = list(q_b_name_c.bind(q).all())
    print("Clorm syntax, indexed, named arguments: {} => {}".format(len(r), t3))

    with Timer() as t4:
        r = list(q_a_posn_l.bind(a=q).all())
    print("Lambda positional arguments: {} => {}".format(len(r), t4))

    with Timer() as t5:
        r = list(q_a_posn_c.bind(q).all())
    print("Lambda named arguments: {} => {}".format(len(r), t5))
    # Access
    print("--------------------------------------------------------\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():

    compare_generating_simple_facts_and_symbols()
    compare_generating_complex_facts_and_symbols()
    time_to_instantiate_simple_from_raw()
    time_to_instantiate_complex_from_raw()
    compare_query_times()


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
