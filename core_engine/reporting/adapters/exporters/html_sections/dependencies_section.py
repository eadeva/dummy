"""Dependencies/downloads section renderer."""

from html import escape


def render_dependencies_section(
    metadata: dict,
) -> str:
    def _normalize_dependency_items(items):
        normalized = []
        if not isinstance(items, list):
            return normalized
        for item in items:
            if not isinstance(item, dict):
                continue
            properties = {
                str(k): str(v)
                for k, v in (item.get('properties', {}) or {}).items()
            }
            normalized.append(
                {
                    'name': str(item.get('name', '')).strip(),
                    'type': str(item.get('type', '')).strip(),
                    'version': str(item.get('version', '')).strip(),
                    'properties': properties,
                    'repository': str(item.get('repository', '')).strip(),
                    'repository_type': str(
                        item.get('repository_type', '')
                    ).strip(),
                    'source': str(item.get('source', '')).strip(),
                }
            )
        return normalized

    requirements = _normalize_dependency_items(metadata.get('requirements', []))
    artifactory_downloads = _normalize_dependency_items(
        metadata.get('artifactory_downloads', [])
    )

    cyclonedx = metadata.get('cyclonedx', {})
    if not isinstance(cyclonedx, dict):
        cyclonedx = {}

    runtime_requirements = cyclonedx.get('tools_detailed', [])
    if not isinstance(runtime_requirements, list):
        runtime_requirements = []

    normalized_runtime_requirements = []
    for item in runtime_requirements:
        if isinstance(item, dict):
            name = str(item.get('name', '') or '').strip()
            version = str(item.get('version', '') or '').strip()
            if name:
                normalized_runtime_requirements.append(
                    {
                        'name': name,
                        'version': version,
                    }
                )

    if not normalized_runtime_requirements:
        legacy_tools = cyclonedx.get('tools', [])
        if not isinstance(legacy_tools, list):
            legacy_tools = []
        for tool_name in legacy_tools:
            text = str(tool_name or '').strip()
            if not text:
                continue
            normalized_runtime_requirements.append(
                {
                    'name': text,
                    'version': '',
                }
            )

    runtime_alias_types = {
        'runtime',
        'step-runtime',
        'cmake-fetch',
    }

    requirements_rows = []
    runtime_requirements_count = 0
    for item in requirements:
        item_type = str(item['type'] or '').strip()
        if item_type.lower() in runtime_alias_types:
            runtime_requirements_count += 1

        requirements_rows.append(
            f"<tr>"
            f"<td>{escape(item['name'] or '-')}</td>"
            f"<td>{escape(item_type or '-')}</td>"
            f"<td>{escape(item['version'] or '-')}</td>"
            f"</tr>"
        )

    for tool in normalized_runtime_requirements:
        runtime_requirements_count += 1
        requirements_rows.append(
            f"<tr>"
        f"<td>{escape(tool.get('name', '') or '-')}</td>"
            f"<td>step-runtime</td>"
        f"<td>{escape(tool.get('version', '') or '-')}</td>"
            f"</tr>"
        )

    artifactory_rows = []
    for item in artifactory_downloads:
        display_properties = {
            k: v
            for k, v in sorted(item['properties'].items())
            if str(k).strip().lower() != 'rb_version'
        }
        properties_text = (
            '; '.join(f'{k}={v}' for k, v in display_properties.items()) or '-'
        )
        artifactory_rows.append(
            f"<tr>"
            f"<td>{escape(item['name'] or '-')}</td>"
            f"<td>{escape(item['version'] or '-')}</td>"
            f"<td>{escape(item.get('repository', '') or '-')}</td>"
            f"<td>{escape(item.get('repository_type', '') or 'OTHER')}</td>"
            f"<td>{escape(properties_text)}</td>"
            f"<td>{escape(item['source'] or '-')}</td>"
            f"</tr>"
        )

    requirements_subsection_html = ''
    if requirements_rows:
        requirements_subsection_html = f"""
      <details class=\"report-subsection\">
        <summary>Requirements Used In Action</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap\">
          <table>
            <thead>
              <tr><th>Name</th><th>Type</th><th>Version</th></tr>
            </thead>
            <tbody>
              {''.join(requirements_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
"""

    downloads_subsection_html = ''
    if artifactory_rows:
        downloads_subsection_html = f"""
      <details class=\"report-subsection\">
        <summary>Artifactory Downloads</summary>
        <div class=\"section-body\">
          <div class=\"table-wrap\">
          <table>
            <thead>
              <tr><th>Name</th><th>Version</th><th>Repository</th><th>Repository Type</th><th>Properties</th><th>Source</th></tr>
            </thead>
            <tbody>
              {''.join(artifactory_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
"""

    return f"""
  <details class=\"report-section\">
    <summary>Dependencies/Downloads</summary>
    <div class=\"section-body\">
      <div class=\"section-summary\">
        <div class=\"card card-neutral\"><strong>Requirements</strong><br />{len(requirements)}</div>
        <div class=\"card card-neutral\"><strong>Artifactory Downloads</strong><br />{len(artifactory_downloads)}</div>
        <div class=\"card card-neutral\"><strong>Runtime Requirements</strong><br />{runtime_requirements_count}</div>
      </div>
      {requirements_subsection_html}
      {downloads_subsection_html}
    </div>
  </details>
"""
