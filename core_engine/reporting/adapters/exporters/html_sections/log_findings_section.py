"""Log findings section renderer."""


def render_log_findings_section(
    has_log_findings: bool,
    findings_total: int,
    log_exceptions: int,
    log_errors: int,
    log_warnings: int,
    log_classification_options_html: str,
    log_findings_rows: list[str],
) -> str:
    if not has_log_findings:
        return ''

    return f"""
  <details class=\"report-section\">
    <summary>Log Analyzer</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-neutral\"><strong>Total Findings</strong><br />{findings_total}</div>
        <div class=\"card card-danger\"><strong>Exceptions</strong><br />{log_exceptions}</div>
        <div class=\"card card-danger\"><strong>Errors</strong><br />{log_errors}</div>
        <div class=\"card card-warn\"><strong>Warnings</strong><br />{log_warnings}</div>
      </div>
      <div class=\"table-meta\">
        <button class=\"toggle-message-col\" data-table-id=\"log-findings-table\" data-message-col=\"5\" type=\"button\">Hide Message Column</button>
        <button class=\"clear-filters\" data-table-id=\"log-findings-table\" type=\"button\">Clear Filters</button>
        <span class=\"filter-count\" data-table-id=\"log-findings-table\"></span>
      </div>
      <div class=\"table-wrap\">
      <table id=\"log-findings-table\">
        <thead>
          <tr><th>Step</th><th>Type</th><th>Classification</th><th>File</th><th class=\"col-short\">Line</th><th class=\"col-message\">Message</th></tr>
          <tr class=\"column-filters\">
            <th><input class=\"col-filter\" data-col=\"0\" placeholder=\"Filter step\" /></th>
            <th>
              <select class=\"col-filter\" data-col=\"1\">
                <option value=\"\">All</option>
                <option value=\"exception\">exception</option>
                <option value=\"error\">error</option>
                <option value=\"warning\">warning</option>
              </select>
            </th>
            <th>
              <select class=\"col-filter\" data-col=\"2\">
                <option value=\"\">All</option>
                {log_classification_options_html}
              </select>
            </th>
            <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter file\" /></th>
            <th><input class=\"col-filter\" data-col=\"4\" placeholder=\"Filter line\" /></th>
            <th><input class=\"col-filter\" data-col=\"5\" placeholder=\"Filter message\" /></th>
          </tr>
        </thead>
        <tbody>
          {''.join(log_findings_rows)}
        </tbody>
      </table>
      </div>
    </div>
  </details>
"""
