"""Test cases section renderer."""

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


def render_tests_section(
    has_test_cases: bool,
    report: CanonicalReport,
    test_rows: list[str],
) -> str:
    if not has_test_cases:
        return ''

    return f"""
  <details class=\"report-section\">
    <summary>Test Cases</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-neutral\"><strong>Tests</strong><br />{report.total_tests}</div>
        <div class=\"card card-danger\"><strong>Failures</strong><br />{report.total_failures}</div>
        <div class=\"card card-danger\"><strong>Errors</strong><br />{report.total_errors}</div>
        <div class=\"card card-warn\"><strong>Skipped</strong><br />{report.total_skipped}</div>
      </div>
      <div class=\"table-meta\">
        <button class=\"toggle-message-col\" data-table-id=\"tests-table\" data-message-col=\"5\" type=\"button\">Hide Message Column</button>
        <button class=\"clear-filters\" data-table-id=\"tests-table\" type=\"button\">Clear Filters</button>
        <span class=\"filter-count\" data-table-id=\"tests-table\"></span>
      </div>
      <div class=\"table-wrap\">
      <table id=\"tests-table\">
        <thead>
          <tr><th class=\"col-status\">Status</th><th>Suite</th><th>Class</th><th>Name</th><th class=\"col-short\">Time (s)</th><th class=\"col-message\">Message</th><th>Test Specification</th></tr>
          <tr class=\"column-filters\">
            <th>
              <select class=\"col-filter\" data-col=\"0\">
                <option value=\"\">All</option>
                <option value=\"passed\">passed</option>
                <option value=\"failed\">failed</option>
                <option value=\"error\">error</option>
                <option value=\"skipped\">skipped</option>
              </select>
            </th>
            <th><input class=\"col-filter\" data-col=\"1\" placeholder=\"Filter suite\" /></th>
            <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter class\" /></th>
            <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter name\" /></th>
            <th><input class=\"col-filter\" data-col=\"4\" placeholder=\"Filter time\" /></th>
            <th><input class=\"col-filter\" data-col=\"5\" placeholder=\"Filter message\" /></th>
            <th><input class=\"col-filter\" data-col=\"6\" placeholder=\"Filter spec\" /></th>
          </tr>
        </thead>
        <tbody>
          {''.join(test_rows)}
        </tbody>
      </table>
      </div>
    </div>
  </details>
"""
