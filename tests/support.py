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
