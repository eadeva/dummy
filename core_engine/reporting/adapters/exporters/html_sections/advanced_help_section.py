"""Renderer for the HTML Advanced Help section."""

from __future__ import annotations

import sys
from html import escape


def _normalize_bool_to_binary_str(val) -> str:
    """Normalize boolean-like values into string '1' or '0'."""
    if isinstance(val, bool):
        return '1' if val else '0'
    val_str = str(val).strip().upper()
    if val_str in ('TRUE', 'ON', 'YES', '1'):
        return '1'
    if val_str in ('FALSE', 'OFF', 'NO', '0'):
        return '0'
    return str(val)


def _resolve_version_string(r_ver) -> str:
    """Resolve requirement version string, handling latest and nested properties dicts."""
    if isinstance(r_ver, dict):
        if r_ver.get('latest') is True:
            return 'latest'
        if r_ver.get('properties', {}).get('latest') is True:
            return 'latest'

        version_str = r_ver.get('rb_version') or r_ver.get('version') or ''
        if not version_str and 'properties' in r_ver:
            props = r_ver.get('properties', {}) or {}
            version_str = props.get('rb_version') or props.get('version') or ''
        return str(version_str)

    if isinstance(r_ver, (str, int, float)):
        return str(r_ver)

    return ''


def render_advanced_help_section(project_config: dict) -> str:
    """Render the advanced help section containing project config tables."""
    if not project_config:
        return ''

    # Platform-appropriate wrapper script command prefix
    script_ext = 'ps1' if sys.platform == 'win32' else 'sh'
    script_char = '\\' if sys.platform == 'win32' else '/'
    script_name = f'.{script_char}build.{script_ext}'

    # 1. Available Actions & Groups Section (MOVED TO TOP)
    actions = project_config.get('actions', [])
    actions_rows = []
    if actions:
        for action in sorted(actions, key=lambda a: str(a.get('name', ''))):
            name = escape(str(action.get('name', '')))
            desc = escape(str(action.get('description', 'No description')))
            group = escape(str(action.get('group', 'Top-level')))
            allowed_variants = escape(str(action.get('allowed_variants', 'All')))
            actions_rows.append(
                f'<tr>'
                f"<td><strong style='color: #0f172a;'>{name}</strong></td>"
                f'<td>{desc}</td>'
                f"<td><span style='font-size: 0.85rem; color: #475569;'>{allowed_variants}</span></td>"
                f"<td><span class='badge' style='background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1;'>{group}</span></td>"
                f'</tr>'
            )
    else:
        actions_rows.append("<tr><td colspan='4'>No actions registered</td></tr>")

    actions_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>Available Actions & Groups</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 15%;">Action Name</th>
                <th style="width: 45%;">Description</th>
                <th style="width: 25%;">Possible Variants</th>
                <th style="width: 15%;">Action Group</th>
              </tr>
            </thead>
            <tbody>
              {''.join(actions_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 1b. CLI Syntax & Usage Section
    syntax_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>CLI Syntax & Usage</summary>
        <div class="section-body" style="padding: 1rem; line-height: 1.6;">
          <p>The <code>xc-ce-utils</code> CLI is constructed using a nested command and option hierarchy. You can specify options globally at the root level, target config utility command groups, or run variant-dependent build actions.</p>
          <div style="background: #0f172a; color: #f8fafc; padding: 1rem; border-left: 4px solid #3b82f6; border-radius: 6px; font-family: monospace; font-size: 0.9rem; margin: 1rem 0;">
            Usage: {script_name} [OPTIONS] [COMMAND] [ARGS]...
          </div>
        </div>
      </details>
    """

    # 2. CLI General Options
    options_rows = [
        (
            '<code>--help</code>, <code>-h</code>',
            'Show main or action-specific help message and exit',
        ),
        ('<code>--version</code>', 'Show current xc-ce-utils version and exit'),
        (
            '<code>--adv-help</code>, <code>-ah</code>',
            'Generate and open the interactive Advanced Help documentation page and exit',
        ),
        (
            '<code>--variant &lt;alias&gt;</code>, <code>-var &lt;alias&gt;</code>',
            'Specify the variant alias/path or comma/space-separated list of variants to run',
        ),
        (
            '<code>--all-variants</code>, <code>-all</code>',
            'Execute the specified action for all configured variants sequentially (ignores -var)',
        ),
        (
            '<code>--clean</code>, <code>-c</code>',
            'Delete build/reports folders for the specified action and stop',
        ),
        (
            '<code>--rebuild</code>, <code>-rb</code>',
            'Forces a clean rebuild of the specified action (deletes folders first, then builds)',
        ),
        (
            '<code>--force-gen</code>, <code>-fg</code>',
            'Force code generation, ignoring all cache checks',
        ),
        (
            '<code>--verbose</code>, <code>-v</code>',
            'Enable verbose log output streaming to the terminal (INFO level)',
        ),
        (
            '<code>--verbose --verbose</code>, <code>-vv</code>',
            'Enable extremely detailed TRACE level logging and diagnostic/startup traces',
        ),
    ]
    options_html_rows = []
    for opt, desc in options_rows:
        options_html_rows.append(f'<tr><td>{opt}</td><td>{desc}</td></tr>')

    options_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>CLI General Options</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 30%;">CLI Option</th>
                <th style="width: 70%;">Description</th>
              </tr>
            </thead>
            <tbody>
              {''.join(options_html_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 3. General Commands
    general_cmds = [
        (
            f'<code>{script_name} --help</code>',
            'Show main CLI help message and list of available actions',
            'All Users',
        ),
        (
            f'<code>{script_name} --version</code>',
            'Show the currently active version of xc-ce-utils',
            'All Users',
        ),
        (
            f'<code>{script_name} -ah</code>',
            'Generate and launch this Advanced Help interactive page',
            'All Users',
        ),
        (
            f'<code>{script_name} &lt;action&gt;</code>',
            'Execute the specified action on the default variant',
            'All Users',
        ),
        (
            f'<code>{script_name} -var &lt;variant&gt; &lt;action&gt;</code>',
            'Execute the specified action on a specific variant alias/path',
            'All Users',
        ),
        (
            f'<code>{script_name} -all &lt;action&gt;</code>',
            'Execute the specified action for all configured variants',
            'All Users',
        ),
    ]
    cmds_html_rows = []
    for cmd, desc, audience in general_cmds:
        cmds_html_rows.append(f'<tr><td>{cmd}</td><td>{desc}</td><td>{audience}</td></tr>')

    cmds_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>General Commands</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 40%;">Command Line</th>
                <th style="width: 45%;">Description</th>
                <th style="width: 15%;">Audience</th>
              </tr>
            </thead>
            <tbody>
              {''.join(cmds_html_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 4. Config Commands (Developer self-service)
    config_cmds = [
        (
            f'<code>{script_name} config force-setup</code>',
            'Delete local setup directories and force standard developer environment setup',
            'All Users',
        ),
        (
            f'<code>{script_name} config clean-older-versions</code>',
            'Clean up older tool versions from local cache',
            'All Users',
        ),
        (
            f'<code>{script_name} config refresh-hooks</code>',
            "Force re-deploy and refresh the repository's local Git hooks",
            'All Users',
        ),
        (
            f'<code>{script_name} config creds check</code>',
            'Check the presence and status of active Artifactory/Git credentials',
            'All Users',
        ),
        (
            f'<code>{script_name} config creds set</code>',
            'Set and store local/environment credentials',
            'All Users',
        ),
        (
            f'<code>{script_name} config creds clear</code>',
            'Wipe and clear stored Artifactory/Git credentials',
            'All Users',
        ),
        (
            f'<code>{script_name} config vs-code check-extensions</code>',
            'Check and alert about missing committed VS Code extensions',
            'All Users',
        ),
        (
            f'<code>{script_name} config vs-code devmate-setup</code>',
            'Configure local Devmate settings for the user',
            'All Users',
        ),
        (
            f'<code>{script_name} config validate</code>',
            'Validate project configuration files for syntax or semantic errors',
            'All Users',
        ),
        (
            f'<code>{script_name} config dump-config</code>',
            'Dumps the resolved configuration payload to stdout or a file',
            'All Users',
        ),
    ]
    config_html_rows = []
    for cmd, desc, audience in config_cmds:
        config_html_rows.append(f'<tr><td>{cmd}</td><td>{desc}</td><td>{audience}</td></tr>')

    config_subsection_html = f"""
      <details class="report-subsection">
        <summary>Config Commands (Developer Self-Service)</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 40%;">Config Command</th>
                <th style="width: 45%;">Description</th>
                <th style="width: 15%;">Audience</th>
              </tr>
            </thead>
            <tbody>
              {''.join(config_html_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 5. DevOps & Maintainer Commands (under config-devops group)
    devops_cmds = [
        (
            f'<code>{script_name} config-devops full-setup</code>',
            'Delete current setup folder and run a complete, fresh maintainer full-setup',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
        (
            f'<code>{script_name} config-devops clang-setup</code>',
            'Force re-download, extract, and configure the local Clang compiler toolchain',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
        (
            f'<code>{script_name} config-devops hooks-setup</code>',
            'Force re-install and deploy the standard Git hooks in the repository',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
        (
            f'<code>{script_name} config-devops vscode regen-ws-conf</code>',
            'Regenerate the shared VS Code workspace tasks, extensions, and settings',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
        (
            f'<code>{script_name} config-devops vscode regen-mcp-json</code>',
            'Regenerate the .vscode/mcp.json file from the registry',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
        (
            f'<code>{script_name} config-devops vscode regen-copilot</code>',
            'Regenerate the committed .github/copilot-instructions.md file',
            "<span style='color: #b91c1c; font-weight: bold;'>Maintainers</span>",
        ),
    ]
    devops_html_rows = []
    for cmd, desc, audience in devops_cmds:
        devops_html_rows.append(f'<tr><td>{cmd}</td><td>{desc}</td><td>{audience}</td></tr>')

    devops_subsection_html = f"""
      <details class="report-subsection">
        <summary>DevOps & Maintainer Commands</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 40%;">DevOps Command</th>
                <th style="width: 45%;">Description</th>
                <th style="width: 15%;">Audience</th>
              </tr>
            </thead>
            <tbody>
              {''.join(devops_html_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 6. Global Default Parameters
    defaults = project_config.get('default_parameters', {})
    defaults_rows = []
    if defaults:
        for k, v in sorted(defaults.items()):
            defaults_rows.append(
                f'<tr><td><strong>{escape(str(k))}</strong></td><td><code>{escape(str(v))}</code></td></tr>'
            )
    else:
        defaults_rows.append("<tr><td colspan='2'>No default parameters configured</td></tr>")

    defaults_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>Global Default Parameters</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 30%;">Parameter Key</th>
                <th style="width: 70%;">Default Value</th>
              </tr>
            </thead>
            <tbody>
              {''.join(defaults_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 6b. Global Requirements Section (with explicit requested columns: Actions and Additional Properties)
    global_reqs = project_config.get('global_requirements', {}) or {}
    global_reqs_details = []
    for req_dict in global_reqs.values():
        if isinstance(req_dict, dict):
            for r_name, r_ver in sorted(req_dict.items()):
                version_str = _resolve_version_string(r_ver)

                # Settle needed_for (actions on separate lines)
                actions_list = []
                if isinstance(r_ver, dict) and 'needed_for' in r_ver:
                    raw_needed = r_ver.get('needed_for', [])
                    if isinstance(raw_needed, list):
                        actions_list = [escape(str(act)) for act in raw_needed]
                    else:
                        actions_list = [escape(str(raw_needed))]
                actions_str = (
                    '<br />'.join(actions_list)
                    if actions_list
                    else "<em style='color: #64748b;'>None</em>"
                )

                # Settle additional properties (not rb_version, formatted as key=value on separate lines)
                add_props = []
                if isinstance(r_ver, dict):
                    # 1. Properties dictionary
                    props = r_ver.get('properties', {}) or {}
                    for pk, pv in sorted(props.items()):
                        if pk not in ('rb_version', 'version'):
                            add_props.append(f'<code>{escape(str(pk))}={escape(str(pv))}</code>')
                    # 2. Main dictionary attributes (excluding standard ones)
                    for mk, mv in sorted(r_ver.items()):
                        if mk not in (
                            'rb_version',
                            'version',
                            'properties',
                            'needed_for',
                            'latest',
                            'type',
                        ) and not isinstance(mv, (dict, list)):
                            add_props.append(f'<code>{escape(str(mk))}={escape(str(mv))}</code>')
                add_props_str = (
                    '<br />'.join(add_props)
                    if add_props
                    else "<em style='color: #64748b;'>None</em>"
                )

                if version_str and not version_str.endswith(('.yml', '.yaml', '.json')):
                    global_reqs_details.append(
                        f'<tr>'
                        f'<td><strong>{escape(str(r_name))}</strong></td>'
                        f'<td><code>{escape(str(version_str))}</code></td>'
                        f'<td>{actions_str}</td>'
                        f'<td>{add_props_str}</td>'
                        f'</tr>'
                    )
                elif not version_str:
                    global_reqs_details.append(
                        f'<tr>'
                        f'<td><strong>{escape(str(r_name))}</strong></td>'
                        f'<td><code>None</code></td>'
                        f'<td>{actions_str}</td>'
                        f'<td>{add_props_str}</td>'
                        f'</tr>'
                    )

    if not global_reqs_details:
        global_reqs_details.append(
            "<tr><td colspan='4'>No global requirements configured</td></tr>"
        )

    global_requirements_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>Global Requirements</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 25%;">Requirement / Tool Name</th>
                <th style="width: 20%;">Version (rb_version)</th>
                <th style="width: 25%;">Actions</th>
                <th style="width: 30%;">Additional Properties</th>
              </tr>
            </thead>
            <tbody>
              {''.join(global_reqs_details)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 6c. Global Build Options
    global_build_opts = project_config.get('global_build_options', {})
    build_opts_rows = []
    if global_build_opts:
        for k, v in sorted(global_build_opts.items()):
            norm_val = _normalize_bool_to_binary_str(v)
            build_opts_rows.append(
                f'<tr><td><strong>{escape(str(k))}</strong></td><td><code>{escape(str(norm_val))}</code></td></tr>'
            )
    else:
        build_opts_rows.append("<tr><td colspan='2'>No global build options configured</td></tr>")

    build_opts_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>Global Build Options</summary>
        <div class="section-body">
          <p style="margin-bottom: 0.75rem; font-size: 0.88rem; line-height: 1.5; color: #475569;">
            In the <code>xc-ce-utils</code> toolchain, build options are made available in CMake as compile definitions
            and in general as environment variables (prefixed with <code>BO_</code>) which can be used throughout
            the whole system in project-specific scripts.
          </p>
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 50%;">Build Option</th>
                <th style="width: 50%;">Value</th>
              </tr>
            </thead>
            <tbody>
              {''.join(build_opts_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    # 7. Variants Matrix Section
    variants = project_config.get('variants', [])
    variant_rows = []
    if variants:
        for var in variants:
            var_id = escape(str(var.get('id', '')))
            alias = escape(str(var.get('alias', '')))
            desc = escape(str(var.get('description', '')))
            is_default_str = 'Yes' if var.get('default') else ''

            # Build Options (only variant explicit overrides)
            bo = var.get('build_options', {})
            bo_html = []
            if bo:
                for k, v in sorted(bo.items()):
                    norm_val = _normalize_bool_to_binary_str(v)
                    bo_html.append(f'<code>{escape(str(k))}={escape(str(norm_val))}</code>')
                bo_str = '<br />'.join(bo_html)
            else:
                bo_str = "<em style='color: #64748b;'>None</em>"

            # Calibration Variants
            cal_vars = var.get('calibration_variants', [])
            cal_vars_str = (
                escape(', '.join(cal_vars)) if cal_vars else "<em style='color: #64748b;'>None</em>"
            )

            # Requirements (strictly structured: name, version, and additional_properties)
            reqs = var.get('requirements', {}) or {}
            req_details = []

            for req_dict in reqs.values():
                if isinstance(req_dict, dict):
                    for r_name, r_ver in sorted(req_dict.items()):
                        version_str = _resolve_version_string(r_ver)

                        # Extract additional properties
                        add_props = []
                        if isinstance(r_ver, dict):
                            # Properties sub-dict
                            props = r_ver.get('properties', {}) or {}
                            for pk, pv in sorted(props.items()):
                                if pk not in ('rb_version', 'version'):
                                    add_props.append(f'{escape(str(pk))}={escape(str(pv))}')
                            # Sibling attributes
                            for mk, mv in sorted(r_ver.items()):
                                if mk not in (
                                    'rb_version',
                                    'version',
                                    'properties',
                                    'needed_for',
                                    'latest',
                                    'type',
                                ) and not isinstance(mv, (dict, list)):
                                    add_props.append(f'{escape(str(mk))}={escape(str(mv))}')

                        # Build structured block
                        req_block = []
                        req_block.append(f'<strong>{escape(str(r_name))}</strong>')
                        if version_str and not version_str.endswith(('.yml', '.yaml', '.json')):
                            req_block.append(
                                f'&nbsp;&nbsp;&nbsp;&nbsp;<code>version={escape(str(version_str))}</code>'
                            )
                        for prop in add_props:
                            req_block.append(f'&nbsp;&nbsp;&nbsp;&nbsp;<code>{prop}</code>')

                        req_details.append('<br />'.join(req_block))

            reqs_str = (
                '<br /><br />'.join(req_details)
                if req_details
                else "<em style='color: #64748b;'>None</em>"
            )

            # Format example commands
            commands = var.get('possible_commands', [])
            cmds_html = []
            for cmd in commands:
                cmds_html.append(
                    f"<div style='display: flex; align-items: center; margin-bottom: 0.25rem;'>"
                    f"<code style='background: #f1f5f9; padding: 0.15rem 0.35rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.8rem; flex-grow: 1; white-space: nowrap;'>{escape(cmd)}</code>"
                    f'</div>'
                )
            cmds_str = ''.join(cmds_html)

            variant_rows.append(
                f'<tr>'
                f'<td><strong>{var_id}</strong></td>'
                f'<td>{alias}</td>'
                f'<td>{desc}</td>'
                f'<td><strong>{is_default_str}</strong></td>'
                f'<td>{bo_str}</td>'
                f'<td>{cal_vars_str}</td>'
                f"<td style='font-size: 0.82rem;'>{reqs_str}</td>"
                f"<td style='min-width: 25rem;'>{cmds_str}</td>"
                f'</tr>'
            )
    else:
        variant_rows.append(
            "<tr><td colspan='8'>No variant matrix configurations available</td></tr>"
        )

    variants_subsection_html = f"""
      <details class="report-subsection" open>
        <summary>Variant Configurations</summary>
        <div class="section-body">
          <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 15%;">Variant (long name)</th>
                <th style="width: 5%;">Alias</th>
                <th style="width: 20%;">Description</th>
                <th style="width: 5%;">Default</th>
                <th style="width: 15%;">Build Options</th>
                <th style="width: 10%;">Calibration Variants</th>
                <th style="width: 15%;">Requirements</th>
                <th style="width: 35%; min-width: 25rem;">Example CLI Commands</th>
              </tr>
            </thead>
            <tbody>
              {''.join(variant_rows)}
            </tbody>
          </table>
          </div>
        </div>
      </details>
    """

    return f"""
  <details class="report-section" open>
    <summary>Advanced Help & Project Configuration</summary>
    <div class="section-body">
      {actions_subsection_html}
      {syntax_subsection_html}
      {options_subsection_html}
      {cmds_subsection_html}
      {config_subsection_html}
      {devops_subsection_html}
      {defaults_subsection_html}
      {global_requirements_subsection_html}
      {build_opts_subsection_html}
      {variants_subsection_html}
    </div>
  </details>
"""
