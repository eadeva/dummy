"""Concise GitHub workflow summary exporter."""

from __future__ import annotations

import os
from pathlib import Path

from xc_ce_utils import logger
from xc_ce_utils.core_engine.reporting.adapters.exporters.markdown_rendering import (
    aggregate_coverage,
    escape_markdown,
    overall_status,
    render_table,
    severity_counts,
)
from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport

_FAIL_STATUSES = {'failed', 'error'}
_DETAIL_SEVERITIES = {'critical', 'high'}
_SEVERITY_ORDER = ('critical', 'high', 'medium', 'low', 'warning', 'info', 'unknown')


class GitHubSummaryExporter:
    """Export canonical report as concise GitHub summary Markdown."""

    format_name = 'github_summary'

    @staticmethod
    def _format_percentage(value: float | None) -> str:
        return f'{value}%' if value is not None else 'N/A'

    @staticmethod
    def _derive_report_base_name(report: CanonicalReport, output_path: Path) -> str:
        action = str(report.metadata.get('action', '')).strip()
        variant = str(report.metadata.get('variant', '')).strip()
        if action and variant:
            return f'{action}-{variant}-report'
        if action:
            return f'{action}-report'

        name = output_path.name
        suffix = '.github-summary.md'
        if name.endswith(suffix):
            return name[: -len(suffix)]
        if output_path.suffix:
            return output_path.stem
        return name

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self._render(report, output_path)
        output_path.write_text(content, encoding='utf-8')
        self._append_to_github_summary(content)
        return output_path.resolve()

    @staticmethod
    def _append_to_github_summary(content: str) -> None:
        summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
        if not summary_path:
            return

        try:
            with Path(summary_path).open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(content)
        except OSError as exc:
            logger.warning(f'[GitHubSummaryExporter] Could not append workflow summary: {exc}')

    def _render(self, report: CanonicalReport, output_path: Path) -> str:
        lines: list[str] = []

        lines.extend(self._render_identity(report))
        lines.extend(self._render_execution(report))
        lines.extend(self._render_tests(report))
        lines.extend(self._render_coverage(report))
        lines.extend(self._render_finding_counts(report))
        lines.extend(self._render_critical_high_details(report))
        lines.extend(self._render_report_references(report, output_path))

        return '\n'.join(lines).rstrip() + '\n'

    def _render_identity(self, report: CanonicalReport) -> list[str]:  # noqa: PLR6301
        action = report.metadata.get('action', 'n/a')
        variant = report.metadata.get('variant', 'n/a')
        return [
            '# Unified Report Summary',
            f"**Action:** {escape_markdown(action)}",
            f"**Variant:** {escape_markdown(variant)}",
            f"**Result:** {overall_status(report)}",
            '',
        ]

    def _render_execution(self, report: CanonicalReport) -> list[str]:  # noqa: PLR6301
        failed_steps = [step for step in report.execution_steps if step.status.upper() == 'FAILED']
        lines = [
            '## Execution',
            (
                f'**Totals:** {report.total_execution_steps} total, '
                f'{report.failed_execution_steps} failed'
            ),
        ]
        if failed_steps:
            rows = [[step.name, step.step_type, step.status] for step in failed_steps]
            lines.append(render_table(['Step', 'Type', 'Status'], rows))
        lines.append('')
        return lines

    def _render_tests(self, report: CanonicalReport) -> list[str]:  # noqa: PLR6301
        failed_cases: list[list[object]] = []
        for suite in report.test_suites:
            for case in suite.test_cases:
                status = case.status.lower()
                if status in _FAIL_STATUSES:
                    failed_cases.append([
                        suite.name,
                        case.classname,
                        case.name,
                        case.status,
                        case.message,
                    ])

        lines = [
            '## Tests',
            (
                f'**Totals:** {report.total_tests} total, {report.total_failures} failed, '
                f'{report.total_errors} errors, {report.total_skipped} skipped'
            ),
        ]
        if failed_cases:
            lines.append(
                render_table(
                    ['Suite', 'Class', 'Test', 'Status', 'Message'],
                    failed_cases,
                )
            )
        lines.append('')
        return lines

    def _render_coverage(self, report: CanonicalReport) -> list[str]:
        lines = ['## Coverage']
        if report.coverage:
            agg = aggregate_coverage(report.coverage)
            lines.append(
                f"- Lines: {agg['lines_covered']}/{agg['lines_total']} "
                f"({self._format_percentage(agg['line_coverage_pct'])})"
            )
            lines.append(
                f"- Branches: {agg['branches_covered']}/{agg['branches_total']} "
                f"({self._format_percentage(agg['branch_coverage_pct'])})"
            )
            lines.append(
                f"- Functions: {agg['functions_covered']}/{agg['functions_total']} "
                f"({self._format_percentage(agg['function_coverage_pct'])})"
            )
        else:
            lines.append('No entries were imported.')
        lines.append('')
        return lines

    def _render_finding_counts(self, report: CanonicalReport) -> list[str]:  # noqa: PLR6301
        static_counts = severity_counts(report.findings)
        log_counts = severity_counts(report.log_findings)
        lines = ['## Finding Counts']
        rows = [
            [
                severity,
                static_counts.get(severity, 0),
                log_counts.get(severity, 0),
            ]
            for severity in _SEVERITY_ORDER
        ]
        lines.append(render_table(['Severity', 'Static', 'Log'], rows))
        lines.append('')
        return lines

    def _render_critical_high_details(self, report: CanonicalReport) -> list[str]:  # noqa: PLR6301
        highlighted = [
            finding
            for finding in report.findings
            if finding.severity.lower() in _DETAIL_SEVERITIES
        ]

        lines = ['## Critical And High Static Findings']
        if highlighted:
            rows = [
                [
                    finding.tool,
                    finding.severity,
                    finding.category,
                    finding.rule_id,
                    finding.message,
                    finding.file,
                    finding.line,
                ]
                for finding in highlighted
            ]
            lines.append(
                render_table(
                    ['Tool', 'Severity', 'Category', 'Rule', 'Message', 'File', 'Line'],
                    rows,
                )
            )
        else:
            lines.append('None.')
        lines.append('')
        return lines

    def _render_report_references(self, report: CanonicalReport, output_path: Path) -> list[str]:
        requested_formats = report.metadata.get('requested_formats', [])
        requested = {
            str(item).strip().lower()
            for item in requested_formats
            if str(item).strip()
        }

        base_name = self._derive_report_base_name(report, output_path)
        lines = ['## Full Reports']

        references: list[str] = []
        if 'markdown' in requested:
            references.append(f'{base_name}.md')
        if 'html' in requested:
            references.append(f'{base_name}.html')

        if references:
            lines.extend(f'- {escape_markdown(item)}' for item in references)
        else:
            lines.append('No full report formats were requested.')

        return lines
