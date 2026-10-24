"""Canonical Markdown exporter."""

import json
from pathlib import Path
from typing import Any

from xc_ce_utils.core_engine.reporting.adapters.exporters.markdown_rendering import (
    aggregate_coverage,
    escape_markdown,
    overall_status,
    render_table,
    severity_counts,
)
from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    CoverageSummary,
    ExecutionStepRecord,
    Finding,
    LogFinding,
    Need,
    TestSuite,
)


class MarkdownReportExporter:
    """Export canonical report as Markdown."""

    format_name = 'markdown'

    @staticmethod
    def _format_percentage(value: float | None) -> str:
        return f'{value}%' if value is not None else 'N/A'

    @staticmethod
    def _append_json_block(lines: list[str], value: Any) -> None:
        lines.append('```json')
        lines.append(json.dumps(value, indent=2, ensure_ascii=False, default=str))
        lines.append('```')

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sections = [
            self._render_header(report),
            self._render_summary(report),
            self._render_execution_steps(report.execution_steps),
            self._render_test_suites(report.test_suites),
            self._render_coverage(report.coverage),
            self._render_findings(report.findings),
            self._render_log_findings(report.log_findings),
            self._render_needs(report.needs),
            self._render_dependencies(report.metadata),
            self._render_sbom(report.metadata.get('cyclonedx')),
            self._render_additional_metadata(report.metadata),
        ]
        output_path.write_text('\n\n'.join(sections).rstrip() + '\n', encoding='utf-8')
        return output_path.resolve()

    def _render_header(self, report: CanonicalReport) -> str:  # noqa: PLR6301
        meta = report.metadata
        lines = ['# Canonical Report']
        if action := meta.get('action'):
            lines.append(f'**Action:** {escape_markdown(action)}')
        if variant := meta.get('variant'):
            lines.append(f'**Variant:** {escape_markdown(variant)}')
        if generated := meta.get('generated_at'):
            lines.append(f'**Generated:** {escape_markdown(generated)}')
        return '\n'.join(lines)

    def _render_summary(self, report: CanonicalReport) -> str:
        status = overall_status(report)
        lines = [
            '## Summary',
            f'**Overall Status:** {status}',
            f'**Execution Steps:** {report.total_execution_steps} total, {report.failed_execution_steps} failed',
            f'**Test Cases:** {report.total_tests} total, {report.total_failures} failed, {report.total_errors} errors, {report.total_skipped} skipped',
        ]

        if report.coverage:
            agg = aggregate_coverage(report.coverage)
            line_pct = agg['line_coverage_pct']
            branch_pct = agg['branch_coverage_pct']
            lines.append(
                f'**Coverage:** {self._format_percentage(line_pct)} lines, '
                f'{self._format_percentage(branch_pct)} branches'
            )

        if report.findings:
            counts = severity_counts(report.findings)
            lines.append(
                f"**Static Findings:** {sum(counts.values())} total ({counts['critical']} critical, {counts['high']} high, {counts['medium']} medium)"
            )

        if report.log_findings:
            counts = severity_counts(report.log_findings)
            lines.append(f'**Log Findings:** {sum(counts.values())} total')

        return '\n'.join(lines)

    def _render_execution_steps(self, steps: list[ExecutionStepRecord]) -> str:  # noqa: PLR6301
        lines = ['## Execution Steps']
        if not steps:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        for step in steps:
            lines.append(f'### {escape_markdown(step.name)}')
            lines.append(f'**Type:** {escape_markdown(step.step_type)}')
            lines.append(f'**Status:** {escape_markdown(step.status)}')
            if step.elapsed_human:
                lines.append(f'**Duration:** {escape_markdown(step.elapsed_human)}')

            if step.parameters:
                lines.append('**Parameters:**')
                lines.append('```json')
                lines.append(json.dumps(step.parameters, indent=2, ensure_ascii=False, default=str))
                lines.append('```')

            if step.results:
                lines.append(f"**Results:** {', '.join(escape_markdown(r) for r in step.results)}")

            if step.artifacts:
                lines.append('**Artifacts:**')
                for key, value in step.artifacts.items():
                    lines.append(f'- {escape_markdown(key)}: {escape_markdown(value)}')

        return '\n'.join(lines)

    def _render_test_suites(self, suites: list[TestSuite]) -> str:  # noqa: PLR6301
        lines = ['## Test Suites']
        if not suites:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        for suite in suites:
            lines.append(f'### {escape_markdown(suite.name)}')
            lines.append(
                f'**Tests:** {suite.tests}, **Failures:** {suite.failures}, **Errors:** {suite.errors}, **Skipped:** {suite.skipped}'
            )
            if suite.time is not None:
                lines.append(f'**Time:** {suite.time:.3f}s')

            if suite.test_cases:
                rows = [
                    [
                        case.classname,
                        case.name,
                        case.status,
                        f'{case.duration:.3f}s' if case.duration is not None else '',
                        case.message,
                    ]
                    for case in suite.test_cases
                ]
                lines.append(render_table(['Class', 'Test', 'Status', 'Duration', 'Message'], rows))

        return '\n'.join(lines)

    def _render_coverage(self, coverage: list[CoverageSummary]) -> str:
        lines = ['## Coverage']
        if not coverage:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        rows = []
        for entry in coverage:
            rows.append(
                [
                    entry.source_file or 'Overall',
                    entry.lines_covered,
                    entry.lines_total,
                    f'{entry.line_coverage_pct:.2f}%'
                    if entry.line_coverage_pct is not None
                    else 'N/A',
                    entry.branches_covered,
                    entry.branches_total,
                    f'{entry.branch_coverage_pct:.2f}%'
                    if entry.branch_coverage_pct is not None
                    else 'N/A',
                ]
            )

        lines.append(
            render_table(
                [
                    'Source',
                    'Lines Covered',
                    'Lines Total',
                    'Line %',
                    'Branches Covered',
                    'Branches Total',
                    'Branch %',
                ],
                rows,
            )
        )

        agg = aggregate_coverage(coverage)
        lines.append('')
        lines.append('**Aggregated Coverage:**')
        lines.append(
            f"- Lines: {agg['lines_covered']}/{agg['lines_total']} "
            f"({self._format_percentage(agg['line_coverage_pct'])})"
        )
        lines.append(
            f"- Branches: {agg['branches_covered']}/{agg['branches_total']} "
            f"({self._format_percentage(agg['branch_coverage_pct'])})"
        )
        if agg['functions_total']:
            lines.append(
                f"- Functions: {agg['functions_covered']}/{agg['functions_total']} "
                f"({self._format_percentage(agg['function_coverage_pct'])})"
            )

        return '\n'.join(lines)

    def _render_findings(self, findings: list[Finding]) -> str:  # noqa: PLR6301
        lines = ['## Static Analysis Findings']
        if not findings:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        counts = severity_counts(findings)
        lines.append(
            f"**Total:** {len(findings)} ({counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low)"
        )

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
            for finding in findings
        ]
        lines.append(
            render_table(['Tool', 'Severity', 'Category', 'Rule', 'Message', 'File', 'Line'], rows)
        )

        return '\n'.join(lines)

    def _render_log_findings(self, findings: list[LogFinding]) -> str:  # noqa: PLR6301
        lines = ['## Log Findings']
        if not findings:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        lines.append(f'**Total:** {len(findings)}')

        rows = [
            [
                finding.step,
                finding.type,
                finding.classification,
                finding.message,
                finding.file,
                finding.line,
            ]
            for finding in findings
        ]
        lines.append(
            render_table(['Step', 'Type', 'Classification', 'Message', 'File', 'Line'], rows)
        )

        return '\n'.join(lines)

    def _render_needs(self, needs: list[Need]) -> str:  # noqa: PLR6301
        lines = ['## Needs And Traceability']
        if not needs:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        rows = [
            [need.id, need.type, need.title, ', '.join(need.links) if need.links else '']
            for need in needs
        ]
        lines.append(render_table(['ID', 'Type', 'Title', 'Links'], rows))

        return '\n'.join(lines)

    def _render_dependencies(self, metadata: dict[str, Any]) -> str:
        lines = ['## Dependencies']

        reqs = metadata.get('requirements', [])
        downloads = metadata.get('artifactory_downloads', [])

        if not reqs and not downloads:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        if reqs:
            lines.append('### Requirements')
            rows = [[req.get('name', ''), req.get('version', '')] for req in reqs]
            lines.append(render_table(['Name', 'Version'], rows))
            lines.append('**Requirements Metadata (Full):**')
            self._append_json_block(lines, reqs)

        if downloads:
            lines.append('### Artifactory Downloads')
            rows = [[dl.get('name', ''), dl.get('version', '')] for dl in downloads]
            lines.append(render_table(['Name', 'Version'], rows))
            lines.append('**Artifactory Download Metadata (Full):**')
            self._append_json_block(lines, downloads)

        return '\n'.join(lines)

    def _render_sbom(self, cyclonedx: dict[str, Any] | None) -> str:
        lines = ['## SBOM']
        if not cyclonedx:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        total = cyclonedx.get('components_total', 0)
        lines.append(f'**Components:** {total}')

        components = cyclonedx.get('components', [])
        if components:
            rows = [
                [comp.get('name', ''), comp.get('version', ''), comp.get('type', '')]
                for comp in components
            ]
            lines.append(render_table(['Name', 'Version', 'Type'], rows))

        lines.append('**SBOM Metadata (Full):**')
        self._append_json_block(lines, cyclonedx)

        return '\n'.join(lines)

    def _render_additional_metadata(self, metadata: dict[str, Any]) -> str:
        lines = ['## Additional Metadata']

        # Exclude keys that were already rendered in specific sections
        excluded_keys = {
            'action',
            'variant',
            'generated_at',
            'requirements',
            'artifactory_downloads',
            'cyclonedx',
        }

        additional = {k: v for k, v in metadata.items() if k not in excluded_keys}

        if not additional:
            lines.append('No entries were imported.')
            return '\n'.join(lines)

        self._append_json_block(lines, additional)

        return '\n'.join(lines)
