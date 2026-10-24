"""JUnit exporter from canonical report model."""

import xml.etree.ElementTree as ET
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class JUnitReportExporter:
    """Export canonical report test data to merged JUnit XML."""

    format_name = 'junit'

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        root = ET.Element('testsuites')
        root.set('name', 'Unified Report')
        root.set('tests', str(report.total_tests))
        root.set('failures', str(report.total_failures))
        root.set('errors', str(report.total_errors))
        root.set('skipped', str(report.total_skipped))
        root.set('time', f'{report.total_time:.3f}')

        for suite in report.test_suites:
            suite_el = ET.SubElement(
                root,
                'testsuite',
                name=suite.name,
                tests=str(suite.tests),
                failures=str(suite.failures),
                errors=str(suite.errors),
                skipped=str(suite.skipped),
                time=f'{suite.time:.3f}',
                timestamp=suite.timestamp,
            )

            if suite.properties:
                props_el = ET.SubElement(suite_el, 'properties')
                for key, value in suite.properties.items():
                    ET.SubElement(
                        props_el, 'property', name=key, value=str(value)
                    )

            for case in suite.test_cases:
                tc_el = ET.SubElement(
                    suite_el,
                    'testcase',
                    classname=case.classname,
                    name=case.name,
                    time=f'{case.duration:.3f}',
                )

                if case.properties:
                    tc_props = ET.SubElement(tc_el, 'properties')
                    for key, value in case.properties.items():
                        ET.SubElement(
                            tc_props, 'property', name=key, value=str(value)
                        )

                if case.status == 'failed':
                    fail_el = ET.SubElement(
                        tc_el,
                        'failure',
                        message=case.message or 'Test failed',
                        type='AssertionError',
                    )
                    if case.output:
                        fail_el.text = case.output
                elif case.status == 'error':
                    err_el = ET.SubElement(
                        tc_el,
                        'error',
                        message=case.message or 'Test error',
                        type='TestError',
                    )
                    if case.output:
                        err_el.text = case.output
                elif case.status == 'skipped':
                    ET.SubElement(
                        tc_el,
                        'skipped',
                        message=case.message or 'Test skipped',
                    )
                elif case.output:
                    out_el = ET.SubElement(tc_el, 'system-out')
                    out_el.text = case.output

        if report.coverage:
            cov = report.coverage[0]
            suite_el = ET.SubElement(
                root,
                'testsuite',
                name='Coverage',
                tests='1',
                failures='0',
                errors='0',
                skipped='0',
                time='0.000',
            )
            tc_el = ET.SubElement(
                suite_el,
                'testcase',
                classname='coverage',
                name='gcovr_summary',
                time='0.000',
            )
            out_el = ET.SubElement(tc_el, 'system-out')
            out_el.text = (
                f'line coverage: {cov.line_coverage_pct}% '
                f'({cov.lines_covered}/{cov.lines_total}), '
                f'branch coverage: {cov.branch_coverage_pct}% '
                f'({cov.branches_covered}/{cov.branches_total})'
            )

        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        return output_path.resolve()
