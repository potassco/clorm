"""Enable NOCLINGO.

NOTE: This currently doesn't work so still have noclingo enabled.
"""

NOCLINGO_INITIALISED = False
ENABLE_NOCLINGO = True

def enable_noclingo():
    """A feature-enabling function that must be called before clorm is loaded.

    This function should only be called once and should be called before any of
    the main clorm modules are loaded.  It allows the `clorm.set_clingo_mode()`
    function to be used to switch between clorm's NOCLINGO and CLINGO modes.

    NOCLINGO is a mechanism to allow clorm to be used with long running
    processes. When `clingo.Symbol` objects are created they cannot be
    destroyed and will persist until the process ends. This works fine for many
    applications, where the process is short-lived; for example running the
    solver to find a solution and present it to the user. However, for long
    running processes, such as a server, not being able to free `clingo.Symbol`
    objects can be a problem if many new objects are being created.

    Clorm solves this problem by allow for a special mode where creating clorm
    facts will internally produce `clorm.NoSymbol` object rather than a
    `clingo.Symbol` object. These objects behave the same as `clingo.Symbol`
    objects except, of course, that they cannot be passed to the solver.

    The idea is that a long-running process would run in NOCLINGO mode, while
    the solver would be run in spawned sub-processes that are relatively
    short-lived. The sub-processes would operating in "normal" CLINGO mode. Any
    `clingo.Symbol` data that need to be communicated back to the main process
    can be converted to `clorm.NoSymbol` objects, which are then serialised and
    sent to the main process. If clorm fact objects are serialized this
    conversion process happens transparently to the user.

    Enabling NOCLINGO mode has a small performance overhead, but since many
    use-cases have no need for NOCLINGO it must be enabled explicitly.

    """
    global NOCLINGO_INITIALISED, ENABLE_NOCLINGO

    if NOCLINGO_INITIALISED and not ENABLE_NOCLINGO:
        raise RuntimeError(("enable_noclingo() must be called before the main clorm "
                            "modules have been loaded."))
    ENABLE_NOCLINGO = True

# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------


if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
