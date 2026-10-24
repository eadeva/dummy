"""Advanced help report generator and configuration importer orchestration."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from xc_ce_utils import logger
from xc_ce_utils.core_engine.reporting import (
    build_default_reporting_pipeline,
)

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


def run_advanced_help(generator: DynamicCLIGenerator) -> None:
    """Generate the advanced help HTML report from project configuration."""
    logger.progress('Gathering project configuration details for Advanced Help...')

    full_config = generator.full_config

    project_name = os.environ.get('PROJECT_NAME', 'Unknown Project')
    xc_ce_utils_version = os.environ.get('XC_CE_UTILS_VERSION', 'Unknown Version')

    # 1. Harvest System & Context Details
    system_info = {
        'os': sys.platform,
        'python_version': sys.version.split()[0],
        'repo_root': str(generator.repo_root),
        'execution_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # 2. Harvest Registered Actions (excluding CX-only actions)
    from xc_ce_utils.core_engine.cli.action_introspection import (
        get_action_config,
        is_ci_only_action,
    )

    actions_info = []
    for action_name, action_config in generator.actions.items():
        if is_ci_only_action(generator, action_name):
            continue

        desc = 'No description'
        group = 'Top-level'
        if isinstance(action_config, dict):
            desc = action_config.get('description', desc)
            group = action_config.get('action_group', group)

        act_cfg = get_action_config(generator, action_name)
        no_variants = act_cfg.get('no_variants', False)
        only_variants = act_cfg.get('only_variants', [])
        omit_variants = act_cfg.get('omit_variants', [])

        actions_info.append(
            {
                'name': action_name,
                'description': desc,
                'group': group,
                'no_variants': no_variants,
                'only_variants': [str(v) for v in only_variants],
                'omit_variants': [str(v) for v in omit_variants],
            }
        )

    # Helper to resolve and load raw requirement YAML/JSON paths into dicts
    def load_req_dict(req_val):
        if isinstance(req_val, dict):
            return req_val
        if isinstance(req_val, str) and req_val.endswith(('.yml', '.yaml', '.json')):
            main_conf_dir = Path(generator.conf_file).parent
            req_path = (main_conf_dir / req_val).resolve()
            if req_path.is_file():
                try:
                    import yaml

                    return yaml.safe_load(req_path.read_text(encoding='utf-8')) or {}
                except Exception:
                    pass
        return {}

    # 3. Harvest Variant Matrix Overrides and Global Defaults
    variants_info = []
    global_build_options = {}
    global_requirements = {}
    matrix = getattr(generator, 'variant_matrix', None)
    if matrix:
        raw_global_bo = matrix.global_defaults.get('build_options', {}) or {}
        for k, v in raw_global_bo.items():
            global_build_options[f"BO_{k.upper().replace('-', '_')}"] = v

        global_requirements = {
            'build': load_req_dict(matrix.global_defaults.get('build_requires', {})),
            'tool': load_req_dict(matrix.global_defaults.get('tool_requires', {})),
            'test': load_req_dict(matrix.global_defaults.get('test_requires', {})),
        }

        default_variant_path = getattr(matrix, 'default_variant', None)
        all_variants_list = list(matrix.get_variants().items())

        for var_path, var_obj in sorted(all_variants_list):
            alias = var_obj.get_variant_alias()

            # Retrieve only original raw overrides from get_raw_dict()
            raw_dict = var_obj.get_raw_dict() or {}
            reqs = {
                'build': load_req_dict(raw_dict.get('build_requires', {})),
                'tool': load_req_dict(raw_dict.get('tool_requires', {})),
                'test': load_req_dict(raw_dict.get('test_requires', {})),
            }

            # Determine platform-appropriate wrapper script command prefix
            cmd_prefix = r'.\build.ps1' if sys.platform == 'win32' else './build.sh'

            # Build Example CLI Commands
            is_default = var_path == default_variant_path
            possible_commands = []
            for action in actions_info:
                allowed = True
                if action['no_variants']:
                    possible_commands.append(f'{cmd_prefix} {action["name"]}')
                else:
                    if action['only_variants']:
                        if alias not in action['only_variants']:
                            allowed = False
                    if action['omit_variants']:
                        if alias in action['omit_variants']:
                            allowed = False

                    if allowed:
                        if is_default:
                            possible_commands.append(f'{cmd_prefix} {action["name"]}')
                        else:
                            possible_commands.append(f'{cmd_prefix} -var {alias} {action["name"]}')

            # Build options: only variant explicit overrides with BO_ prefix, plus automatic variant options
            bo_dict = {}
            for k, v in (raw_dict.get('build_options', {}) or {}).items():
                bo_dict[f"BO_{k.upper().replace('-', '_')}"] = v
            # Add automatic variant build options
            for level_val in var_obj.get_variant_values().values():
                if level_val:
                    bo_dict[f"BO_{level_val.upper().replace('-', '_')}"] = 1

            variants_info.append(
                {
                    'id': var_path,
                    'alias': alias,
                    'description': var_obj.get_description(),
                    'default': is_default,
                    'build_options': bo_dict,
                    'calibration_variants': var_obj.get_calibration_variants() or [],
                    'requirements': reqs,
                    'possible_commands': possible_commands,
                }
            )
    else:
        # Determine platform-appropriate wrapper script command prefix
        cmd_prefix = r'.\build.ps1' if sys.platform == 'win32' else './build.sh'
        # Fallback if no matrix initialized
        variants_info.append(
            {
                'id': 'default',
                'alias': 'default',
                'description': 'Default Variant',
                'default': True,
                'build_options': {},
                'calibration_variants': [],
                'requirements': {'build': {}, 'tool': {}, 'test': {}},
                'possible_commands': [f'{cmd_prefix} build'],
            }
        )

    # Post-process actions_info to populate allowed_variants string for display
    all_v_aliases = [var['alias'] for var in variants_info]
    for action in actions_info:
        if action['no_variants']:
            action['allowed_variants'] = 'no variant dependencies'
        elif action['only_variants']:
            action['allowed_variants'] = ', '.join(action['only_variants'])
        elif action['omit_variants']:
            allowed_v = [v for v in all_v_aliases if v not in action['omit_variants']]
            action['allowed_variants'] = ', '.join(allowed_v) if allowed_v else 'None'
        else:
            action['allowed_variants'] = ', '.join(all_v_aliases) if all_v_aliases else 'All'

    # 4. Gather default parameters from the full PROJECT_CONFIG, DEFAULT_PARAMETERS and generator.build_config
    project_cfg = full_config.get('PROJECT_CONFIG', {}) or {}
    defaults = {}
    for k, v in project_cfg.items():
        if k not in ('VARIANTS', 'variants', 'variant_matrix') and isinstance(
            v, (str, int, float, bool)
        ):
            defaults[k] = v

    root_defaults = full_config.get('DEFAULT_PARAMETERS', {}) or {}
    for k, v in root_defaults.items():
        if isinstance(v, (str, int, float, bool)):
            defaults[k] = v

    # Merge action config default parameters (from actions_conf.yml via build_config)
    build_cfg = getattr(generator, 'build_config', {}) or {}
    actions_defaults = build_cfg.get('DEFAULT_PARAMETERS', {}) or {}
    for k, v in actions_defaults.items():
        if isinstance(v, (str, int, float, bool)):
            defaults[k] = v

    # Resolve short commit hash and dirty status using git.Repo
    import git

    short_commit_hash = 'unknown'
    git_is_dirty = 'false'
    try:
        repo = git.Repo(generator.repo_root, search_parent_directories=True)
        short_commit_hash = repo.head.commit.hexsha[:8]
        git_is_dirty = 'true' if repo.is_dirty() else 'false'
    except Exception:
        pass

    # Construct complete payload, preserving the ENTIRE merged configuration dictionary!
    rb_version_value = getattr(generator, 'artifact_version', 'unknown') or 'unknown'

    build_context = {
        'rb_version': rb_version_value,
        'xc_ce_utils_version': xc_ce_utils_version,
        'variant_long_name': 'all',
        'short_commit_hash': short_commit_hash,
        'git_is_dirty': git_is_dirty,
        'os_name': 'Windows' if sys.platform == 'win32' else 'Linux',
        'docker_enabled': False,
    }

    config_info = {
        'project': project_name,
        'version': xc_ce_utils_version,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'system_info': system_info,
        'build_context': build_context,
        'default_parameters': defaults,
        'global_build_options': global_build_options,
        'global_requirements': global_requirements,
        'project_config_meta': full_config.get('PROJECT_CONFIG', {}),
        'conan_enabled': full_config.get('CONAN_ENABLED', True),
        'variants': variants_info,
        'actions': actions_info,
        # Preserve the raw, complete full_config for any potential future usages
        'full_config': full_config,
    }

    # 5. Create the reports output folder
    reports_dir = generator.repo_root / '_reports' / 'advanced-help'
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 6. Save the payload as project_config.json
    config_json_file = reports_dir / 'project_config.json'
    config_json_file.write_text(json.dumps(config_info, indent=2), encoding='utf-8')

    # 7. Execute the unified reporting pipeline to generate advanced-help-report.html!
    logger.progress('Running reporting pipeline to generate advanced help page...')
    pipeline = build_default_reporting_pipeline()

    metadata = {
        'action': 'adv-help',
        'variant': 'all',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'project_config': config_info,  # Put it in metadata for HTML rendering
    }

    generated = pipeline.run(
        reports_dir=str(reports_dir),
        output_dir=str(generator.repo_root / '_reports'),
        report_name='advanced-help-report',
        output_formats=['html'],
        glob_pattern='*',
        metadata=metadata,
        canonical_json_name='advanced-help-report.canonical.json',
    )

    html_path = generated.get('html')
    if html_path:
        abs_html_path = str(Path(html_path).resolve())
        logger.success(f'Advanced help documentation page generated: {abs_html_path}')
        # Register in environment variables so execution_tracker can open it non-blockingly at exit
        os.environ['XC_CE_UTILS_ADVANCED_HELP_HTML'] = abs_html_path

        # Open the report in browser directly and non-blockingly from this process
        logger.info('Opening advanced help page in browser...')
        import time
        import webbrowser

        try:
            if sys.platform == 'win32':
                os.startfile(abs_html_path)
            else:
                webbrowser.open(Path(abs_html_path).as_uri())
            time.sleep(
                0.2
            )  # Give OS shell thread a moment to spawn the browser before process exits
        except Exception as e:
            logger.warning(f'Could not open browser automatically: {e}')
