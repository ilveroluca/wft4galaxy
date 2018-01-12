from __future__ import print_function

import os as _os
import sys as _sys
import argparse as _argparse
import logging as _logging

import wft4galaxy.core as _core
import wft4galaxy.common as _common
from wft4galaxy.core import OutputFormat

# set logger
_logger = _common.LoggerManager.get_logger(__name__)


class _CustomFormatter(_argparse.RawTextHelpFormatter):
    """ Customize settings of the default RawTextHelpFormatter """

    def __init__(self, prog, indent_increment=2, max_help_position=40, width=None):
        super(_CustomFormatter, self).__init__(prog, indent_increment, max_help_position, width)


def _check_positive(value):
    int_value = int(value)
    if int_value <= 0:
        raise _argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return int_value


def _make_parser():
    parser = _argparse.ArgumentParser(add_help=True, formatter_class=_CustomFormatter)
    parser.add_argument("test", help="Workflow Test Name", nargs="*")
    parser.add_argument('--server', help='Galaxy server URL', dest="galaxy_url")
    parser.add_argument('--api-key', help='Galaxy server API KEY', dest="galaxy_api_key")
    parser.add_argument('-f', '--file', default=_core.WorkflowTestCase.DEFAULT_CONFIG_FILENAME,
                        help='YAML configuration file of workflow tests (default is {0})'.format(
                            _core.WorkflowTestCase.DEFAULT_CONFIG_FILENAME))
    parser.add_argument('--enable-logger', help='Enable log messages', action='store_true', default=None)
    parser.add_argument('--debug', help='Enable debug mode', action='store_true', default=None)
    parser.add_argument('--disable-cleanup', help='Disable cleanup', action='store_true', default=None)

    parser.add_argument('--output-format', choices=OutputFormat, help='Choose output type', default=OutputFormat.text)
    parser.add_argument('--xunit-file', default=None, metavar="FILE_PATH",
                        help='Set the path of the xUnit report file (absolute or relative to the output folder)')
    parser.add_argument('-o', '--output', dest="output_folder", metavar="PATH", help='Path of the output folder')

    parser.add_argument('--max-retries', type=_check_positive, help='Max number of retries', default=None)
    parser.add_argument('--retry-delay', type=_check_positive, help='Delay between retries in seconds', default=None)
    parser.add_argument('--polling-interval', type=_check_positive, help='Delay between polling requests in seconds', default=None)

    return parser


def _parse_cli_arguments(parser, cmd_args):
    args = parser.parse_args(cmd_args)
    _logger.debug("Parsed arguments %r", args)

    if not _os.path.isfile(args.file):
        parser.error("Test file {} doesn't exist or isn't a file".format(args.file))
    if not _os.access(args.file, _os.R_OK):
        parser.error("Permission error.  Test file {} isn't accessible for reading".format(args.file))
    if args.xunit_file and args.output_format != OutputFormat.xunit:
        parser.error("--xunit-file can only be specified when using the xUnit output format")

    return args


def run_tests(filename,
              galaxy_url=None, galaxy_api_key=None,
              enable_logger=None, enable_debug=None,
              disable_cleanup=None, disable_assertions=None,
              max_retries=None, retry_delay=None, polling_interval=None,
              output_folder=None, enable_xunit=False, xunit_file=None, tests=None):
    """
    Run a workflow test suite defined in a configuration file.

    :type enable_logger: bool
    :param enable_logger: ``True`` to enable INFO messages; ``False`` (default) otherwise.

    :type enable_debug: bool
    :param enable_debug: ``True`` to enable DEBUG messages; ``False`` (default) otherwise.

    :type disable_cleanup: bool
    :param disable_cleanup: ``True`` to avoid the clean up of the workflow and history created on the Galaxy server;
        ``False`` (default) otherwise.

    :type disable_assertions: bool
    :param disable_assertions: ``True`` to disable assertions during the execution of the workflow test;
        ``False`` (default) otherwise.
    """

    # load suite configuration
    suite = _core.WorkflowTestSuite.load(filename,
                                         output_folder=output_folder)  # FIXME: do we need output_folder here ?
    # log the current configuration
    _logger.info("Configuration: %s", suite)

    # run the configured test suite
    result = suite.run(galaxy_url=galaxy_url, galaxy_api_key=galaxy_api_key, verbosity=2, tests=tests,
                       enable_xunit=enable_xunit or (xunit_file != None), xunit_file=xunit_file,
                       output_folder=output_folder,
                       enable_logger=enable_logger, enable_debug=enable_debug,
                       disable_cleanup=disable_cleanup, disable_assertions=disable_assertions,
                       max_retries=max_retries, retry_delay=retry_delay, polling_interval=polling_interval)
    # compute exit code
    exit_code = len([r for r in result.test_case_results if r.failed()])
    _logger.debug("wft4galaxy.run_tests exiting with code: %s", exit_code)
    return exit_code


def main():
    try:
        # parse arguments
        parser = _make_parser()
        options = _parse_cli_arguments(parser, _sys.argv[1:])

        # setup logging
        _common.LoggerManager.configure_logging(
            level=_logging.DEBUG if options.debug else _logging.INFO if options.enable_logger else _logging.ERROR,
            show_logger_name=True if options.debug else False
        )

        # log Python version
        _logger.debug("Python version: %s", _sys.version)

        # run tests and collect exit code
        code = run_tests(filename=options.file,
                         galaxy_url=options.galaxy_url,
                         galaxy_api_key=options.galaxy_api_key,
                         output_folder=options.output_folder,
                         enable_logger=options.enable_logger,
                         enable_debug=options.debug,
                         disable_cleanup=options.disable_cleanup,
                         max_retries=options.max_retries,
                         retry_delay=options.retry_delay,
                         polling_interval=options.polling_interval,
                         enable_xunit=(options.output_format == OutputFormat.xunit),
                         xunit_file=options.xunit_file,
                         tests=options.test)

        # report exit code to the system
        _sys.exit(code)
    except _common.RunnerStandardError as e:
        # in some cases we exit with an exception even for rather "normal"
        # situations, such as configuration errors.  For this reason we only display
        # the exception's stack trace if debug logging is enabled.
        _logger.error(e)
        if _logger.isEnabledFor(_logging.DEBUG):
            _logger.exception(e)
        _sys.exit(99)


if __name__ == '__main__':
    main()
