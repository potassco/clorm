#!/usr/bin/env bash

#------------------------------------------------------------------------
# Running all unit tests in the test directory

#python -m unittest discover -p test

#------------------------------------------------------------------------
# Running individual unit tests

python -m unittest tests.test_orm
#python -m unittest test.test_process_model
