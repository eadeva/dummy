"""Needs analysis section renderer."""

from html import escape


def render_needs_section(needs_analysis) -> str:
    if not isinstance(needs_analysis, dict) or not needs_analysis.get(
        'available'
    ):
        return ''

    def _int_value(raw_value, default=0):
        try:
            return int(raw_value)
        except Exception:
            return default

    requirements_total = _int_value(
        needs_analysis.get('requirements_total', 0), 0
    )
    req_requirements_total = _int_value(
        needs_analysis.get('req_requirements_total', 0),
        0,
    )
    validated_needs = _int_value(
        needs_analysis.get('validated_needs_count', 0), 0
    )
    validated_per_second = _int_value(
        needs_analysis.get('validated_needs_per_second', 0),
        0,
    )
    violations_total = _int_value(needs_analysis.get('violations_total', 0), 0)

    def _to_count_rows(rows):
        normalized = []
        if not isinstance(rows, list):
            return normalized
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('name', '') or '').strip() or '-'
            count = _int_value(row.get('count', 0), 0)
            if count <= 0:
                continue
            normalized.append((name, count))
        return normalized

    req_type_counts = _to_count_rows(needs_analysis.get('req_type_counts', []))
    req_status_counts = _to_count_rows(
        needs_analysis.get('req_status_counts', [])
    )
    req_status_total = _int_value(needs_analysis.get('req_status_total', 0), 0)
    if req_status_total <= 0:
        req_status_total = sum(count for _, count in req_status_counts)
    if req_status_total <= 0:
        req_status_total = req_requirements_total

    req_type_cards = [
        f'<div class="card card-info"><strong>{escape(name)}</strong><br />{count}</div>'
        for name, count in req_type_counts
    ]
    if not req_type_cards:
        req_type_cards = [
            '<div class="card card-neutral"><strong>Req-* Types</strong><br />No data</div>'
        ]

    status_palette = [
        '#64748b',
        '#2563eb',
        '#0ea5e9',
        '#14b8a6',
    ]

    status_color_map = {
        'accepted': '#16a34a',
        'under review': '#84cc16',
        'in clarification': '#f59e0b',
        'obsolete': '#f97316',
        'rejected': '#dc2626',
        'draft': '#b91c1c',
        '(empty)': '#6b7280',
        'none': '#6b7280',
        'unknown': '#6b7280',
    }

    def _status_color(name, index):
        normalized = str(name or '').strip().lower()
        if normalized in status_color_map:
            return status_color_map[normalized]
        return status_palette[index % len(status_palette)]

    def _build_donut_card(name, count, total, color):
        pct = 0.0
        if total > 0:
            pct = (float(count) * 100.0) / float(total)
        return (
            f'<div class="metric-card">'
            f'<div class="donut" style="--p:{pct:.1f};--c:{color};">'
            f'<div class="donut-value">{pct:.1f}%</div>'
            f'</div>'
            f'<div class="metric-label">{escape(str(name))}</div>'
            f'<div class="metric-ratio">{int(count)}/{int(total) if int(total) > 0 else 0}</div>'
            f'</div>'
        )

    def _build_distribution_cards(rows, total):
        cards = []
        for idx, (name, count) in enumerate(rows):
            cards.append(
                _build_donut_card(
                    name=name,
                    count=count,
                    total=total,
                    color=_status_color(name, idx),
                )
            )
        if not cards:
            cards = [
                '<div class="metric-card"><div class="metric-label">No data</div></div>'
            ]
        return cards

    total_status_cards_html = ''.join(
        _build_distribution_cards(req_status_counts, req_status_total)
    )

    req_status_by_type = []
    req_status_by_type_raw = needs_analysis.get('req_status_by_type', [])
    if isinstance(req_status_by_type_raw, list):
        for item in req_status_by_type_raw:
            if not isinstance(item, dict):
                continue
            req_type_name = str(item.get('type', '') or '').strip()
            if not req_type_name:
                continue
            rows = _to_count_rows(item.get('status_counts', []))
            total = _int_value(item.get('total', 0), 0)
            if total <= 0:
                total = sum(count for _, count in rows)
            if total <= 0:
                continue
            req_status_by_type.append((req_type_name, rows, total))

    req_type_status_lines_html = ''.join(
        f"<div class=\"req-type-status-row\">"
        f"<div class=\"req-type-status-title\">{escape(req_type_name)} by Status</div>"
        f"<div class=\"coverage-grid\">{''.join(_build_distribution_cards(rows, total))}</div>"
        f"</div>"
        for req_type_name, rows, total in req_status_by_type
    )

    if not req_type_status_lines_html:
        req_type_status_lines_html = '<div class="metric-card"><div class="metric-label">No req-* type status data</div></div>'

    status_overview_html = f"""
          <div class=\"pie-charts-grid\">
            <div class=\"diagram-block\">
              <div class=\"pie-row-title\">Requirements by Status</div>
              <div class=\"coverage-grid\">{total_status_cards_html}</div>
            </div>
          </div>
          <div class=\"pie-row-title\">Requirements Breakdown</div>
          <div class=\"req-type-status-lines\">
            {req_type_status_lines_html}
          </div>
"""

    violations = needs_analysis.get('violations', [])
    violations_rows_html = ''
    if isinstance(violations, list) and violations:
        rows = []
        for item in violations:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '') or '').strip() or '-'
            count = _int_value(item.get('count', 0), 0)
            sample = str(item.get('sample', '') or '').strip() or '-'
            rows.append(
                f'<tr><td>{escape(name)}</td><td class="col-short">{count}</td><td>{escape(sample)}</td></tr>'
            )
        violations_rows_html = ''.join(rows)

    needs_errors = []
    needs_parse_error = str(
        needs_analysis.get('needs_parse_error', '') or ''
    ).strip()
    violations_parse_error = str(
        needs_analysis.get('violations_parse_error', '') or ''
    ).strip()
    if needs_parse_error:
        needs_errors.append(
            f'<div class="card card-danger"><strong>needs.json parse error</strong><br />{escape(needs_parse_error)}</div>'
        )
    if violations_parse_error:
        needs_errors.append(
            f'<div class="card card-danger"><strong>schema_violations.json parse error</strong><br />{escape(violations_parse_error)}</div>'
        )

    if not violations_rows_html:
        violations_rows_html = '<tr class="placeholder-row"><td colspan="3">No schema violations</td></tr>'
    violations_subsection_html = f"""
      <details class=\"report-subsection\">
        <summary>Violations</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap compact-wrap\">
          <table>
            <thead>
              <tr><th>Name</th><th class=\"col-short\">Count</th><th>Sample</th></tr>
            </thead>
            <tbody>
              {violations_rows_html}
            </tbody>
          </table>
          </div>
        </div>
      </details>
"""

    requirements_overview_subsection_html = f"""
      <details class=\"report-subsection\">
        <summary>Requirements Overview</summary>
        <div class=\"section-body\">
          <div class=\"section-summary\">
            <div class=\"card card-neutral\"><strong>Requirements</strong><br />{req_requirements_total}</div>
            {''.join(req_type_cards)}
          </div>
          {status_overview_html}
        </div>
      </details>
"""

    return f"""
  <details class=\"report-section\">
    <summary>Needs Analysis</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-neutral\"><strong>Total Needs</strong><br />{requirements_total}</div>
        <div class=\"card card-neutral\"><strong>Requirements</strong><br />{req_requirements_total}</div>
        <div class=\"card card-neutral\"><strong>Validated Needs</strong><br />{validated_needs}</div>
        <div class=\"card card-neutral\"><strong>Validation Speed</strong><br />{validated_per_second} / s</div>
        <div class=\"card card-danger\"><strong>Violations</strong><br />{violations_total}</div>
      </div>
      {''.join(needs_errors)}
      {violations_subsection_html}
      {requirements_overview_subsection_html}
    </div>
  </details>
"""
