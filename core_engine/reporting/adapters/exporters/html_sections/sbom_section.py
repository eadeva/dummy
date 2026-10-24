"""CycloneDX SBOM section renderer."""

from html import escape


def _render_uncovered(sbom_discovery: dict) -> tuple:
    """Card and subsection for the build input folders without a component manifest."""
    uncovered = sbom_discovery.get('uncovered_dirs', [])
    if not isinstance(uncovered, list):
        uncovered = []
    card_class = 'card-warn' if uncovered else 'card-neutral'
    card = f'<div class="card {card_class}"><strong>Uncovered Paths</strong><br />{len(uncovered)}</div>'
    entries = [item if isinstance(item, dict) else {'path': item} for item in uncovered]
    rows = ''.join(
        f'<tr><td>{escape(str(item.get("path", "")))}</td><td>{escape(str(item.get("files") or "-"))}</td></tr>'
        for item in entries
    ) or (
        '<tr class="placeholder-row"><td colspan="2">The SBOM discovery found a component manifest for every build input path</td></tr>'
    )
    ignored = int(sbom_discovery.get('uncovered_ignored_files', 0) or 0)
    ignored_note = (
        f' {ignored} file(s) are ignored by <code>uncovered_ignore</code>.' if ignored else ''
    )
    subsection = f"""
      <details class=\"report-subsection\">
        <summary>Uncovered Paths</summary>
        <div class=\"section-body\">
          <p>The SBOM discovery didn't find any component manifest for these build input paths; they are only covered by the project manifest.{ignored_note}</p>
          <div class=\"table-wrap\">
            <table id=\"sbom-uncovered-table\">
              <thead><tr><th>Folder</th><th>Files</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        </div>
      </details>"""
    return card, subsection


def render_sbom_section(cyclonedx, sbom_discovery=None) -> str:
    has_cyclonedx = isinstance(cyclonedx, dict) and bool(cyclonedx.get('available'))
    has_discovery = isinstance(sbom_discovery, dict) and bool(sbom_discovery.get('available'))
    if not has_cyclonedx and not has_discovery:
        return ''
    uncovered_card, uncovered_subsection = (
        _render_uncovered(sbom_discovery) if has_discovery else ('', '')
    )
    if not has_cyclonedx:
        return f"""
  <details class=\"report-section\">
    <summary>SBOM</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        {uncovered_card}
      </div>
{uncovered_subsection}
    </div>
  </details>
"""

    components = cyclonedx.get('components', [])
    if not isinstance(components, list):
        components = []

    type_values = sorted(
        {
            str(item.get('type', '') or '').strip()
            for item in components
            if isinstance(item, dict) and str(item.get('type', '') or '').strip()
        },
        key=lambda value: value.lower(),
    )
    type_options_html = ''.join(
        f'<option value="{escape(value)}">{escape(value)}</option>' for value in type_values
    )

    supplier_values = sorted(
        {
            str(item.get('supplier', '') or '').strip()
            for item in components
            if isinstance(item, dict) and str(item.get('supplier', '') or '').strip()
        },
        key=lambda value: value.lower(),
    )
    supplier_options_html = ''.join(
        f'<option value="{escape(value)}">{escape(value)}</option>' for value in supplier_values
    )

    flagged_options_html = ''.join(
        [
            '<option value="yes">yes</option>',
            '<option value="no">no</option>',
        ]
    )

    def _render_licenses_cell(item: dict) -> str:
        licenses_text = str(item.get('licenses', '') or '').strip()
        if not licenses_text:
            return '-'

        flagged_licenses = item.get('flagged_licenses', [])
        if not isinstance(flagged_licenses, list):
            flagged_licenses = []
        flagged_set = {
            str(name).strip().lower() for name in flagged_licenses if str(name or '').strip()
        }

        license_parts = [part.strip() for part in licenses_text.split(',') if part.strip()]
        if not license_parts:
            return escape(licenses_text)

        rendered_parts = []
        for part in license_parts:
            safe_part = escape(part)
            if part.lower() in flagged_set:
                rendered_parts.append(f'<span class="sbom-license-flagged">{safe_part}</span>')
            else:
                rendered_parts.append(safe_part)
        return ', '.join(rendered_parts)

    component_rows = []
    for item in components:
        if not isinstance(item, dict):
            continue

        depth = str(item.get('depth', '0') or '0').strip()
        name = str(item.get('name', '') or '').strip() or '-'
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' * max(0, int(depth or '0'))
        flagged_value = 'yes' if bool(item.get('flagged')) else 'no'

        component_rows.append(
            f'<tr>'
            f'<td>{escape(str(item.get("type", "") or "-"))}</td>'
            f'<td>{flagged_value}</td>'
            f'<td>{indent}{escape(name)}</td>'
            f'<td>{escape(str(item.get("version", "") or "-"))}</td>'
            f'<td>{escape(str(item.get("supplier", "") or "-"))}</td>'
            f'<td>{_render_licenses_cell(item)}</td>'
            f'</tr>'
        )

    if not component_rows:
        component_rows.append('<tr class="placeholder-row"><td colspan="6">No components</td></tr>')

    flagged_components_total = int(cyclonedx.get('flagged_components_total', 0) or 0)

    return f"""
  <details class=\"report-section\">
    <summary>SBOM</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-info\"><strong>BOM Format</strong><br />{escape(str(cyclonedx.get('bom_format', '') or '-'))}</div>
        <div class=\"card card-info\"><strong>Spec Version</strong><br />{escape(str(cyclonedx.get('spec_version', '') or '-'))}</div>
        <div class=\"card card-info\"><strong>Manufacturer</strong><br />{escape(str(cyclonedx.get('manufacturer', '') or '-'))}</div>
        <div class=\"card card-neutral\"><strong>Components</strong><br />{int(cyclonedx.get('components_total', 0) or 0)}</div>
        <div class=\"card card-neutral\"><strong>Suppliers</strong><br />{int(cyclonedx.get('suppliers_total', 0) or 0)}</div>
        <div class=\"card card-neutral\"><strong>Licenses</strong><br />{int(cyclonedx.get('licenses_total', 0) or 0)}</div>
        <div class=\"card card-danger\"><strong>Flagged Components</strong><br />{flagged_components_total}</div>
        {uncovered_card}
      </div>

      <details class=\"report-subsection\">
        <summary>Components</summary>
        <div class=\"section-body\">
          <div class=\"table-meta\">
            <button class=\"clear-filters\" data-table-id=\"sbom-components-table\" type=\"button\">Clear Filters</button>
            <span class=\"filter-count\" data-table-id=\"sbom-components-table\"></span>
          </div>
          <div class=\"table-wrap\">
            <table id=\"sbom-components-table\">
              <thead>
                <tr><th>Type</th><th>Flagged</th><th>Name</th><th>Version</th><th>Supplier</th><th>Licenses</th></tr>
                <tr class=\"column-filters\">
                  <th>
                    <select class=\"col-filter\" data-col=\"0\">
                      <option value=\"\">All</option>
                      {type_options_html}
                    </select>
                  </th>
                  <th>
                    <select class=\"col-filter\" data-col=\"1\">
                      <option value=\"\">All</option>
                      {flagged_options_html}
                    </select>
                  </th>
                  <th><input class=\"col-filter\" data-col=\"2\" placeholder=\"Filter name\" /></th>
                  <th><input class=\"col-filter\" data-col=\"3\" placeholder=\"Filter version\" /></th>
                  <th>
                    <select class=\"col-filter\" data-col=\"4\">
                      <option value=\"\">All</option>
                      {supplier_options_html}
                    </select>
                  </th>
                  <th><input class=\"col-filter\" data-col=\"5\" placeholder=\"Filter license\" /></th>
                </tr>
              </thead>
              <tbody>
                {''.join(component_rows)}
              </tbody>
            </table>
          </div>
        </div>
      </details>
{uncovered_subsection}
    </div>
  </details>
"""
