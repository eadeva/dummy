"""Shared Markdown rendering utilities."""

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    CoverageSummary,
    Finding,
    LogFinding,
)

_SEVERITIES = ('critical', 'high', 'medium', 'low', 'warning', 'info', 'unknown')


def _log_type_to_severity(log_type: str) -> str:
    normalized = str(log_type or '').strip().lower()
    if normalized == 'critical':
        return 'critical'
    if normalized in {'high', 'error', 'exception', 'fatal'}:
        return 'high'
    if normalized == 'medium':
        return 'medium'
    if normalized == 'low':
        return 'low'
    if normalized in {'warning', 'warn'}:
        return 'warning'
    if normalized in {'info', 'information', 'notice', 'debug', 'trace'}:
        return 'info'
    return 'unknown'


def escape_markdown(value: object) -> str:
    text = '' if value is None else str(value)
    escaped = text.replace('\\', '\\\\').replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')
    return escaped.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')


def render_table(headers: list[str], rows: list[list[object]]) -> str:
    escaped_headers = [escape_markdown(item) for item in headers]
    lines = [f"| {' | '.join(escaped_headers)} |", f"| {' | '.join('---' for _ in headers)} |"]
    lines.extend(f"| {' | '.join(escape_markdown(item) for item in row)} |" for row in rows)
    return '\n'.join(lines)


def _percentage(covered: int, total: int) -> float | None:
    return round(covered * 100.0 / total, 2) if total else None


def aggregate_coverage(entries: list[CoverageSummary]) -> dict[str, float | int | None]:
    totals = {
        'lines_total': sum(item.lines_total for item in entries),
        'lines_covered': sum(item.lines_covered for item in entries),
        'branches_total': sum(item.branches_total for item in entries),
        'branches_covered': sum(item.branches_covered for item in entries),
        'functions_total': sum(item.functions_total or 0 for item in entries),
        'functions_covered': sum(item.functions_covered or 0 for item in entries),
    }
    totals['line_coverage_pct'] = _percentage(totals['lines_covered'], totals['lines_total'])
    totals['branch_coverage_pct'] = _percentage(totals['branches_covered'], totals['branches_total'])
    totals['function_coverage_pct'] = _percentage(totals['functions_covered'], totals['functions_total'])
    return totals


def severity_counts(items: list[Finding | LogFinding]) -> dict[str, int]:
    counts = dict.fromkeys(_SEVERITIES, 0)
    for item in items:
        if isinstance(item, LogFinding):
            value = _log_type_to_severity(item.type)
        else:
            value = str(getattr(item, 'severity', '')).strip().lower() or 'unknown'
        counts[value if value in counts else 'unknown'] += 1
    return counts


def overall_status(report: CanonicalReport) -> str:
    static = severity_counts(report.findings)
    if report.failed_execution_steps or report.total_failures or report.total_errors or static['critical'] or static['high']:
        return 'FAILED'
    non_passing = any(case.status.lower() not in {'passed', 'success'} for suite in report.test_suites for case in suite.test_cases)
    logs = severity_counts(report.log_findings)
    has_warning_finding = any(static[level] for level in ('medium', 'warning'))
    has_warning_log_finding = any(logs[level] for level in ('critical', 'high', 'medium', 'warning'))
    if non_passing or has_warning_finding or has_warning_log_finding:
        return 'WARNING'
    return 'PASSED'
