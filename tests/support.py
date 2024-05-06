from clorm import Predicate

# ------------------------------------------------------------------------------
# Support functions for the unit tests
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Helper function for helping to test for good error messages.
# ------------------------------------------------------------------------------
def check_errmsg(startmsg, ctx):
    msg = str(ctx.exception)
    if not msg.startswith(startmsg):
        msg = ('Error message "{}" does not start ' 'with "{}"').format(msg, startmsg)
        raise AssertionError(msg)


def check_errmsg_contains(contmsg, ctx):
    msg = str(ctx.exception)
    if contmsg not in msg:
        msg = ('Error message "{}" does not contain ' '"{}"').format(msg, contmsg)
        raise AssertionError(msg)


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


def to_tuple(value):
    """Recursively convert a predicate/normal tuple into a Python tuple"""
    if isinstance(value, tuple) or (isinstance(value, Predicate) and value.meta.is_tuple):
        return tuple(to_tuple(x) for x in value)
    return value


# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------
import clingo

if clingo.__version__ >= "5.5.0":
    from clingo.ast import parse_string

    def add_program_string(ctrl, prgstr):
        with clingo.ast.ProgramBuilder(ctrl) as pb:
            parse_string(prgstr, pb.add)

else:
    from clingo import parse_program

    def add_program_string(ctrl, prgstr):
        with ctrl.builder() as pb:
            parse_program(prgstr, lambda stm: pb.add(stm))


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
