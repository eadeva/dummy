"""Arch2Needs (architecture needs generation) section renderer."""

from html import escape


def _int_value(raw_value, default=0) -> int:
    try:
        return int(raw_value)
    except Exception:
        return default


def _options(values) -> str:
    return ''.join(
        f'<option value="{escape(value)}">{escape(value)}</option>'
        for value in sorted({str(value) for value in values if value}, key=str.lower)
    )


def render_arch2needs_section(arch2needs, status_class_fn) -> str:
    if not isinstance(arch2needs, dict) or not arch2needs.get('available'):
        return ''

    findings = [item for item in arch2needs.get('findings', []) or [] if isinstance(item, dict)]
    codes = [item for item in arch2needs.get('codes', []) or [] if isinstance(item, dict)]
    log_messages = [
        item for item in arch2needs.get('log_messages', []) or [] if isinstance(item, dict)
    ]
    level_counts = arch2needs.get('log_level_counts', {}) or {}
    errors = _int_value(arch2needs.get('errors', 0))
    warnings = _int_value(arch2needs.get('warnings', 0))
    log_errors = _int_value(level_counts.get('ERROR', 0)) + _int_value(
        level_counts.get('CRITICAL', 0)
    )
    log_warnings = _int_value(level_counts.get('WARNING', 0))

    def badge(severity: str) -> str:
        status_class = status_class_fn(
            'failed' if severity.lower() in {'error', 'critical'} else severity
        )
        return f'<span class="badge {status_class}">{escape(severity)}</span>'

    code_rows = [
        f'<tr><td class="col-short">{badge(str(item.get("severity", "")))}</td>'
        f'<td>{escape(str(item.get("code", "")))}</td>'
        f'<td class="col-short">{_int_value(item.get("count", 0))}</td></tr>'
        for item in codes
    ] or ['<tr class="placeholder-row"><td colspan="3">No findings</td></tr>']

    finding_rows = [
        f'<tr><td class="col-short">{badge(item.get("severity", ""))}</td>'
        f'<td>{escape(item.get("code", ""))}</td>'
        f'<td>{escape(item.get("file", ""))}</td>'
        f'<td>{escape(item.get("location", ""))}</td>'
        f'<td class="col-message">{escape(item.get("message", ""))}</td></tr>'
        for item in findings
    ] or ['<tr class="placeholder-row"><td colspan="5">No findings</td></tr>']

    log_rows = [
        f'<tr><td class="col-short">{escape(str(item.get("time", "")))}</td>'
        f'<td class="col-short">{badge(str(item.get("level", "")))}</td>'
        f'<td>{escape(str(item.get("logger", "")))}</td>'
        f'<td class="col-message">{escape(str(item.get("message", "")))}</td></tr>'
        for item in log_messages
    ] or ['<tr class="placeholder-row"><td colspan="4">No warnings or errors logged</td></tr>']
    truncated_note = (
        '<p>Only the first log messages are listed; see the log file for all.</p>'
        if arch2needs.get('log_messages_truncated')
        else ''
    )

    files_html = ''.join(
        f'<div><strong>{label}:</strong> <code>{escape(str(arch2needs.get(key)))}</code></div>'
        for label, key in (('Validation report', 'report_file'), ('Log file', 'log_file'))
        if arch2needs.get(key)
    )
    parse_errors_html = ''.join(
        f'<div class="card card-danger"><strong>{label}</strong><br />{escape(str(arch2needs[key]))}</div>'
        for label, key in (
            ('Validation report parse error', 'report_parse_error'),
            ('Log parse error', 'log_parse_error'),
        )
        if arch2needs.get(key)
    )

    return f"""
  <details class=\"report-section\">
    <summary>Architecture Needs (arch2needs)</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-danger\"><strong>Model Errors</strong><br />{errors}</div>
        <div class=\"card card-warn\"><strong>Model Warnings</strong><br />{warnings}</div>
        <div class=\"card card-danger\"><strong>Log Errors</strong><br />{log_errors}</div>
        <div class=\"card card-warn\"><strong>Log Warnings</strong><br />{log_warnings}</div>
        {parse_errors_html}
      </div>
      <div class=\"table-meta\" style=\"justify-content: flex-start; flex-direction: column; align-items: flex-start;\">{files_html}</div>

      <details class=\"report-subsection\" open>
        <summary>Validation Findings by Code</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap compact-wrap\">
          <table>
            <thead><tr><th class=\"col-short\">Severity</th><th>Code</th><th class=\"col-short\">Count</th></tr></thead>
            <tbody>{''.join(code_rows)}</tbody>
          </table>
          </div>
        </div>
      </details>

      <details class=\"report-subsection\">
        <summary>Validation Findings</summary>
        <div class=\"section-body\">
          <div class=\"table-meta\">
            <button class=\"clear-filters\" data-table-id=\"arch2needs-findings-table\" type=\"button\">Clear Filters</button>
            <span class=\"filter-count\" data-table-id=\"arch2needs-findings-table\"></span>
          </div>
          <div class=\"table-wrap\">
          <table id=\"arch2needs-findings-table\">
            <thead>
              <tr><th class=\"col-short\">Severity</th><th>Code</th><th>File</th><th>Location</th><th class=\"col-message\">Message</th></tr>
              <tr class=\"column-filters\">
                <th><select class=\"col-filter\" data-col=\"0\"><option value=\"\">All</option>{_options(item.get('severity') for item in findings)}</select></th>
                <th><select class=\"col-filter\" data-col=\"1\"><option value=\"\">All</option>{_options(item.get('code') for item in findings)}</select></th>
                <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter file\" /></th>
                <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter location\" /></th>
                <th><input class=\"col-filter\" data-col=\"4\" placeholder=\"Filter message\" /></th>
              </tr>
            </thead>
            <tbody>{''.join(finding_rows)}</tbody>
          </table>
          </div>
        </div>
      </details>

      <details class=\"report-subsection\">
        <summary>Log Warnings and Errors</summary>
        <div class=\"section-body\">
          {truncated_note}
          <div class=\"table-meta\">
            <button class=\"clear-filters\" data-table-id=\"arch2needs-log-table\" type=\"button\">Clear Filters</button>
            <span class=\"filter-count\" data-table-id=\"arch2needs-log-table\"></span>
          </div>
          <div class=\"table-wrap\">
          <table id=\"arch2needs-log-table\">
            <thead>
              <tr><th class=\"col-short\">Time</th><th class=\"col-short\">Level</th><th>Logger</th><th class=\"col-message\">Message</th></tr>
              <tr class=\"column-filters\">
                <th><input class=\"col-filter\" data-col=\"0\" placeholder=\"Filter time\" /></th>
                <th><select class=\"col-filter\" data-col=\"1\"><option value=\"\">All</option>{_options(item.get('level') for item in log_messages)}</select></th>
                <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter logger\" /></th>
                <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter message\" /></th>
              </tr>
            </thead>
            <tbody>{''.join(log_rows)}</tbody>
          </table>
          </div>
        </div>
      </details>
    </div>
  </details>
"""
