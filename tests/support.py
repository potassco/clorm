#------------------------------------------------------------------------------
# Support functions for the unit tests
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Helper function for helping to test for good error messages.
#------------------------------------------------------------------------------
def check_errmsg(startmsg, ctx):
    msg=str(ctx.exception)
    if not msg.startswith(startmsg):
        msg = ("Error message \"{}\" does not start "
               "with \"{}\"").format(msg,startmsg)
        raise AssertionError(msg)


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
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

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
