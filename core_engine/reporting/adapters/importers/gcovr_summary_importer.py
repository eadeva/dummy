"""gcovr summary JSON importer adapter."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    CoverageSummary,
)


class GcovrSummaryImporter:
    """Import gcovr summary JSON into canonical coverage model."""

    name = 'gcovr-summary'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False

        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False

        return data.get('report_kind') == 'gcovr-summary'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        metrics = data.get('metrics', {})
        source_file = str(data.get('source_file', ''))

        summary = CoverageSummary(
            lines_total=int(metrics.get('lines_total', 0) or 0),
            lines_covered=int(metrics.get('lines_covered', 0) or 0),
            line_coverage_pct=float(
                metrics.get('line_coverage_pct', 100.0) or 100.0
            ),
            branches_total=int(metrics.get('branches_total', 0) or 0),
            branches_covered=int(metrics.get('branches_covered', 0) or 0),
            branch_coverage_pct=float(
                metrics.get('branch_coverage_pct', 100.0) or 100.0
            ),
            functions_total=self._opt_int(metrics.get('functions_total')),
            functions_covered=self._opt_int(metrics.get('functions_covered')),
            function_coverage_pct=self._opt_float(
                metrics.get('function_coverage_pct')
            ),
            source_file=source_file,
        )

        existing = None
        if summary.source_file:
            existing = next(
                (
                    cov
                    for cov in report.coverage
                    if cov.source_file == summary.source_file
                ),
                None,
            )
        if existing is None and report.coverage:
            existing = report.coverage[0]

        if existing is None:
            report.coverage.append(summary)
            return

        existing.lines_total = summary.lines_total
        existing.lines_covered = summary.lines_covered
        existing.line_coverage_pct = summary.line_coverage_pct
        existing.branches_total = summary.branches_total
        existing.branches_covered = summary.branches_covered
        existing.branch_coverage_pct = summary.branch_coverage_pct
        existing.functions_total = summary.functions_total
        existing.functions_covered = summary.functions_covered
        existing.function_coverage_pct = summary.function_coverage_pct

    def _opt_int(self, value):
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _opt_float(self, value):
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
