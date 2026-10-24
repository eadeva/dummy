"""Coverage section renderer."""


def render_coverage_section(
    has_coverage: bool,
    coverage_sources_count: int,
    coverage_cards: list[str],
    coverage_rows: list[str],
) -> str:
    if not has_coverage:
        return ''

    table_html = ''
    if coverage_rows:
        table_html = f"""
      <details style="margin-top: 1.5rem;" open>
        <summary style="font-weight: bold; cursor: pointer; outline: none; margin-bottom: 0.5rem; user-select: none;">File Details</summary>
        <div class="table-meta">
          <span class="filter-count" data-table-id="coverage-table">Showing all {len(coverage_rows)} file(s)</span>
          <button class="clear-filters btn-text" data-table-id="coverage-table" style="display: none;">Clear filters</button>
        </div>
        <div class="table-wrap">
        <table id="coverage-table">
          <thead>
            <tr>
              <th>Source File</th>
              <th class="col-short">Lines</th>
              <th class="col-short">Branches</th>
              <th class="col-short">Functions</th>
            </tr>
            <tr class="column-filters">
              <th><input class="col-filter" data-col="0" placeholder="Filter file" /></th>
              <th><input class="col-filter" data-col="1" placeholder="Filter lines" /></th>
              <th><input class="col-filter" data-col="2" placeholder="Filter branches" /></th>
              <th><input class="col-filter" data-col="3" placeholder="Filter functions" /></th>
            </tr>
          </thead>
          <tbody>
            {''.join(coverage_rows)}
          </tbody>
        </table>
        </div>
      </details>
"""

    return f"""
  <details class="report-section">
    <summary>Coverage</summary>
    <div class="section-body">
      <div class="section-summary">
        <div class="card card-info"><strong>Coverage Sources</strong><br />{coverage_sources_count}</div>
      </div>
      <div class="coverage-grid">{''.join(coverage_cards)}</div>
      {table_html}
    </div>
  </details>
"""
