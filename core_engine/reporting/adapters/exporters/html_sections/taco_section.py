"""TACO (test selection verdicts) section renderer."""

from html import escape

_PASSED = {'passed'}
_FAILED = {'failed', 'error', 'blocked'}


def _verdict_status(verdict: str) -> str:
    lowered = verdict.lower()
    if lowered in _PASSED:
        return 'passed'
    if lowered in _FAILED:
        return 'failed'
    return 'skipped'


def _options(values) -> str:
    return ''.join(
        f'<option value="{escape(value)}">{escape(value)}</option>'
        for value in sorted({str(value) for value in values if value}, key=str.lower)
    )


def render_taco_section(taco, status_class_fn) -> str:
    if not isinstance(taco, dict) or not taco.get('available'):
        return ''

    selections = [item for item in taco.get('selections', []) or [] if isinstance(item, dict)]
    results = [
        {**result, 'selection': selection.get('selection', '')}
        for selection in selections
        for result in selection.get('results', []) or []
    ]
    counts: dict = {}
    for result in results:
        status = _verdict_status(result.get('verdict', ''))
        counts[status] = counts.get(status, 0) + 1

    def badge(verdict: str) -> str:
        return f'<span class="badge {status_class_fn(_verdict_status(verdict))}">{escape(verdict)}</span>'

    selection_rows = [
        f'<tr><td>{escape(item.get("selection", ""))}</td><td>{escape(item.get("variant", ""))}</td>'
        f'<td>{escape(", ".join(f"{k}: {v}" for k, v in sorted((item.get("counts") or {}).items())))}</td>'
        f'<td>{escape(item.get("parse_error", ""))}</td></tr>'
        for item in selections
    ] or ['<tr class="placeholder-row"><td colspan="4">No test selections</td></tr>']

    result_rows = [
        f'<tr><td>{escape(item.get("selection", ""))}</td><td>{escape(item.get("test_case", ""))}</td>'
        f'<td class="col-short">{badge(item.get("verdict", ""))}</td></tr>'
        for item in results
    ] or ['<tr class="placeholder-row"><td colspan="3">No test verdicts</td></tr>']
    selection_options = _options(item.get('selection') for item in results)
    verdict_options = _options(item.get('verdict') for item in results)

    return f"""
  <details class=\"report-section\">
    <summary>Test Selections (TACO)</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-info\"><strong>Passed</strong><br />{counts.get('passed', 0)}</div>
        <div class=\"card card-danger\"><strong>Failed</strong><br />{counts.get('failed', 0)}</div>
        <div class=\"card card-warn\"><strong>Not executed / other</strong><br />{counts.get('skipped', 0)}</div>
      </div>

      <details class=\"report-subsection\" open>
        <summary>Selections</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap compact-wrap\">
          <table>
            <thead><tr><th>Selection</th><th>Variant</th><th>Verdicts</th><th>Parse error</th></tr></thead>
            <tbody>{''.join(selection_rows)}</tbody>
          </table>
          </div>
        </div>
      </details>

      <details class=\"report-subsection\">
        <summary>Test Case Verdicts</summary>
        <div class=\"section-body\">
          <div class=\"table-meta\">
            <button class=\"clear-filters\" data-table-id=\"taco-results-table\" type=\"button\">Clear Filters</button>
            <span class=\"filter-count\" data-table-id=\"taco-results-table\"></span>
          </div>
          <div class=\"table-wrap\">
          <table id=\"taco-results-table\">
            <thead>
              <tr><th>Selection</th><th>Test Case</th><th class=\"col-short\">Verdict</th></tr>
              <tr class=\"column-filters\">
                <th><select class=\"col-filter\" data-col=\"0\"><option value=\"\">All</option>{selection_options}</select></th>
                <th><input class=\"col-filter\" data-col=\"1\" placeholder=\"Filter test case\" /></th>
                <th><select class=\"col-filter\" data-col=\"2\"><option value=\"\">All</option>{verdict_options}</select></th>
              </tr>
            </thead>
            <tbody>{''.join(result_rows)}</tbody>
          </table>
          </div>
        </div>
      </details>
    </div>
  </details>
"""
