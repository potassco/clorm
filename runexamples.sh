#!/usr/bin/env bash

#--------------------------------------------------------------------------------------
# Run the examples in the examples sub-directory and report if there is an error
#--------------------------------------------------------------------------------------

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source ${THIS_DIR}/examples/local.sh


VERBOSE="No"

#--------------------------------------------------------------------------------------
# Run a clingo program. Note: Clingo seems to return a return code of either 30
# or 10 (rather than 0) even though it appears to finish without an error. I'm
# not sure why.
# --------------------------------------------------------------------------------------

run_clingo(){
    local asp=$1
    local dir=$( dirname $asp )
    local base=$( basename $asp )

    echo "======================================================================="
    echo "Running clingo program: {$asp}"
    result=$( cd $dir ; clingo $base )
    status=$?

    if [ "$status" != "30" ] && [ "$status" != "10" ] ; then
	echo ""
	echo "Error $status running: {$asp}"
	echo ""
	echo "$result"
	echo "======================================================================="
	return 1
    fi
    if [ "$VERBOSE" == "Yes" ] ; then
	echo "$result"
    fi
    echo "======================================================================="
    return 0
}

#--------------------------------------------------------------------------------------
# Run a python
#--------------------------------------------------------------------------------------

run_python(){
    local prg=$1
    local dir=$( dirname $prg )
    local base=$( basename $prg )

    echo "======================================================================="
    echo "Running Python clingo program: {$prg}"
    result=$( cd $dir ; python $base )
    status=$?

    if [ "$status" != "0" ] ; then
	echo ""
	echo "Error $status running: {$prg}"
	echo ""
	echo "$result"
	echo "======================================================================="
	return 1
    fi
    if [ "$VERBOSE" == "Yes" ] ; then
	echo "$result"
    fi
    echo "======================================================================="
    return 0
}

#--------------------------------------------------------------------------------------
#
#--------------------------------------------------------------------------------------

run_clingo examples/debugging/simple_predicate.lp

run_clingo examples/grounding_context/embedded_grounding_context.lp

run_python examples/introspection/introspection.py

run_python examples/monkey_patching/quickstart.py

run_clingo examples/quickstart/embedded_quickstart.lp
run_python examples/quickstart/quickstart.py

#run_python examples/performance_tests/performance_comparison.py
