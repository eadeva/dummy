"""Importer for TACO run summaries written by the ``taco_ctest`` and ``taco_robotfw`` steps."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport

SUMMARY_FILE_NAME = 'taco_summary.json'


class TacoImporter:
    """Import ``taco_summary.json`` files (test selection verdicts) into ``metadata['taco']``."""

    name = 'taco'

    def supports(self, file_path: Path) -> bool:
        return file_path.name.lower() == SUMMARY_FILE_NAME

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            selections = report.metadata.setdefault('taco', {'available': True, 'selections': []})
            selections['selections'].append(
                {'summary_file': str(file_path), 'parse_error': str(exc)}
            )
            return
        if not isinstance(data, dict):
            return
        results = [
            {'test_case': str(item.get('test_case', '')), 'verdict': str(item.get('verdict', ''))}
            for item in data.get('results', []) or []
            if isinstance(item, dict)
        ]
        taco = report.metadata.setdefault('taco', {'available': True, 'selections': []})
        taco['selections'].append(
            {
                'selection': str(data.get('selection', '')),
                'variant': str(data.get('variant', '')),
                'counts': data.get('counts', {}) if isinstance(data.get('counts'), dict) else {},
                'results': results,
                'summary_file': str(file_path),
            }
        )
