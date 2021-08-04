#-----------------------------------------------------------------------------
# Monkey patching of clingo for the clorm library
# ------------------------------------------------------------------------------

import sys
import clingo as original_clingo
from . import clingo as clorm_clingo

original_control = original_clingo.Control

#------------------------------------------------------------------------------
# clingo patching and unpatching
#------------------------------------------------------------------------------

def patch():
    """Patch clingo to add interface for Clorm objects.

    This patch replaces clingo.Control with
    clorm.clingo.Control. clorm.clingo.Control wraps the clingo.Control
    functions to add interfaces for Clorm fact and factbase objects. On solving
    it returns clorm.clingo.Model or clorm.clingo.SolveHandle object (as
    necessary).
    """
    original_clingo.Control=clorm_clingo.Control


def unpatch():
    """Reverse the patching of clingo."""
    original_clingo.Control=original_control

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')

