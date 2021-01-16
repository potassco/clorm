# -----------------------------------------------------------------------------
# Some generic iterator and functional functions
# ------------------------------------------------------------------------------

import functools
import itertools

__all__ = [
    'all_equal'
]


# ------------------------------------------------------------------------------
# check that all the elements of a list are equal
# ------------------------------------------------------------------------------
def all_equal(iterable):
    g = itertools.groupby(iterable)
    return next(g, True) and not next(g,False)


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
