"""Simple HTML exporter for canonical report data."""

from html import escape
from pathlib import Path

from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections import (
    render_advanced_help_section,
    render_arch2needs_section,
    render_coverage_section,
    render_dependencies_section,
    render_execution_section,
    render_log_findings_section,
    render_needs_section,
    render_sbom_section,
    render_static_findings_section,
    render_taco_section,
    render_tests_section,
)
from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class HtmlReportExporter:
    """Export canonical report to a lightweight standalone HTML file."""

    format_name = 'html'

    def _suite_label(self, suite_name: str, classname: str) -> str:
        suite = (suite_name or '').strip()
        if suite:
            return suite
        cls = (classname or '').strip()
        if cls:
            return cls
        return 'Unnamed Suite'

    def _status_class(self, status: str) -> str:
        normalized = (status or '').strip().lower()
        if normalized in {'passed', 'success'}:
            return 'status-passed'
        if normalized in {'failed', 'fail'}:
            return 'status-failed'
        if normalized in {'error', 'user_interrupt', 'interrupted'}:
            return 'status-error'
        if normalized in {'warning', 'warn'}:
            return 'status-warning'
        if normalized in {'skipped', 'not_executed', 'n.a.', 'na'}:
            return 'status-skipped'
        return 'status-unknown'

    def _severity_class(self, severity: str) -> str:
        normalized = (severity or '').strip().lower()
        if normalized in {'critical', 'high', 'medium', 'low', 'info'}:
            return f'sev-{normalized}'
        return 'sev-unknown'

    def _donut(self, pct: float, css_class: str, label: str, ratio: str) -> str:
        safe_pct = max(0.0, min(100.0, float(pct)))
        return (
            f'<div class="metric-card">'
            f'<div class="donut {css_class}" style="--p:{safe_pct:.1f};">'
            f'<div class="donut-value">{safe_pct:.1f}%</div>'
            f'</div>'
            f'<div class="metric-label">{escape(label)}</div>'
            f'<div class="metric-ratio">{escape(ratio)}</div>'
            f'</div>'
        )

    def _aggregate_coverage_metrics(self, report: CanonicalReport):
        lines_total = sum(c.lines_total for c in report.coverage)
        lines_covered = sum(c.lines_covered for c in report.coverage)
        branches_total = sum(c.branches_total for c in report.coverage)
        branches_covered = sum(c.branches_covered for c in report.coverage)

        functions_total_values = [
            c.functions_total for c in report.coverage if c.functions_total is not None
        ]
        functions_covered_values = [
            c.functions_covered for c in report.coverage if c.functions_covered is not None
        ]

        functions_total = sum(functions_total_values) if functions_total_values else None
        functions_covered = sum(functions_covered_values) if functions_covered_values else None

        def pct(covered, total):
            if covered is None or total is None or total <= 0:
                return None
            return round((covered / total) * 100.0, 2)

        return [
            {
                'label': 'Line Coverage',
                'covered': lines_covered,
                'total': lines_total,
                'pct': pct(lines_covered, lines_total),
                'css': 'line',
            },
            {
                'label': 'Function Coverage',
                'covered': functions_covered,
                'total': functions_total,
                'pct': pct(functions_covered, functions_total),
                'css': 'function',
            },
            {
                'label': 'Branch Coverage',
                'covered': branches_covered,
                'total': branches_total,
                'pct': pct(branches_covered, branches_total),
                'css': 'branch',
            },
        ]

    def _coverage_value_label(self, covered, total) -> str:
        if covered is None or total is None:
            return 'n/a'
        return f'{covered}/{total}'

    def _execution_sort_key(self, step) -> tuple:
        """Sort execution steps by canonical execution index."""
        execution_index = getattr(step, 'execution_index', None)
        if execution_index is not None:
            try:
                return (0, int(execution_index), 0.0, step.name)
            except Exception:
                pass
        return (2, 0, 0.0, step.name)

    def _resolve_action_name(self, report: CanonicalReport, output_path: Path) -> str:
        metadata = report.metadata or {}
        candidate = (
            metadata.get('action')
            or metadata.get('build_action')
            or metadata.get('step')
            or metadata.get('workflow')
            or output_path.parent.name
        )
        text = str(candidate or 'unknown').strip()
        return text or 'unknown'

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        action_name = self._resolve_action_name(report, output_path)
        report_title = f'Unified Report - Action {action_name}'

        needs_by_id = {need.id: need for need in report.needs}
        test_rows = []
        for suite in report.test_suites:
            for case in suite.test_cases:
                status_class = self._status_class(case.status)

                spec_id = case.properties.get('test_spec_id')
                spec_html = ''
                if spec_id:
                    need = needs_by_id.get(spec_id)
                    if need:
                        spec_html = (
                            f'<td><b>{escape(need.title)}</b><br>{escape(need.description)}</td>'
                        )
                    else:
                        spec_html = f'<td><span class="badge status-warning">NOT FOUND: {escape(spec_id)}</span></td>'
                else:
                    spec_html = '<td></td>'

                test_rows.append(
                    f'<tr class="{status_class}">'
                    f'<td class="col-status"><span class="badge {status_class}">{escape(case.status)}</span></td>'
                    f'<td>{escape(self._suite_label(suite.name, case.classname))}</td>'
                    f'<td>{escape(case.classname)}</td>'
                    f'<td>{escape(case.name)}</td>'
                    f'<td class="col-short">{case.duration:.3f}</td>'
                    f'<td class="col-message">{escape(case.message)}</td>'
                    f'{spec_html}'
                    '</tr>'
                )

        execution_rows = []
        for step in sorted(report.execution_steps, key=self._execution_sort_key):
            status_class = self._status_class(step.status)
            elapsed = (
                step.elapsed_human
                if step.elapsed_human
                else (f'{step.elapsed_seconds:.3f}s' if step.elapsed_seconds is not None else '')
            )
            execution_rows.append(
                f'<tr class="{status_class}">'
                f'<td class="col-status"><span class="badge {status_class}">{escape(step.status)}</span></td>'
                f'<td>{escape(step.name)}</td>'
                f'<td>{escape(step.step_type)}</td>'
                f'<td>{escape(step.test_status)}</td>'
                f'<td class="col-short">{escape(elapsed)}</td>'
                '</tr>'
            )

        log_findings_rows = []
        log_classification_values = set()
        for finding in report.log_findings:
            issue_type = (finding.type or '').strip().lower() or 'warning'
            status_class = self._status_class(issue_type)
            classification_value = (finding.classification or '').strip()
            if classification_value:
                log_classification_values.add(classification_value)
            log_findings_rows.append(
                f'<tr class="{status_class}">'
                f'<td>{escape(finding.step)}</td>'
                f'<td><span class="badge {status_class}">{escape(issue_type)}</span></td>'
                f'<td>{escape(classification_value)}</td>'
                f'<td>{escape(finding.file)}</td>'
                f'<td class="col-short">{finding.line}</td>'
                f'<td class="col-message">{escape(finding.message)}</td>'
                '</tr>'
            )

        static_findings_rows = []
        for finding in report.findings:
            severity_class = self._severity_class(finding.severity)
            props = {
                (str(k).strip().lower()): str(v).strip()
                for k, v in (finding.properties or {}).items()
            }
            producer_message_number = props.get(
                'producer component:message number',
                finding.rule_id,
            )
            criticality = props.get('criticality', '')
            severity_text = props.get('severity', finding.severity)
            suppression_type_bitmask = props.get('suppression type bitmask', '')
            suppression_justification = props.get('suppression justification', '')
            rule_group = props.get('rule group', '')
            rule_scope = props.get('rule scope', '')
            rule_text = props.get('rule text', '')
            static_findings_rows.append(
                f'<tr class="{severity_class}">'
                f'<td>{escape(finding.file)}</td>'
                f'<td class="col-short">{finding.line}</td>'
                f'<td class="col-short">{finding.column}</td>'
                f'<td>{escape(producer_message_number)}</td>'
                f'<td class="col-message">{escape(finding.message)}</td>'
                f'<td>{escape(criticality)}</td>'
                f'<td><span class="badge {severity_class}">{escape(severity_text)}</span></td>'
                f'<td>{escape(suppression_type_bitmask)}</td>'
                f'<td>{escape(suppression_justification)}</td>'
                f'<td>{escape(rule_group)}</td>'
                f'<td>{escape(rule_scope)}</td>'
                f'<td>{escape(rule_text)}</td>'
                '</tr>'
            )

        coverage_metrics = self._aggregate_coverage_metrics(report)
        coverage_cards = []
        for metric in coverage_metrics:
            if metric['pct'] is None:
                # Only show Line and Branch coverage, hide Function Coverage if n/a
                if metric['label'] != 'Function Coverage':
                    coverage_cards.append(
                        "<div class=\"metric-card\">"
                        f"<div class=\"metric-label\">{escape(metric['label'])}</div>"
                        "<div class=\"metric-ratio\">n/a</div>"
                        "</div>"
                    )
                continue

            coverage_cards.append(
                self._donut(
                    pct=metric['pct'],
                    css_class=metric['css'],
                    label=metric['label'],
                    ratio=self._coverage_value_label(metric['covered'], metric['total']),
                )
            )

        coverage_rows = []
        for item in sorted(report.coverage, key=lambda c: c.source_file):
            lines_lbl = self._coverage_value_label(item.lines_covered, item.lines_total)
            if item.lines_total > 0:
                lines_lbl += f' ({item.line_coverage_pct}%)'

            branches_lbl = self._coverage_value_label(item.branches_covered, item.branches_total)
            if item.branches_total > 0:
                branches_lbl += f' ({item.branch_coverage_pct}%)'

            functions_lbl = self._coverage_value_label(item.functions_covered, item.functions_total)
            if item.functions_total is not None and item.functions_total > 0:
                functions_lbl += f' ({item.function_coverage_pct}%)'

            coverage_rows.append(
                '<tr>'
                f'<td>{escape(item.source_file)}</td>'
                f'<td class="col-short">{escape(lines_lbl)}</td>'
                f'<td class="col-short">{escape(branches_lbl)}</td>'
                f'<td class="col-short">{escape(functions_lbl)}</td>'
                '</tr>'
            )

        has_test_cases = len(test_rows) > 0
        has_coverage = len(report.coverage) > 0
        log_exceptions = sum(
            1 for f in report.log_findings if (f.type or '').strip().lower() == 'exception'
        )
        log_errors = sum(
            1 for f in report.log_findings if (f.type or '').strip().lower() == 'error'
        )
        log_warnings = sum(
            1 for f in report.log_findings if (f.type or '').strip().lower() == 'warning'
        )

        has_log_findings = len(log_findings_rows) > 0
        has_static_findings = len(static_findings_rows) > 0

        metadata = report.metadata or {}
        static_findings_analysis = metadata.get('static_findings_analysis', {})
        if not isinstance(static_findings_analysis, dict):
            static_findings_analysis = {}

        static_section_title = str(
            static_findings_analysis.get('section_title', 'Full Static Code Analysis')
            or 'Full Static Code Analysis'
        )

        severity_cards = static_findings_analysis.get('severity_cards', [])
        if not isinstance(severity_cards, list):
            severity_cards = []
        static_severity_cards_html = ''.join(
            f"<div class=\"card card-{escape(str(card.get('tone', 'neutral')))}{' card-ungated' if bool(card.get('ungated', False)) else ''}\"><strong>Severity {escape(str(card.get('severity', '')))}</strong><br />{int(card.get('count', 0) or 0)}</div>"
            for card in severity_cards
            if isinstance(card, dict) and int(card.get('count', 0) or 0) > 0
        )

        producer_rows = static_findings_analysis.get('producer_rows', [])
        if not isinstance(producer_rows, list):
            producer_rows = []
        producer_rows_html = ''.join(
            f"<tr>"
            f"<td>{escape(str(row.get('producer', 'unknown')))}</td>"
            f"<td>{escape(str(row.get('severity', '')))}</td>"
            f"<td>{escape(str(row.get('threshold', 'not-gated')))}</td>"
            f"<td class=\"col-short\">{int(row.get('violations', 0) or 0)}</td>"
            f"</tr>"
            for row in producer_rows
            if isinstance(row, dict) and int(row.get('violations', 0) or 0) > 0
        )
        static_producer_table_html = ''
        if producer_rows_html:
            static_producer_table_html = f"""
      <details class=\"report-subsection\">
        <summary>Producer/Severity Overview</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap compact-wrap\">
          <table>
            <thead>
              <tr><th>Producer</th><th>Severity</th><th>Threshold</th><th class=\"col-short\">Violations</th></tr>
            </thead>
            <tbody>
              {producer_rows_html}
            </tbody>
          </table>
          </div>
        </div>
      </details>
"""

        build_context = metadata.get('build_context', {})
        if not isinstance(build_context, dict):
            build_context = {}

        xc_ce_utils_version = (
            str(
                build_context.get('xc_ce_utils_version', '')
                or metadata.get('xc_ce_utils_version', 'unknown')
                or 'unknown'
            ).strip()
            or 'unknown'
        )
        rb_version_value = (
            str(build_context.get('rb_version', 'unknown') or 'unknown').strip() or 'unknown'
        )
        variant_long_name = (
            str(
                build_context.get('variant_long_name', '')
                or metadata.get('variant', 'unknown')
                or 'unknown'
            ).strip()
            or 'unknown'
        )
        short_commit_hash = (
            str(build_context.get('short_commit_hash', 'unknown') or 'unknown').strip() or 'unknown'
        )
        os_name_value = (
            str(build_context.get('os_name', 'unknown') or 'unknown').strip() or 'unknown'
        )
        docker_enabled = bool(build_context.get('docker_enabled', False))

        git_is_dirty = str(build_context.get('git_is_dirty', 'false')).strip().lower()
        if git_is_dirty in {'true', 'yes', 'on', '1'}:
            dirty_card = (
                '<div class="card card-warn" style="background: #fde8e8; color: #9b1c1c; border-color: #f8b4b4;">'
                '<strong>Dirty</strong><br />Yes</div>'
            )
        else:
            dirty_card = (
                '<div class="card card-info" style="background: #ecfdf5; color: #047857; border-color: #a7f3d0;">'
                '<strong>Dirty</strong><br />No</div>'
            )

        top_cards = [
            f'<div class="card card-info"><strong>RB_VERSION</strong><br />{escape(rb_version_value)}</div>',
            f'<div class="card card-info"><strong>XC-CE Utils Version</strong><br />{escape(xc_ce_utils_version)}</div>',
            f'<div class="card card-info"><strong>Variant</strong><br />{escape(variant_long_name)}</div>',
            f'<div class="card card-info"><strong>Short Commit Hash</strong><br />{escape(short_commit_hash)}</div>',
            dirty_card,
            f'<div class="card card-warn"><strong>OS</strong><br />{escape(os_name_value)}</div>',
        ]
        if docker_enabled:
            top_cards.append('<div class="card card-warn"><strong>Docker</strong><br />true</div>')

        top_summary_cards_html = f"""
  <div class=\"section-summary\">
    {''.join(top_cards)}
  </div>
"""

        dependencies_section_html = render_dependencies_section(
            metadata=metadata,
        )

        project_config = report.metadata.get('project_config')
        if project_config:
            advanced_help_section_html = render_advanced_help_section(project_config)
        else:
            advanced_help_section_html = ''

        sbom_section_html = render_sbom_section(
            metadata.get('cyclonedx', {}), metadata.get('sbom_discovery', {})
        )

        needs_section_html = render_needs_section(metadata.get('needs_analysis', {}))

        arch2needs_section_html = render_arch2needs_section(
            metadata.get('arch2needs', {}),
            self._status_class,
        )

        taco_section_html = render_taco_section(metadata.get('taco', {}), self._status_class)

        log_classification_options_html = ''.join(
            f'<option value="{escape(value)}">{escape(value)}</option>'
            for value in sorted(log_classification_values, key=lambda item: str(item).lower())
        )
        static_severity_values = static_findings_analysis.get('severity_values', [])
        if not isinstance(static_severity_values, list):
            static_severity_values = []
        static_severity_options_html = ''.join(
            f'<option value="{escape(value)}">{escape(value)}</option>'
            for value in sorted(static_severity_values, key=lambda item: str(item).lower())
        )

        execution_section_summary = (
            f'<div class="section-summary">'
            f'<div class="card card-neutral"><strong>Total Steps</strong><br />{report.total_execution_steps}</div>'
            f'<div class="card card-danger"><strong>Step Failures</strong><br />{report.failed_execution_steps}</div>'
            f'</div>'
        )

        execution_section_html = render_execution_section(
            execution_section_summary=execution_section_summary,
            execution_rows=execution_rows,
        )

        tests_section_html = render_tests_section(
            has_test_cases=has_test_cases,
            report=report,
            test_rows=test_rows,
        )

        coverage_section_html = render_coverage_section(
            has_coverage=has_coverage,
            coverage_sources_count=len(report.coverage),
            coverage_cards=coverage_cards,
            coverage_rows=coverage_rows,
        )

        static_findings_section_html = render_static_findings_section(
            has_static_findings=has_static_findings,
            static_section_title=static_section_title,
            findings_total=len(report.findings),
            static_severity_cards_html=static_severity_cards_html,
            static_producer_table_html=static_producer_table_html,
            static_severity_options_html=static_severity_options_html,
            static_findings_rows=static_findings_rows,
        )

        log_findings_section_html = render_log_findings_section(
            has_log_findings=has_log_findings,
            findings_total=len(report.log_findings),
            log_exceptions=log_exceptions,
            log_errors=log_errors,
            log_warnings=log_warnings,
            log_classification_options_html=log_classification_options_html,
            log_findings_rows=log_findings_rows,
        )

        # Clear standard sections for advanced-help documentation pages
        if metadata.get('action') == 'adv-help':
            dependencies_section_html = ''
            execution_section_html = ''
            sbom_section_html = ''
            needs_section_html = ''
            arch2needs_section_html = ''
            taco_section_html = ''
            tests_section_html = ''
            coverage_section_html = ''
            static_findings_section_html = ''
            log_findings_section_html = ''

        html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(report_title)}</title>
  <style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 1rem; color: #222; background: #fbfcfd; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 0; table-layout: auto; }}
  #coverage-table td:first-child {{ word-break: break-all; max-width: 450px; }}
  th, td {{ border: 1px solid #d5dde5; padding: 0.35rem 0.5rem; font-size: 0.9rem; vertical-align: top; }}
  th {{ background: #eef3f8; text-align: left; white-space: nowrap; }}
  h1, h2 {{ margin: 0.5rem 0; }}
  .section-summary {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0.2rem 0 0.5rem 0; }}
  .report-section {{ border: 1px solid #d5dde5; border-radius: 8px; background: #fff; margin: 0.75rem 0; overflow: visible; }}
  .report-section > summary {{ cursor: pointer; list-style: none; font-size: 1.1rem; font-weight: 600; padding: 0.55rem 0.7rem; background: #f3f7fb; border-bottom: 1px solid #d5dde5; }}
  .report-section > summary::-webkit-details-marker {{ display: none; }}
  .report-section > summary::before {{ content: "-"; display: inline-block; margin-right: 0.4rem; color: #334155; }}
  .report-section:not([open]) > summary::before {{ content: "+"; }}
  .report-section .section-body {{ padding: 0.5rem 0.6rem 0.3rem 0.6rem; }}
  .report-subsection {{ border: 1px solid #d5dde5; border-radius: 8px; margin-bottom: 0.6rem; background: #fff; }}
  .report-subsection > summary {{ cursor: pointer; list-style: none; padding: 0.4rem 0.55rem; font-size: 0.92rem; font-weight: 600; background: #f8fafc; border-bottom: 1px solid #d5dde5; }}
  .report-subsection > summary::-webkit-details-marker {{ display: none; }}
  .report-subsection > summary::before {{ content: "-"; display: inline-block; margin-right: 0.35rem; color: #475569; }}
  .report-subsection:not([open]) > summary::before {{ content: "+"; }}
  .card {{ border: 1px solid #d5dde5; background: #fff; padding: 0.5rem 0.75rem; border-radius: 6px; min-width: 120px; }}
  .card-danger {{ background: #fdeceb; border-color: #ef9a9a; color: #7f1d1d; }}
  .card-warn {{ background: #fff4df; border-color: #f5c26b; color: #8a4b00; }}
  .card-info {{ background: #e8f1ff; border-color: #9ec5ff; color: #1e3a8a; }}
  .card-neutral {{ background: #f8fafc; border-color: #d5dde5; color: #1f2937; }}
  .card-ungated {{ background: #eceff3 !important; border-color: #cfd8e3 !important; color: #475569 !important; }}
  .compact-wrap {{ max-height: 20vh; }}
  .badge {{ display: inline-block; padding: 0.1rem 0.45rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }}
  .status-passed .badge, .badge.status-passed {{ background: #d9f2e3; color: #0f6b37; }}
  .status-failed .badge, .badge.status-failed {{ background: #fde3e3; color: #9b1c1c; }}
  .status-error .badge, .badge.status-error {{ background: #ffe3d1; color: #9a3412; }}
  .status-warning .badge, .badge.status-warning {{ background: #fff4df; color: #8a4b00; }}
  .status-skipped .badge, .badge.status-skipped {{ background: #eceef1; color: #4b5563; }}
  .status-unknown .badge, .badge.status-unknown {{ background: #e5e7eb; color: #374151; }}
  .sev-critical .badge, .badge.sev-critical {{ background: #7f1d1d; color: #fff; }}
  .sev-high .badge, .badge.sev-high {{ background: #dc2626; color: #fff; }}
  .sev-medium .badge, .badge.sev-medium {{ background: #f59e0b; color: #111827; }}
  .sev-low .badge, .badge.sev-low {{ background: #fde68a; color: #111827; }}
  .sev-info .badge, .badge.sev-info {{ background: #dbeafe; color: #1e3a8a; }}
  .sev-unknown .badge, .badge.sev-unknown {{ background: #e5e7eb; color: #374151; }}
  .coverage-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.85rem; margin-bottom: 1rem; }}
  .metric-card {{ background: #fff; border: 1px solid #d5dde5; border-radius: 8px; padding: 0.7rem 0.6rem; text-align: center; }}
  .donut {{
    --p: 0;
    width: 78px;
    height: 78px;
    border-radius: 50%;
    margin: 0 auto 0.45rem auto;
    display: grid;
    place-items: center;
    background: conic-gradient(var(--c, #16a34a) calc(var(--p) * 1%), #e6ecf2 0);
    position: relative;
  }}
  .donut::before {{ content: \"\"; width: 54px; height: 54px; border-radius: 50%; background: #fff; position: absolute; }}
  .donut-value {{ position: relative; z-index: 1; font-size: 0.8rem; font-weight: 700; color: #111827; }}
  .donut.line {{ --c: #16a34a; }}
  .donut.function {{ --c: #8b5cf6; }}
  .donut.branch {{ --c: #0284c7; }}
  .metric-label {{ font-size: 0.85rem; font-weight: 600; color: #111827; }}
  .metric-ratio {{ font-size: 0.78rem; color: #4b5563; margin-top: 0.1rem; }}
  .pie-charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 0.9rem; margin: 0.5rem 0 0.8rem 0; }}
  .pie-row-title {{ font-size: 0.88rem; font-weight: 600; color: #334155; margin: 0.1rem 0 0.45rem 0; }}
  .diagram-block {{ border: 1px solid #d5dde5; border-radius: 8px; background: #fff; padding: 0.6rem 0.7rem; }}
  .req-type-status-lines {{ display: flex; flex-direction: column; gap: 0.7rem; margin-bottom: 0.8rem; }}
  .req-type-status-row {{ border: 1px solid #d5dde5; border-radius: 8px; background: #fff; padding: 0.55rem 0.65rem; }}
  .req-type-status-title {{ font-size: 0.86rem; font-weight: 600; color: #334155; margin: 0.1rem 0 0.45rem 0; }}
  .table-meta {{ display: flex; justify-content: flex-end; align-items: center; gap: 0.5rem; margin: 0.2rem 0 0.35rem 0; }}
  .filter-count {{ font-size: 0.8rem; color: #4b5563; }}
  .table-wrap {{ border: 1px solid #d5dde5; border-radius: 8px; background: #fff; overflow: auto; max-height: 44vh; margin-bottom: 1rem; }}
  .table-wrap table {{ border: 0; }}
  .table-wrap thead tr:first-child th {{ position: sticky; top: 0; z-index: 3; }}
  .table-wrap thead tr.column-filters th {{ position: sticky; top: 34px; z-index: 2; }}
  .column-filters th {{ background: #f8fafc; }}
  .column-filters input, .column-filters select {{ width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 0.25rem 0.35rem; font-size: 0.8rem; }}
  .clear-filters {{ border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 0.2rem 0.55rem; font-size: 0.78rem; color: #334155; cursor: pointer; }}
  .clear-filters:hover {{ background: #f8fafc; }}
  .toggle-message-col {{ border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 0.2rem 0.55rem; font-size: 0.78rem; color: #334155; cursor: pointer; }}
  .toggle-message-col:hover {{ background: #f8fafc; }}
  .sbom-license-flagged {{ color: #b91c1c; font-weight: 700; }}
  .col-status {{ width: 1%; white-space: nowrap; }}
  .col-short {{ width: 1%; white-space: nowrap; }}
  .col-message {{ min-width: 24rem; width: 45%; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <h1>{escape(report_title)}</h1>

  {top_summary_cards_html}

  {dependencies_section_html}

  {advanced_help_section_html}

  {execution_section_html}

  {sbom_section_html}

  {needs_section_html}
  {arch2needs_section_html}

  {tests_section_html}
  {taco_section_html}
  {coverage_section_html}
  {static_findings_section_html}
  {log_findings_section_html}

  <script>
  (() => {{
    const FILTER_STORAGE_KEY = 'unified-report-column-filters-v1';
    const normalize = (value) => (value || '').toString().trim().toLowerCase();

    function loadAllSavedFilters() {{
      try {{
        const raw = localStorage.getItem(FILTER_STORAGE_KEY);
        if (!raw) {{
          return {{}};
        }}
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {{}};
      }} catch (error) {{
        return {{}};
      }}
    }}

    function saveAllSavedFilters(payload) {{
      try {{
        localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(payload));
      }} catch (error) {{
      }}
    }}

    function bindColumnFilters(tableId) {{
      const table = document.getElementById(tableId);
      if (!table) {{
        return;
      }}

      const countEl = document.querySelector(`.filter-count[data-table-id="${{tableId}}"]`);
      const clearButton = document.querySelector(`.clear-filters[data-table-id="${{tableId}}"]`);
      const rows = Array.from(table.querySelectorAll('tbody tr')).filter(
        (row) => !row.classList.contains('placeholder-row')
      );
      const filterNodes = Array.from(table.querySelectorAll('thead .col-filter'));
      const allSaved = loadAllSavedFilters();
      const savedForTable = (allSaved && allSaved[tableId]) || {{}};

      filterNodes.forEach((node) => {{
        const key = node.getAttribute('data-col') || '';
        if (!Object.prototype.hasOwnProperty.call(savedForTable, key)) {{
          return;
        }}

        const savedValue = savedForTable[key];
        if (node.tagName === 'SELECT' && node.multiple) {{
          const selectedValues = Array.isArray(savedValue)
            ? savedValue
            : (savedValue ? [savedValue] : []);
          const selectedSet = new Set(selectedValues.map((value) => String(value)));
          Array.from(node.options).forEach((option) => {{
            option.selected = selectedSet.has(option.value);
          }});
        }} else {{
          node.value = savedValue || '';
        }}
      }});

      function persistCurrentFilters() {{
        const nextSaved = loadAllSavedFilters();
        nextSaved[tableId] = {{}};
        filterNodes.forEach((node) => {{
          const key = node.getAttribute('data-col') || '';
          if (node.tagName === 'SELECT' && node.multiple) {{
            nextSaved[tableId][key] = Array.from(node.selectedOptions).map(
              (option) => option.value || ''
            );
          }} else {{
            nextSaved[tableId][key] = node.value || '';
          }}
        }});
        saveAllSavedFilters(nextSaved);
      }}

      function applyFilters() {{
        let visibleRows = 0;

        rows.forEach((row) => {{
          let isVisible = true;

          for (const node of filterNodes) {{
            const columnIndex = parseInt(node.getAttribute('data-col') || '-1', 10);
            const cell = columnIndex >= 0 ? row.cells[columnIndex] : null;
            const cellText = normalize(cell ? cell.textContent : '');

            if (node.tagName === 'SELECT' && node.multiple) {{
              const needles = Array.from(node.selectedOptions)
                .map((option) => normalize(option.value))
                .filter((value) => !!value);
              if (!needles.length) {{
                continue;
              }}
              if (!needles.some((needle) => cellText === needle || cellText.includes(needle))) {{
                isVisible = false;
                break;
              }}
              continue;
            }}

            const needle = normalize(node.value);
            if (!needle) {{
              continue;
            }}

            if (!cellText.includes(needle)) {{
              isVisible = false;
              break;
            }}
          }}

          row.style.display = isVisible ? '' : 'none';
          if (isVisible) {{
            visibleRows += 1;
          }}
        }});

        if (countEl) {{
          countEl.textContent = `${{visibleRows}}/${{rows.length}} shown`;
        }}

        persistCurrentFilters();
      }}

      filterNodes.forEach((node) => {{
        node.addEventListener('input', applyFilters);
        node.addEventListener('change', applyFilters);
      }});

      if (clearButton) {{
        clearButton.addEventListener('click', () => {{
          filterNodes.forEach((node) => {{
            if (node.tagName === 'SELECT' && node.multiple) {{
              Array.from(node.options).forEach((option) => {{
                option.selected = false;
              }});
            }} else {{
              node.value = '';
            }}
          }});
          applyFilters();
        }});
      }}

      applyFilters();
    }}

    function bindMessageColumnToggle(tableId, messageColIndex, forceVisible) {{
      const table = document.getElementById(tableId);
      if (!table) {{
        return;
      }}

      const button = document.querySelector(`.toggle-message-col[data-table-id="${{tableId}}"]`);
      if (!button) {{
        return;
      }}

      const dataRows = Array.from(table.querySelectorAll('tbody tr')).filter(
        (row) => !row.classList.contains('placeholder-row')
      );
      const hasAnyMessage = dataRows.some((row) => {{
        const cell = row.cells[messageColIndex];
        return normalize(cell ? cell.textContent : '') !== '';
      }});

      let isVisible = (typeof forceVisible === 'boolean') ? forceVisible : hasAnyMessage;

      function setVisibility(nextVisible) {{
        isVisible = !!nextVisible;
        const nth = messageColIndex + 1;
        table.querySelectorAll(`tr > :nth-child(${{nth}})`).forEach((cell) => {{
          cell.style.display = isVisible ? '' : 'none';
        }});
        button.textContent = isVisible ? 'Hide Message Column' : 'Show Message Column';
      }}

      button.addEventListener('click', () => {{
        setVisibility(!isVisible);
      }});

      setVisibility(isVisible);
    }}

    function bindNaColumnToggle(tableId, colIndex) {{
      const table = document.getElementById(tableId);
      if (!table) {{
        return;
      }}

      const button = document.querySelector(`.toggle-na-col[data-table-id="${{tableId}}"]`);
      if (!button) {{
        return;
      }}

      const dataRows = Array.from(table.querySelectorAll('tbody tr')).filter(
        (row) => !row.classList.contains('placeholder-row')
      );
      const allNa = dataRows.length > 0 && dataRows.every((row) => {{
        const cell = row.cells[colIndex];
        const value = normalize(cell ? cell.textContent : '');
        return value === '' || value === 'n.a.' || value === 'na';
      }});

      let isVisible = !allNa;

      function setVisibility(nextVisible) {{
        isVisible = !!nextVisible;
        const nth = colIndex + 1;
        table.querySelectorAll(`tr > :nth-child(${{nth}})`).forEach((cell) => {{
          cell.style.display = isVisible ? '' : 'none';
        }});

        const filterNode = table.querySelector(`thead .col-filter[data-col="${{colIndex}}"]`);
        if (!isVisible && filterNode && filterNode.value) {{
          filterNode.value = '';
          filterNode.dispatchEvent(new Event('change'));
        }}

        button.textContent = isVisible ? 'Hide Test Status Column' : 'Show Test Status Column';
      }}

      button.addEventListener('click', () => {{
        setVisibility(!isVisible);
      }});

      setVisibility(isVisible);
    }}

    bindColumnFilters('execution-table');
    bindColumnFilters('arch2needs-findings-table');
    bindColumnFilters('arch2needs-log-table');      bindColumnFilters('taco-results-table');    bindColumnFilters('coverage-table');
    bindColumnFilters('tests-table');
    bindColumnFilters('log-findings-table');
    bindColumnFilters('static-findings-table');
    bindColumnFilters('sbom-components-table');
    bindNaColumnToggle('execution-table', 3);
    bindMessageColumnToggle('tests-table', 5);
    bindMessageColumnToggle('log-findings-table', 5, true);
    bindMessageColumnToggle('static-findings-table', 4, true);
  }})();
  </script>
</body>
</html>
"""

        output_path.write_text(html, encoding='utf-8')
        return output_path.resolve()
