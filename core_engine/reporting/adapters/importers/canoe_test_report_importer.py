"""
CANoe Test Report XML Importer.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    TestCase,
    TestSuite,
)


class CanoeTestReportImporter:
    """Import CANoe test report XML files."""

    name = 'canoe-xml'

    def supports(self, file_path: Path) -> bool:
        """Support XML files that appear to be CANoe test reports."""
        if file_path.suffix.lower() != '.xml':
            return False
        try:
            # Simple heuristic: check for a common CANoe report tag
            with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                for _ in range(20):  # Check first 20 lines
                    if '<testreport' in f.readline():
                        return True
            return False
        except Exception:
            return False

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        """Import a CANoe test report XML file."""
        suite = self._parse_from_xml(file_path)
        report.merge_suite(suite)

    def _parse_from_xml(self, file_path: Path) -> TestSuite:
        """
        Parse a CANoe XML test report into a canonical TestSuite object.
        """
        content = file_path.read_text(encoding='utf-8')

        suite_name_match = re.search(r'<title>(.*?)</title>', content)
        suite_name = suite_name_match.group(1) if suite_name_match else 'CANoe Test Report'

        suite = TestSuite(
            name=suite_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_file=str(file_path.resolve()),
        )

        # Regex to find testcase blocks and their inner verdict
        testcase_pattern = re.compile(
            r'<testcase.*?title="(.*?)".*?>' r'(.*?)' r'</testcase>', re.DOTALL
        )
        verdict_pattern = re.compile(
            r'<verdict.*?type="(.*?)".*?time="(.*?)".*?>(.*?)</verdict>', re.DOTALL
        )

        for tc_match in testcase_pattern.finditer(content):
            name = tc_match.group(1)
            inner_content = tc_match.group(2)

            status = 'skipped'
            duration = 0.0
            message = 'Test case was skipped or had an indeterminate outcome.'

            verdict_match = verdict_pattern.search(inner_content)
            if verdict_match:
                canoe_status = verdict_match.group(1).lower()
                duration_text = verdict_match.group(2)

                if canoe_status == 'pass':
                    status = 'passed'
                    message = 'Test case passed.'
                elif canoe_status == 'fail':
                    status = 'failed'
                    message = verdict_match.group(3).strip() or 'Test case failed.'
                elif canoe_status == 'error':
                    status = 'error'
                    message = verdict_match.group(3).strip() or 'Test case errored.'

                if duration_text.startswith('PT') and duration_text.endswith('S'):
                    try:
                        duration = float(duration_text[2:-1])
                    except ValueError:
                        duration = 0.0

            suite.test_cases.append(
                TestCase(
                    name=name,
                    classname=suite.name,
                    status=status,
                    duration=duration,
                    message=message,
                    output=f'CANoe Test Case: {name}\nStatus: {status}\nDuration: {duration}s',
                    properties={'source_format': 'CANoe XML'},
                )
            )

        suite.recalculate_totals()
        return suite
