"""Static findings section renderer."""

from html import escape


def render_static_findings_section(
    has_static_findings: bool,
    static_section_title: str,
    findings_total: int,
    static_severity_cards_html: str,
    static_producer_table_html: str,
    static_severity_options_html: str,
    static_findings_rows: list[str],
) -> str:
    if not has_static_findings:
        return ''

    return f"""
  <details class=\"report-section\">
    <summary>{escape(static_section_title)}</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-danger\"><strong>Total Violations</strong><br />{findings_total}</div>
        {static_severity_cards_html}
      </div>
      {static_producer_table_html}
      <div class=\"table-meta\">
        <button class=\"toggle-message-col\" data-table-id=\"static-findings-table\" data-message-col=\"4\" type=\"button\">Hide Message Column</button>
        <button class=\"clear-filters\" data-table-id=\"static-findings-table\" type=\"button\">Clear Filters</button>
        <span class=\"filter-count\" data-table-id=\"static-findings-table\"></span>
      </div>
      <div class=\"table-wrap\">
      <table id=\"static-findings-table\">
        <thead>
          <tr><th>Filename</th><th class=\"col-short\">Line number</th><th class=\"col-short\">Column number</th><th>Producer component:Message number</th><th class=\"col-message\">Message text</th><th>Criticality</th><th>Severity</th><th>Suppression type bitmask</th><th>Suppression justification</th><th>Rule Group</th><th>Rule Scope</th><th>Rule Text</th></tr>
          <tr class=\"column-filters\">
            <th><input class=\"col-filter\" data-col=\"0\" placeholder=\"Filter filename\" /></th>
            <th><input class=\"col-filter\" data-col=\"1\" placeholder=\"Filter line\" /></th>
            <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter column\" /></th>
            <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter producer/message\" /></th>
            <th><input class=\"col-filter\" data-col=\"4\" placeholder=\"Filter message text\" /></th>
            <th><input class=\"col-filter\" data-col=\"5\" placeholder=\"Filter criticality\" /></th>
            <th>
              <select class=\"col-filter\" data-col=\"6\">
                <option value=\"\">All</option>
                {static_severity_options_html}
              </select>
            </th>
            <th><input class=\"col-filter\" data-col=\"7\" placeholder=\"Filter suppression type\" /></th>
            <th><input class=\"col-filter\" data-col=\"8\" placeholder=\"Filter suppression justification\" /></th>
            <th><input class=\"col-filter\" data-col=\"9\" placeholder=\"Filter rule group\" /></th>
            <th><input class=\"col-filter\" data-col=\"10\" placeholder=\"Filter rule scope\" /></th>
            <th><input class=\"col-filter\" data-col=\"11\" placeholder=\"Filter rule text\" /></th>
          </tr>
        </thead>
        <tbody>
          {''.join(static_findings_rows)}
        </tbody>
      </table>
      </div>
    </div>
  </details>
"""
