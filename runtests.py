#!/usr/bin/env python

import optparse
import os
import shutil
import sys
import unittest

USER = os.environ.get('USER') or 'root'


def runtests(suite, verbosity=1, failfast=False):
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    results = runner.run(suite)
    return results.failures, results.errors

def get_option_parser():
    usage = 'usage: %prog module1, module2 ...'
    parser = optparse.OptionParser(usage=usage)
    basic = optparse.OptionGroup(parser, 'Basic test options')
    basic.add_option('-v', '--verbosity', dest='verbosity', default=1,
                     type='int', help='Verbosity of output')
    basic.add_option('-f', '--failfast', action='store_true', default=False,
                     dest='failfast', help='Exit on first failure/error.')
    parser.add_option_group(basic)
    return parser

def collect_tests(args):
    suite = unittest.TestSuite()

    if not args:
        import tests
        module_suite = unittest.TestLoader().loadTestsFromModule(tests)
        suite.addTest(module_suite)
    else:
        cleaned = ['tests.%s' % arg if not arg.startswith('tests.') else arg
                   for arg in args]
        user_suite = unittest.TestLoader().loadTestsFromNames(cleaned)
        suite.addTest(user_suite)

    return suite

if __name__ == '__main__':
    parser = get_option_parser()
    options, args = parser.parse_args()

    suite = collect_tests(args)
    failures, errors = runtests(suite, options.verbosity, options.failfast)

    if errors:
        sys.exit(2)
    elif failures:
        sys.exit(1)

    sys.exit(0)
