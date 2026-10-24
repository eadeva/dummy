"""General-purpose JUnit XML report generation.

Generates standard JUnit XML (compatible with Jenkins, GitHub Actions,
pytest, and the existing GTest JUnit XML parser in xc_ce_utils) from
a list of :class:`TestResult` dataclass instances.

Any step type that produces test verdicts (CANoe, GTest, pytest, custom
test benches) can use this reporter to write CI-compatible results.

Example usage::

    from xc_ce_utils.core_engine.reporting.adapters.exporters.junit_result_reporter import (
        TestResult,
        generate_junit_xml,
    )

    results = [
        TestResult(name='test_startup', classname='SmokeTests', status='passed'),
        TestResult(
            name='test_timeout',
            classname='SmokeTests',
            status='failed',
            message='Expected response within 500ms',
        ),
    ]
    generate_junit_xml(results, 'SmokeTests', '_reports/smoke.xml')
"""

import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from xc_ce_utils import logger

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TestResult:
    """Tool-agnostic representation of a single test case result.

    Attributes
    ----------
    name : str
        Test case name (maps to ``<testcase name="">``).
    classname : str
        Grouping / suite path (maps to ``<testcase classname="">``).
    status : str
        One of ``"passed"``, ``"failed"``, ``"error"``, ``"skipped"``.
    duration : float
        Execution time in seconds (default ``0.0``).
    message : str
        Failure / error message (empty for passed tests).
    output : str
        Captured stdout / log output (empty if none).
    description : str
        Human-readable description of the test case (maps to testcase property).
    properties : dict
        Extra key-value pairs added as ``<property>`` elements on the testcase
        (e.g. requirement ID, expected value, tool version).
    """

    name: str
    status: str  # "passed", "failed", "error", "skipped"
    classname: str = ''
    duration: float = 0.0
    message: str = ''
    output: str = ''
    description: str = ''
    properties: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_junit_xml(
    results: List[TestResult],
    suite_name: str,
    output_path: str,
    properties: Optional[Dict[str, str]] = None,
) -> str:
    """Generate a JUnit XML report from a list of test results.

    Parameters
    ----------
    results : list[TestResult]
        Individual test case results.
    suite_name : str
        Name for the ``<testsuite>`` element.
    output_path : str
        File path for the generated XML report.
    properties : dict, optional
        Extra key-value pairs added as ``<property>`` elements
        (e.g. variant, tool version, configuration path).

    Returns
    -------
    str
        Absolute path to the written XML file.
    """
    tests = len(results)
    failures = sum(1 for r in results if r.status == 'failed')
    errors = sum(1 for r in results if r.status == 'error')
    skipped = sum(1 for r in results if r.status == 'skipped')
    total_time = sum(r.duration for r in results)
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S')

    testsuites = ET.Element('testsuites')
    testsuite = ET.SubElement(
        testsuites,
        'testsuite',
        name=suite_name,
        tests=str(tests),
        failures=str(failures),
        errors=str(errors),
        skipped=str(skipped),
        time=f'{total_time:.3f}',
        timestamp=timestamp,
    )

    # Optional properties
    if properties:
        props_el = ET.SubElement(testsuite, 'properties')
        for key, value in properties.items():
            ET.SubElement(props_el, 'property', name=key, value=str(value))

    # Individual test cases
    for result in results:
        tc = ET.SubElement(
            testsuite,
            'testcase',
            classname=result.classname,
            name=result.name,
            time=f'{result.duration:.3f}',
        )

        # Testcase-level properties (description + custom properties)
        tc_props = {}
        if result.description:
            tc_props['description'] = result.description
        if result.properties:
            tc_props.update(result.properties)
        if tc_props:
            tc_props_el = ET.SubElement(tc, 'properties')
            for key, value in tc_props.items():
                ET.SubElement(tc_props_el, 'property', name=key, value=str(value))

        if result.status == 'failed':
            fail_el = ET.SubElement(
                tc,
                'failure',
                message=result.message or 'Test failed',
                type='AssertionError',
            )
            if result.output:
                fail_el.text = result.output

        elif result.status == 'error':
            err_el = ET.SubElement(
                tc,
                'error',
                message=result.message or 'Test error',
                type='TestError',
            )
            if result.output:
                err_el.text = result.output

        elif result.status == 'skipped':
            ET.SubElement(
                tc,
                'skipped',
                message=result.message or 'Test skipped',
            )

        # For "passed" — no child elements needed

        if result.output and result.status == 'passed':
            stdout_el = ET.SubElement(tc, 'system-out')
            stdout_el.text = result.output

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    tree = ET.ElementTree(testsuites)
    ET.indent(tree, space='  ')
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

    logger.info(f'JUnit XML report written to: {output_path}')
    return output_path


# ---------------------------------------------------------------------------
# Convenience: convert CANoe-style result dicts
# ---------------------------------------------------------------------------


def from_canoe_results(
    results: Dict,
    suite_name: str,
) -> List[TestResult]:
    """Convert a CANoe result dictionary to a list of :class:`TestResult`.

    Parameters
    ----------
    results : dict
        Dictionary as returned by ``CanoeTestApi.execute_test_configuration``,
        ``execute_test_environment``, or ``execute_test_modules``.
        Expected keys: ``total``, ``passed``, ``failed``, ``other``,
        ``failed_tests``.
    suite_name : str
        Default classname for passed tests.

    Returns
    -------
    list[TestResult]
        One entry per test case.
    """
    test_results: List[TestResult] = []
    failed_tests = results.get('failed_tests', [])

    for test_path in failed_tests:
        classname, testname, verdict = _parse_canoe_test_path(test_path, suite_name)
        if verdict:
            # Non-standard verdict → error
            test_results.append(
                TestResult(
                    name=testname,
                    classname=classname,
                    status='error',
                    message=f'Test ended with verdict: {verdict}',
                )
            )
        else:
            test_results.append(
                TestResult(
                    name=testname,
                    classname=classname,
                    status='failed',
                    message='Test failed',
                )
            )

    # Named passed entries (from detailed CANoe report parsing)
    passed_tests = results.get('passed_tests', [])
    if passed_tests:
        for test_path in passed_tests:
            classname, testname, _ = _parse_canoe_test_path(test_path, suite_name)
            test_results.append(
                TestResult(
                    name=testname,
                    classname=classname,
                    status='passed',
                )
            )
    else:
        # Synthetic passed entries (CANoe only provides count, not names)
        passed = results.get('passed', 0)
        for i in range(1, passed + 1):
            test_results.append(
                TestResult(
                    name=f'passed_test_{i}',
                    classname=suite_name,
                    status='passed',
                )
            )

    return test_results


def _parse_canoe_test_path(test_path: str, default_classname: str) -> tuple:
    """Parse a CANoe failed-test path into (classname, testname, verdict).

    Returns ``verdict`` as a non-empty string if the path ends with
    ``(VerdictName)``, otherwise empty string.
    """
    verdict = ''
    clean_path = test_path
    if '(' in clean_path and clean_path.endswith(')'):
        verdict = clean_path.rsplit('(', 1)[-1].rstrip(')')
        clean_path = clean_path.rsplit('(', 1)[0].strip()

    classname, separator, testname = clean_path.rpartition('/')
    if separator:
        return classname, testname, verdict
    return default_classname, clean_path, verdict
