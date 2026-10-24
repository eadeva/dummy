"""Execution steps section renderer."""


def render_execution_section(
    execution_section_summary: str, execution_rows: list[str]
) -> str:
    return f"""
  <details class=\"report-section\">
    <summary>Execution Steps</summary>
    <div class=\"section-body\">
      {execution_section_summary}
      <div class=\"table-meta\">
        <button class=\"toggle-na-col\" data-table-id=\"execution-table\" data-col=\"3\" type=\"button\">Hide Test Status Column</button>
        <button class=\"clear-filters\" data-table-id=\"execution-table\" type=\"button\">Clear Filters</button>
        <span class=\"filter-count\" data-table-id=\"execution-table\"></span>
      </div>
      <div class=\"table-wrap\">
      <table id=\"execution-table\">
        <thead>
          <tr><th class=\"col-status\">Status</th><th>Step</th><th>Type</th><th>Test Status</th><th class=\"col-short\">Elapsed</th></tr>
          <tr class=\"column-filters\">
            <th>
              <select class=\"col-filter\" data-col=\"0\">
                <option value=\"\">All</option>
                <option value=\"success\">success</option>
                <option value=\"passed\">passed</option>
                <option value=\"failed\">failed</option>
                <option value=\"error\">error</option>
                <option value=\"skipped\">skipped</option>
                <option value=\"not_executed\">not_executed</option>
                <option value=\"user_interrupt\">user_interrupt</option>
              </select>
            </th>
            <th><input class=\"col-filter\" data-col=\"1\" placeholder=\"Filter step\" /></th>
            <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter type\" /></th>
            <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter test status\" /></th>
            <th><input class=\"col-filter\" data-col=\"4\" placeholder=\"Filter elapsed\" /></th>
          </tr>
        </thead>
        <tbody>
          {''.join(execution_rows) or '<tr class=\"placeholder-row\"><td colspan="5">No execution step artifacts</td></tr>'}
        </tbody>
      </table>
      </div>
    </div>
  </details>
"""
