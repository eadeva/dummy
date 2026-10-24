"""JUnit XML importer adapter."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    TestCase,
    TestSuite,
)


class JUnitXmlImporter:
    """Import JUnit XML files into canonical test-suite model."""

    name = 'junit-xml'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.xml':
            return False
        try:
            root = ET.parse(file_path).getroot()
        except ET.ParseError:
            return False
        tag = self._local_name(root.tag)
        return tag in {'testsuite', 'testsuites'}

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        root = ET.parse(file_path).getroot()
        tag = self._local_name(root.tag)

        suites = [root] if tag == 'testsuite' else list(root)

        for suite_el in suites:
            if self._local_name(suite_el.tag) != 'testsuite':
                continue

            source_suite_name = (suite_el.attrib.get('name') or '').strip()
            if not source_suite_name:
                source_suite_name = 'Unnamed Suite'

            suites_by_name = {}

            def get_or_create_suite(name: str) -> TestSuite:
                if name not in suites_by_name:
                    suites_by_name[name] = TestSuite(
                        name=name,
                        timestamp=suite_el.attrib.get('timestamp', ''),
                        source_file=str(file_path),
                    )
                return suites_by_name[name]

            for tc_el in list(suite_el):
                if self._local_name(tc_el.tag) != 'testcase':
                    continue

                status = 'passed'
                message = ''
                output = ''
                properties = {}

                for child in list(tc_el):
                    child_name = self._local_name(child.tag)
                    if child_name == 'failure':
                        status = 'failed'
                        message = child.attrib.get('message', '')
                        output = child.text or ''
                    elif child_name == 'error':
                        status = 'error'
                        message = child.attrib.get('message', '')
                        output = child.text or ''
                    elif child_name == 'skipped':
                        status = 'skipped'
                        message = child.attrib.get('message', '')
                    elif child_name == 'system-out':
                        output = child.text or output
                    elif child_name == 'properties':
                        for prop in list(child):
                            if self._local_name(prop.tag) == 'property':
                                key = prop.attrib.get('name', '')
                                value = prop.attrib.get('value', '')
                                if key:
                                    properties[key] = value

                case_name = tc_el.attrib.get('name', 'unnamed')
                case_classname = (
                    tc_el.attrib.get('classname') or source_suite_name
                )
                derived_suite_name = self._derive_suite_name(
                    source_suite_name,
                    case_name,
                    case_classname,
                    output,
                )

                suite = get_or_create_suite(derived_suite_name)

                case = TestCase(
                    name=case_name,
                    classname=case_classname,
                    status=status,
                    duration=float(tc_el.attrib.get('time', '0') or 0),
                    message=message,
                    output=output,
                    properties=properties,
                    source_file=str(file_path),
                )
                suite.test_cases.append(case)

            for suite in suites_by_name.values():
                suite.recalculate_totals()
                report.merge_suite(suite)

    def _is_unnamed_suite(self, suite_name: str) -> bool:
        name = (suite_name or '').strip().lower()
        return name in {'', '(empty)', 'empty', 'unnamed suite'}

    def _derive_suite_name(
        self,
        source_suite_name: str,
        case_name: str,
        case_classname: str,
        output: str,
    ) -> str:
        if not self._is_unnamed_suite(source_suite_name):
            return source_suite_name

        for candidate in (case_classname, case_name):
            text = (candidate or '').strip()
            if '.' in text:
                prefix = text.split('.', 1)[0].strip()
                if prefix:
                    return prefix

        # CTest JUnit system-out typically contains this gtest line.
        match = re.search(
            r'\[----------\]\s+\d+\s+test[s]?\s+from\s+(.+)$',
            output or '',
            re.MULTILINE,
        )
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate

        return 'Unnamed Suite'

    def _local_name(self, xml_tag: str) -> str:
        if '}' in xml_tag:
            return xml_tag.rsplit('}', 1)[1]
        return xml_tag
