#!/usr/bin/env python

from clorm import Predicate, ComplexTerm, ConstantField, IntegerField, path


class Acomplex(ComplexTerm):
    anum = IntegerField
    aconst = ConstantField(index=True)


class Apredicate(Predicate):
    anum = IntegerField(index=True)
    acmplx = Acomplex.Field
    atuple = (IntegerField, ConstantField(index=True))


# --------------------------------------------------------------------------
#
# --------------------------------------------------------------------------


def main():

    # Introspect name and arity of predicate/complex-term and is_tuple
    assert Acomplex.meta.name == "acomplex"
    assert Acomplex.meta.arity == 2
    assert Acomplex.meta.is_tuple == False

    assert Apredicate.meta.name == "apredicate"
    assert Apredicate.meta.arity == 3
    assert Apredicate.meta.is_tuple == False

    # The names of the fields
    assert set(Acomplex.meta.keys()) == set(["anum", "aconst"])
    assert set(Apredicate.meta.keys()) == set(["anum", "acmplx", "atuple"])

    # Map positional argument to field name
    assert Acomplex.meta.canonical(0) == "anum"
    assert Acomplex.meta.canonical(1) == "aconst"


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
