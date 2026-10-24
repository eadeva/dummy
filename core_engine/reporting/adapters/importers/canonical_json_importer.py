"""Canonical JSON test-suite importer."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    TestCase,
    TestSuite,
)


class CanonicalJsonImporter:
    """Import canonical JSON test suite files."""

    name = 'canonical-json'

    def supports(self, file_path: Path) -> bool:
        if not file_path.name.endswith('.canonical.json'):
            return False

        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False

        if isinstance(data, dict):
            return 'test_cases' in data
        if isinstance(data, list):
            return bool(data) and all(
                'test_cases' in item for item in data if isinstance(item, dict)
            )

        return False

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        """Import a canonical JSON test suite file."""
        data = json.loads(file_path.read_text(encoding='utf-8'))

        if isinstance(data, dict):
            suites_data = [data]
        elif isinstance(data, list):
            suites_data = data
        else:
            return

        for suite_data in suites_data:
            test_cases = [TestCase(**case) for case in suite_data.get('test_cases', [])]
            suite_data['test_cases'] = test_cases
            suite = TestSuite(**suite_data)
            report.merge_suite(suite)
