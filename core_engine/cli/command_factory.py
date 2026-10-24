"""Click command/group factory functions for the dynamic CLI.

This module owns the construction of every ``click.Command`` and
``click.Group`` exposed by xc-ce-utils.  The functions accept a
``DynamicCLIGenerator`` instance and read configuration / helpers from it,
keeping the click wiring isolated from the orchestrator state.

Extracted from ``core_engine/dynamic_cli.py`` in Phase 4 sub-commit 3 of
PR #47.  Behavioural change must be zero -- bodies were moved verbatim;
``self`` references were renamed to ``generator``.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, cast

import rich_click as click
from packaging.version import InvalidVersion, Version

from xc_ce_utils import logger
from xc_ce_utils.core_engine.cli import action_introspection as introspection
from xc_ce_utils.core_engine.cli import (
    role_gating,
    vscode_commands,
)

_BUILD_TYPES = ['Debug', 'Release', 'RelWithDebInfo', 'Developer']

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


def _get_environment_setup_cls():
    module = import_module('xc_ce_utils.core_engine.setup')
    return module.EnvironmentSetup


def _get_setup_context_cls():
    module = import_module('xc_ce_utils.core_engine.setup.phases')
    return module.SetupContext


def _get_variant_executor_module():
    return import_module('xc_ce_utils.core_engine.cli.variant_executor')


def _get_version_manager():
    module = import_module('xc_ce_utils.utils.version')
    return module.version_manager


def _get_validate_and_dump_commands():
    module = import_module('xc_ce_utils.xc_ce_utils')
    return module.validate, module.dump_config


def _get_creds_group_factory():
    module = import_module('xc_ce_utils.auth.credential_commands')
    return module.create_creds_group


def _get_phase_class(module_name: str, class_name: str):
    module = import_module(module_name)
    return getattr(module, class_name)


def _get_clang_config_resolver():
    module = import_module('xc_ce_utils.clang.config_resolver')
    return module.resolve_clang_config


@dataclass(frozen=True)
class _SetupContextOptions:
    force: bool
    is_ci: bool
    extras: dict | None = None


def _call_setup_method(setup: object, method_name: str, *args, **kwargs):
    method = getattr(setup, method_name)
    return method(*args, **kwargs)


def _call_setup_class_method(setup_cls: type, method_name: str, *args, **kwargs):
    method = getattr(setup_cls, method_name)
    return method(*args, **kwargs)


def _create_setup_context(
    setup: object,
    config: dict,
    state: dict,
    options: _SetupContextOptions,
):
    setup_context_cls = _get_setup_context_cls()
    return setup_context_cls(
        setup=setup,
        config=config,
        state=state,
        first_time_setup=False,
        force=options.force,
        is_ci=options.is_ci,
        needs_credential_check=False,
        extras=options.extras,
    )


# ---------------------------------------------------------------------------
# Per-action command
# ---------------------------------------------------------------------------
def create_action_command_with_arguments(
    generator: 'DynamicCLIGenerator',
    action: str,
    *,
    hidden: bool = False,
) -> click.Command:
    """Create an action command with variant arguments instead of subcommands."""
    help_string = introspection.get_action_help_string(generator, action)

    # Add --no-cache affected phases info to help text
    affected_by_no_cache = []
    if introspection.has_bazel_phases(generator, action):
        affected_by_no_cache.append('Bazel remote cache')
    if introspection.has_docascode_phases(generator, action):
        affected_by_no_cache.append('docascode rebuild')
    if introspection.has_cmake_phases(generator, action):
        affected_by_no_cache.append('CMake ccache override')

    if affected_by_no_cache:
        help_string += f"\n\n Affected by --no-cache: {', '.join(affected_by_no_cache)}"

    (default_from, default_to, action_phases) = introspection.get_action_default_from_and_to_phases(
        generator, action
    )

    logger.debug(f'Action {action} default phases {default_from} -> {default_to}')

    @click.command(
        name=action.lower(),
        hidden=hidden,
        help=f'{help_string}\n\nUsage: build.py {action.lower()} [OPTIONS] TEST',
    )
    @click.option(
        '--from',
        '-f',
        type=click.Choice(action_phases, case_sensitive=False),
        default=default_from,
        show_default=True,
        show_choices=True,
        help=' Starting build phase',
    )
    @click.option(
        '--to',
        '-t',
        type=click.Choice(action_phases, case_sensitive=False),
        default=default_to,
        show_default=True,
        show_choices=True,
        help=' Ending build phase',
    )
    @click.option(
        '--artifact',
        '-art',
        multiple=True,
        help='Artifact source override (repeatable, format: id=local:/path or id=version:x.y.z)',
    )
    @click.option(
        '--build-option',
        '-bo',
        multiple=True,
        help='Build option override (repeatable, format: name=value)',
    )
    @click.option(
        '--misc-param',
        '-mp',
        multiple=True,
        help='Additional parameter (repeatable, format: name=value)',
    )
    @click.pass_context
    def action_command(ctx, **kwargs):
        """Execute the specified action with variant arguments."""
        variant_executor = _get_variant_executor_module()
        variant_executor.execute_action_with_arguments(generator, ctx, action, kwargs)

    # Add action-specific options (e.g. --create-baseline for SCA)
    if action == 'sca':
        action_command = click.option(
            '--create-baseline',
            is_flag=True,
            default=False,
            help=' Create baseline when running static code analysis',
        )(action_command)

    # Conditionally add ccache option only for actions with CMake phases
    # Add build_type option for actions with CMake or Bazel phases
    if introspection.has_cmake_phases(generator, action) or introspection.has_bazel_phases(
        generator, action
    ):
        # Get default ccache setting from action config (only for CMake)
        ccache_default = introspection.get_ccache_default_from_config(generator, action)
        default_parameters = introspection.get_default_parameters(generator, action)

        # Check for both 'build-type' (hyphen) and 'build_type' (underscore) in config
        default_build_type = default_parameters.get(
            'build_type', default_parameters.get('build-type', 'RelWithDebInfo')
        )
        action_command = click.option(
            '--build-type',
            '-bt',
            type=click.Choice(_BUILD_TYPES, case_sensitive=False),
            default=default_build_type,
            help=' Build type',
            show_default=True,
            metavar=f"[{'/'.join(_BUILD_TYPES)}]",
        )(action_command)

        # Only add ccache for CMake builds
        if introspection.has_cmake_phases(generator, action):
            action_command = click.option(
                '--ccache/--no-ccache',
                default=ccache_default,
                help=' Enable/disable ccache for faster compilation',
            )(action_command)

        # Add developer mode and single-file build options
        action_command = click.option(
            '--dev-mode',
            is_flag=True,
            default=False,
            help=' Activate developer mode (sets XC_CE_UTILS_DEVELOPER_MODE)',
        )(action_command)

        action_command = click.option(
            '--single-file',
            type=click.Path(exists=True),
            default=None,
            help=' Build a single source file (implies --dev-mode). Accepts absolute or relative path to a .c file',
        )(action_command)

    return action_command


# ---------------------------------------------------------------------------
# clean-older-versions
# ---------------------------------------------------------------------------
def _parse_tool_version(version_dir_name: str) -> Version | None:
    """Parse a tool-version directory name into a semantic version.

    Returns ``None`` when the folder name is not a valid semantic version.
    """
    try:
        return Version(version_dir_name)
    except InvalidVersion:
        return None


def create_clean_older_versions_command(
    _generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Create the clean-older-versions command for cleanup of old version folders."""

    @click.command(
        name='clean-older-versions',
        help=' Clean up project setup folders and installed xc-ce-utils versions older than the current version',
    )
    @click.option(
        '--dry-run',
        is_flag=True,
        default=False,
        help='Show what would be deleted without actually deleting',
    )
    @click.pass_context
    def clean_older_versions_command(_ctx, dry_run):
        """Clean up setup folders and installed tool versions older than current."""
        _run_clean_older_versions(dry_run=dry_run)

    return clean_older_versions_command


def _run_clean_older_versions(*, dry_run: bool) -> None:
    logger.debug('Starting clean_older_versions_command')

    environment_setup_cls = _get_environment_setup_cls()
    version_manager = _get_version_manager()

    setup = environment_setup_cls()
    current_major = version_manager.load_version()['MAJOR_VERSION']
    current_version_obj = version_manager.get_version_object()
    current_version_str = version_manager.get_version_string()
    current_project_name = _call_setup_method(
        setup,
        '_get_project_name_from_config',
    )

    folders_to_delete, locked_folders = _scan_project_version_folders(
        current_project_name,
        current_major,
    )
    tool_versions_to_delete = _scan_tool_installation_versions(current_version_obj)

    if not _log_cleanup_findings(
        folders_to_delete,
        locked_folders,
        tool_versions_to_delete,
    ):
        return

    if dry_run and not tool_versions_to_delete:
        logger.info('\n Dry-run mode - no files will be deleted')
        return

    deleted_count, failed_count = _delete_project_folders(folders_to_delete)
    deleted_tool_count, failed_tool_count = _delete_tool_versions(
        tool_versions_to_delete,
        current_version_str,
        dry_run=dry_run,
    )

    _log_cleanup_summary(
        deleted_count + deleted_tool_count,
        failed_count + failed_tool_count,
    )


def _scan_project_version_folders(
    current_project_name: str,
    current_major: int,
) -> tuple[list[Path], list[Path]]:
    folders_to_delete: list[Path] = []
    locked_folders: list[Path] = []

    for location in _get_cleanup_locations():
        if not location.exists():
            continue

        _scan_location_versioned_folders(
            location,
            current_project_name,
            current_major,
            folders_to_delete,
            locked_folders,
        )
        _scan_location_legacy_folders(
            location,
            current_project_name,
            folders_to_delete,
            locked_folders,
        )

    return folders_to_delete, locked_folders


def _get_cleanup_locations() -> list[Path]:
    if platform.system() == 'Windows':
        return [Path.home(), Path('C:\\workflows')]
    return [Path.home(), Path('/tmp/workflows')]


def _scan_location_versioned_folders(
    location: Path,
    current_project_name: str,
    current_major: int,
    folders_to_delete: list[Path],
    locked_folders: list[Path],
) -> None:
    pattern = f'*{current_project_name}_xc-ce-utils_*.x'
    for folder in location.glob(pattern):
        if not folder.is_dir():
            continue
        _collect_versioned_folder_if_old(
            folder,
            current_project_name,
            current_major,
            folders_to_delete,
            locked_folders,
        )


def _collect_versioned_folder_if_old(
    folder: Path,
    current_project_name: str,
    current_major: int,
    folders_to_delete: list[Path],
    locked_folders: list[Path],
) -> None:
    folder_name = folder.name
    if '_xc-ce-utils_' not in folder_name or not folder_name.endswith('.x'):
        return

    try:
        project_part = folder_name.split('_xc-ce-utils_')[0].lstrip('.')
        if project_part != current_project_name:
            return

        version_part = folder_name.split('_xc-ce-utils_')[1]
        major_ver = int(version_part.replace('.x', ''))
        if major_ver >= current_major:
            return
    except (ValueError, IndexError) as error:
        logger.debug(f'Error processing folder {folder}: {error}')
        return

    _append_lock_aware(folder, folders_to_delete, locked_folders)


def _scan_location_legacy_folders(
    location: Path,
    current_project_name: str,
    folders_to_delete: list[Path],
    locked_folders: list[Path],
) -> None:
    pattern = f'*{current_project_name}*'
    for folder in location.glob(pattern):
        if not folder.is_dir():
            continue
        _collect_legacy_folder_if_project_owned(
            folder,
            current_project_name,
            folders_to_delete,
            locked_folders,
        )


def _collect_legacy_folder_if_project_owned(
    folder: Path,
    current_project_name: str,
    folders_to_delete: list[Path],
    locked_folders: list[Path],
) -> None:
    folder_name = folder.name
    if '_xc-ce-utils_' in folder_name and folder_name.endswith('.x'):
        return

    normalized = folder_name.lstrip('.')
    if normalized != current_project_name and not normalized.startswith(f'{current_project_name}_'):
        return

    state_file = folder / '.xc_ce_setup_state.json'
    marker_file = folder / '.xc_ce_builder_setup_complete'
    if state_file.exists() or marker_file.exists():
        _append_lock_aware(folder, folders_to_delete, locked_folders)
        return

    folders_to_delete.append(folder)


def _append_lock_aware(
    folder: Path,
    folders_to_delete: list[Path],
    locked_folders: list[Path],
) -> None:
    if (folder / '.xc_ce_setup.lock').exists():
        locked_folders.append(folder)
        return
    folders_to_delete.append(folder)


def _scan_tool_installation_versions(
    current_version_obj: Version,
) -> list[Path]:
    tools_dir = _get_tools_dir()
    if not tools_dir.exists() or not tools_dir.is_dir():
        return []

    tool_versions_to_delete: list[Path] = []
    for entry in tools_dir.iterdir():
        if not entry.is_dir():
            continue

        parsed_version = _parse_tool_version(entry.name)
        if parsed_version is None:
            continue

        if parsed_version < current_version_obj:
            tool_versions_to_delete.append(entry)

    return tool_versions_to_delete


def _get_tools_dir() -> Path:
    if platform.system() == 'Windows':
        return Path('C:\\tools\\xc-ce-utils')
    return Path.home() / '.local' / 'share' / 'xc-ce-utils'


def _log_cleanup_findings(
    folders_to_delete: list[Path],
    locked_folders: list[Path],
    tool_versions_to_delete: list[Path],
) -> bool:
    if not folders_to_delete and not locked_folders and not tool_versions_to_delete:
        logger.info(' No older version folders found')
        return False

    if locked_folders:
        logger.warning(f'  Skipping {len(locked_folders)} folder(s) with active locks:')
        for folder in locked_folders:
            logger.warning(f'  - {folder}')

    if folders_to_delete:
        logger.info(f'\n Found {len(folders_to_delete)} older version folder(s) to remove:')
        for folder in folders_to_delete:
            logger.info(f'  - {folder}')
    elif not tool_versions_to_delete:
        logger.info('No folders to delete')
        return False

    return True


def _delete_project_folders(folders_to_delete: list[Path]) -> tuple[int, int]:
    local_folders = [f for f in folders_to_delete if 'workflows' not in str(f)]
    ci_folders = [f for f in folders_to_delete if 'workflows' in str(f)]

    deleted_count = 0
    failed_count = 0
    deleted, failed = _delete_confirmed_folder_group(
        local_folders,
        prompt='Delete local folders? [y/N]: ',
        group_label='local',
    )
    deleted_count += deleted
    failed_count += failed

    deleted, failed = _delete_confirmed_folder_group(
        ci_folders,
        prompt='Delete CI workflow folders? [y/N]: ',
        group_label='CI workflow',
    )
    deleted_count += deleted
    failed_count += failed

    return deleted_count, failed_count


def _delete_confirmed_folder_group(
    folders: list[Path],
    *,
    prompt: str,
    group_label: str,
) -> tuple[int, int]:
    if not folders:
        return 0, 0

    logger.info(f'\n  About to delete {len(folders)} {group_label} folder(s)')
    response = input(prompt).strip().lower()
    if response != 'y':
        return 0, 0

    deleted_count = 0
    failed_count = 0
    for folder in folders:
        try:
            shutil.rmtree(folder)
            deleted_count += 1
            logger.success(f' Deleted: {folder}')
        except Exception as error:
            failed_count += 1
            logger.error(f' Failed to delete: {folder}')
            logger.error(f'   Reason: {error}')
            logger.error('   → Please delete manually with administrator rights')

    return deleted_count, failed_count


def _delete_tool_versions(
    tool_versions_to_delete: list[Path],
    current_version_str: str,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    if not tool_versions_to_delete:
        return 0, 0

    logger.info(
        f'\n  Found {len(tool_versions_to_delete)} older xc-ce-utils tool version(s) (current: {current_version_str}):'
    )
    for folder in tool_versions_to_delete:
        logger.info(f'  - {folder}')

    if dry_run:
        logger.info('\n Dry-run mode - no tool versions will be deleted')
        return 0, 0

    response = input('Delete older xc-ce-utils tool versions? [y/N]: ').strip().lower()
    if response != 'y':
        return 0, 0

    deleted_count = 0
    failed_count = 0
    for folder in tool_versions_to_delete:
        try:
            shutil.rmtree(folder)
            deleted_count += 1
            logger.success(f' Deleted: {folder}')
        except Exception as error:
            failed_count += 1
            logger.error(f' Failed to delete: {folder}')
            logger.error(f'   Reason: {error}')
            logger.error('   → Please delete manually with administrator rights')

    return deleted_count, failed_count


def _log_cleanup_summary(deleted_count: int, failed_count: int) -> None:
    if deleted_count == 0 and failed_count == 0:
        return

    logger.info('\n Cleanup Summary:')
    logger.info(f'    Deleted: {deleted_count} folder(s)')
    if failed_count > 0:
        logger.info(f'    Failed:  {failed_count} folder(s) (see errors above)')


# ---------------------------------------------------------------------------
# config / creds / dynamic groups
# ---------------------------------------------------------------------------
def create_config_group(generator: 'DynamicCLIGenerator') -> click.Group:
    """Create the 'config' command group with setup/utility subcommands."""

    @click.group(
        name='config',
        help='Configuration and setup utilities',
        invoke_without_command=True,
    )
    @click.pass_context
    def config_group(ctx):
        """Configuration and setup utilities."""
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    config_group_obj = cast(click.Group, config_group)

    bazel_cfg = generator.full_config.get('BAZEL', '')
    if isinstance(bazel_cfg, bool):
        bazel_enabled = bazel_cfg
    else:
        bazel_enabled = str(bazel_cfg).strip().lower() in {
            'true',
            '1',
            'yes',
        }

    # Add hardcoded subcommands
    config_group_obj.add_command(create_force_setup_command(generator))
    config_group_obj.add_command(create_clean_older_versions_command(generator))
    if bazel_enabled:
        config_group_obj.add_command(create_refresh_bazel_cache_command(generator))
    # Developer self-service (always visible, no gating).
    config_group_obj.add_command(create_refresh_hooks_command(generator))
    config_group_obj.add_command(create_creds_group(generator))
    config_group_obj.add_command(
        create_vs_code_group(
            generator,
            include_developer_commands=True,
            include_maintainer_commands=False,
        )
    )

    validate, dump_config = _get_validate_and_dump_commands()

    config_group_obj.add_command(validate)
    config_group_obj.add_command(dump_config)

    return config_group_obj


def _clang_setup_enabled(generator: 'DynamicCLIGenerator') -> bool:
    """Return True only when project clang config exists and is enabled."""
    resolve_clang_config = _get_clang_config_resolver()

    repo_root = Path(getattr(generator, 'repo_root', Path.cwd()))
    clang_cfg = resolve_clang_config(generator.full_config, repo_root)
    return bool(clang_cfg) and bool(clang_cfg.get('enabled', False))


def create_config_devops_group(generator: 'DynamicCLIGenerator') -> click.Group:
    """Create the 'config-devops' command group for maintainer-only setup/regen commands."""

    @click.group(
        name='config-devops',
        help='Maintainer-only configuration and regeneration utilities',
        invoke_without_command=True,
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def config_devops_group(ctx):
        """Maintainer-only configuration and regeneration utilities."""
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    config_devops_group_obj = cast(click.Group, config_devops_group)
    config_devops_group_obj.add_command(create_full_setup_command(generator))
    if _clang_setup_enabled(generator):
        config_devops_group_obj.add_command(create_clang_setup_command(generator))
    config_devops_group_obj.add_command(create_hooks_setup_command(generator))
    config_devops_group_obj.add_command(
        create_vs_code_group(
            generator,
            include_developer_commands=False,
            include_maintainer_commands=True,
        )
    )

    return config_devops_group_obj


def create_creds_group(generator: 'DynamicCLIGenerator') -> click.Group:
    """Create the 'creds' command group for credential management."""
    create_creds_group = _get_creds_group_factory()
    return create_creds_group(generator)


def create_dynamic_group(name: str) -> click.Group:
    """Create a named click.Group for dynamic action grouping."""

    @click.group(name=name, help=f'{name} commands', invoke_without_command=True)
    @click.pass_context
    def group(ctx):
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    return group


# ---------------------------------------------------------------------------
# config vs-code group
# ---------------------------------------------------------------------------
def create_vs_code_group(
    generator: 'DynamicCLIGenerator',
    *,
    include_developer_commands: bool,
    include_maintainer_commands: bool,
) -> click.Group:
    """Create a nested ``vs-code`` command group with selectable command sets."""

    if include_developer_commands and include_maintainer_commands:
        help_text = 'VS Code configuration helpers'
    elif include_developer_commands:
        help_text = 'VS Code local developer helpers'
    else:
        help_text = 'VS Code maintainer regeneration helpers'

    @click.group(
        name='vs-code',
        help=help_text,
        invoke_without_command=True,
        hidden=(
            include_maintainer_commands
            and not include_developer_commands
            and role_gating.hidden_for_non_maintainers(generator.full_config)
        ),
    )
    @click.pass_context
    def vs_code_group(ctx):
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    vs_code_group_obj = cast(click.Group, vs_code_group)

    if include_developer_commands:
        vs_code_group_obj.add_command(create_check_extensions_command(generator))
        vs_code_group_obj.add_command(create_devmate_setup_command(generator))

    if include_maintainer_commands:
        vs_code_group_obj.add_command(create_regen_copilot_command(generator))
        vs_code_group_obj.add_command(create_regen_ws_conf_command(generator))
        vs_code_group_obj.add_command(create_regen_mcp_json_command(generator))

    return vs_code_group_obj


# ---------------------------------------------------------------------------
# Developer self-service commands (always visible, no role gating).
# ---------------------------------------------------------------------------
def create_refresh_hooks_command(
    _generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Re-deploy ``.git/hooks/pre-commit`` in local-only mode.

    This command does not regenerate committed code-quality files
    (``.pre-commit-config.yaml`` / ``.ruff.toml``).
    """

    @click.command(
        name='refresh-hooks',
        help='Re-deploy git hooks locally without regenerating committed pre-commit/ruff config files.',
    )
    @click.pass_context
    def refresh_hooks_command(_ctx):
        environment_setup_cls = _get_environment_setup_cls()
        git_hooks_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.git_hooks_phase',
            'GitHooksPhase',
        )

        logger.info('Refreshing git hooks (force=True)...')
        setup = environment_setup_cls()
        state = _call_setup_method(setup, '_load_setup_state')
        config = _call_setup_class_method(
            environment_setup_cls,
            '_load_configuration',
            setup.repo_path,
        )
        ctx_phase = _create_setup_context(
            setup,
            config,
            state,
            _SetupContextOptions(
                force=True,
                is_ci=False,
                extras={'include_maintainer_steps': False},
            ),
        )
        phase = git_hooks_phase_cls()
        if phase.should_run(ctx_phase):
            phase.run(ctx_phase)
            logger.success(' Git hooks refreshed.')
        else:
            logger.warning(' GitHooksPhase declined to run; nothing to refresh.')

    return refresh_hooks_command


def create_hooks_setup_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Run full hooks setup including committed pre-commit/ruff regen (maintainer-only)."""

    @click.command(
        name='hooks-setup',
        help='Run full git hooks setup and regenerate committed pre-commit/ruff configs (maintainer-only).',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def hooks_setup_command(_ctx):
        environment_setup_cls = _get_environment_setup_cls()
        git_hooks_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.git_hooks_phase',
            'GitHooksPhase',
        )

        role_gating.require_maintainer(generator.full_config)
        logger.info('Running full git hooks setup (force=True)...')

        setup = environment_setup_cls()
        state = _call_setup_method(setup, '_load_setup_state')
        config = _call_setup_class_method(
            environment_setup_cls,
            '_load_configuration',
            setup.repo_path,
        )
        is_ci = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

        ctx_phase = _create_setup_context(
            setup,
            config,
            state,
            _SetupContextOptions(
                force=True,
                is_ci=is_ci,
                extras={'include_maintainer_steps': True},
            ),
        )

        phase = git_hooks_phase_cls()
        if phase.should_run(ctx_phase):
            phase.run(ctx_phase)
            _call_setup_method(setup, '_save_setup_state', state)
            logger.success(' Full git hooks setup refreshed.')
        else:
            logger.warning(' GitHooksPhase declined to run; nothing to refresh.')

    return hooks_setup_command


def create_check_extensions_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Check VS Code extensions from the committed
    ``.vscode/extensions.json``. Bypasses the 3-week cooldown so devs who
    just installed VS Code (or the ``code`` CLI) can pick up extensions
    without waiting. No repo writes — user-local only.
    """

    @click.command(
        name='check-extensions',
        help='Check VS Code extensions from .vscode/extensions.json (user-local).',
    )
    @click.pass_context
    def check_extensions_command(_ctx):
        if os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true':
            logger.info('Skipping VS Code extension check in CI environment')
            return

        vscode_commands.refresh_vscode_extensions(generator)
        generator.print_final_summary()

    return check_extensions_command


def create_refresh_bazel_cache_command(
    _generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Refresh local Bazel cache configuration for developers.

    This updates user-local disk cache settings and regenerates project-local
    cache auth/config files when Bazel is enabled for the project.
    """

    @click.command(
        name='refresh-bazel-cache',
        help='Refresh local Bazel disk/remote cache settings (developer self-service).',
    )
    @click.pass_context
    def refresh_bazel_cache_command(_ctx):
        environment_setup_cls = _get_environment_setup_cls()
        bazel_disk_cache_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.bazel_phase',
            'BazelDiskCachePhase',
        )
        bazel_remote_cache_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.bazel_phase',
            'BazelRemoteCachePhase',
        )

        logger.info('Refreshing Bazel cache setup (force=True)...')
        setup = environment_setup_cls()
        state = _call_setup_method(setup, '_load_setup_state')
        config = _call_setup_class_method(
            environment_setup_cls,
            '_load_configuration',
            setup.repo_path,
        )
        is_ci = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

        ctx_phase = _create_setup_context(
            setup,
            config,
            state,
            _SetupContextOptions(
                force=True,
                is_ci=is_ci,
            ),
        )

        ran_any = False
        for phase in (
            bazel_disk_cache_phase_cls(),
            bazel_remote_cache_phase_cls(),
        ):
            if phase.should_run(ctx_phase):
                phase.run(ctx_phase)
                ran_any = True

        if ran_any:
            _call_setup_method(setup, '_save_setup_state', state)
            logger.success(' Bazel cache setup refreshed.')
        else:
            logger.warning(
                ' Bazel cache phases declined to run; Bazel may be disabled for this project.'
            )

    return refresh_bazel_cache_command


def create_devmate_setup_command(
    _generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Run DEVMATE_PAT setup on-demand (developer self-service)."""

    @click.command(
        name='devmate-setup',
        help='Setup/refresh DEVMATE_PAT now (developer self-service).',
    )
    @click.pass_context
    def devmate_setup_command(_ctx):
        environment_setup_cls = _get_environment_setup_cls()
        devmate_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.devmate_phase',
            'DevmatePATPhase',
        )

        logger.info('Running DEVMATE setup (force=True)...')
        setup = environment_setup_cls()
        state = _call_setup_method(setup, '_load_setup_state')
        config = _call_setup_class_method(
            environment_setup_cls,
            '_load_configuration',
            setup.repo_path,
        )
        is_ci = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

        ctx_phase = _create_setup_context(
            setup,
            config,
            state,
            _SetupContextOptions(
                force=True,
                is_ci=is_ci,
            ),
        )

        phase = devmate_phase_cls()
        if phase.should_run(ctx_phase):
            phase.run(ctx_phase)
            _call_setup_method(setup, '_save_setup_state', state)
            logger.success(' DEVMATE setup refreshed.')
        else:
            logger.info(' DEVMATE setup is already up-to-date.')

    return devmate_setup_command


# ---------------------------------------------------------------------------
# Maintainer-only regenerators (hidden + gated). Each one writes exactly
# one slice of committed state so PR reviews stay tractable.
# ---------------------------------------------------------------------------
def create_regen_copilot_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Regenerate the committed ``.github/copilot-instructions.md``."""

    @click.command(
        name='regen-copilot',
        help='Regenerate .github/copilot-instructions.md (maintainer-only).',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def regen_copilot_command(_ctx):
        role_gating.require_maintainer(generator.full_config)
        vscode_commands.regen_copilot_instructions(generator)
        generator.print_final_summary()

    return regen_copilot_command


def create_clang_setup_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Run clang setup on demand (maintainer-only)."""

    @click.command(
        name='clang-setup',
        help='Run clang installation/configuration setup now (maintainer-only).',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def clang_setup_command(_ctx):
        environment_setup_cls = _get_environment_setup_cls()
        clang_setup_phase_cls = _get_phase_class(
            'xc_ce_utils.core_engine.setup.phases.clang_phase',
            'ClangSetupPhase',
        )

        role_gating.require_maintainer(generator.full_config)
        logger.info('Running clang setup (force=True)...')

        setup = environment_setup_cls()
        state = _call_setup_method(setup, '_load_setup_state')
        config = _call_setup_class_method(
            environment_setup_cls,
            '_load_configuration',
            setup.repo_path,
        )
        is_ci = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

        ctx_phase = _create_setup_context(
            setup,
            config,
            state,
            _SetupContextOptions(
                force=True,
                is_ci=is_ci,
            ),
        )

        phase = clang_setup_phase_cls()
        if phase.should_run(ctx_phase):
            phase.run(ctx_phase)
            _call_setup_method(setup, '_save_setup_state', state)
            logger.success(' Clang setup refreshed.')
        else:
            logger.warning(
                ' Clang setup skipped (feature disabled, unsupported host, or CI environment).'
            )

    return clang_setup_command


def create_regen_ws_conf_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Regenerate the ``.vscode/`` config files (tasks, extensions, settings)."""

    @click.command(
        name='regen-ws-conf',
        help='Regenerate .vscode/ tasks/extensions/settings (maintainer-only).',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def regen_ws_conf_command(_ctx):
        role_gating.require_maintainer(generator.full_config)
        vscode_commands.regen_vscode_shared(generator)
        generator.print_final_summary()

    return regen_ws_conf_command


def create_regen_mcp_json_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Regenerate the committed ``.vscode/mcp.json`` from the MCP server registry.

    Kept separate from ``regen-ws-conf`` because MCP server
    additions/removals are typically reviewed independently (different
    security and IP implications than IDE tasks/extensions).
    """

    @click.command(
        name='regen-mcp-json',
        help='Regenerate .vscode/mcp.json from MCP server registry (maintainer-only).',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def regen_mcp_json_command(_ctx):
        role_gating.require_maintainer(generator.full_config)
        vscode_commands.regen_mcp_json(generator)
        generator.print_final_summary()

    return regen_mcp_json_command


def _delete_setup_folder(current_folder: Path) -> None:
    if current_folder.exists():
        logger.progress(f'Deleting {current_folder}...')
        shutil.rmtree(current_folder)
        logger.success(' Deleted setup folder')
        return
    logger.info("Setup folder doesn't exist, will create fresh")


def _run_setup_after_reset(
    setup_cls: type,
    *,
    include_maintainer_steps: bool,
    setup_label: str,
) -> None:
    logger.info(f'\n Running {setup_label}...')
    new_setup = setup_cls()
    if new_setup.run_setup(
        force=True,
        include_maintainer_steps=include_maintainer_steps,
    ):
        logger.success(f'\n {setup_label.capitalize()} completed successfully')
        return
    logger.error(f'\n {setup_label.capitalize()} completed with warnings')


def _perform_setup_reset(
    setup_cls: type,
    current_folder: Path,
    *,
    include_maintainer_steps: bool,
    setup_label: str,
) -> None:
    try:
        _delete_setup_folder(current_folder)
        _run_setup_after_reset(
            setup_cls,
            include_maintainer_steps=include_maintainer_steps,
            setup_label=setup_label,
        )
    except Exception as error:
        logger.error(f' Failed to complete {setup_label}: {error}')
        logger.error('You may need to manually delete the folder with administrator rights')
        raise


def create_force_setup_command(
    _generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Create the developer force-setup command for resetting current version setup."""

    @click.command(
        name='force-setup',
        help=' Delete current setup and force developer setup steps re-run',
    )
    @click.pass_context
    def force_setup_command(_ctx):
        """Delete current version setup folder and run developer setup steps."""
        environment_setup_cls = _get_environment_setup_cls()

        setup = environment_setup_cls()
        current_folder = setup.project_folder
        current_project_name = _call_setup_method(
            setup,
            '_get_project_name_from_config',
        )

        logger.warning(f'  This will delete setup for project: {current_project_name}')
        logger.warning(f'  Folder: {current_folder}')
        logger.warning('  All cached data (Conan packages, Bazel cache) will be removed')
        response = input('\nContinue with force setup? [y/N]: ').strip().lower()

        if response != 'y':
            logger.info('Force setup cancelled')
            return

        _perform_setup_reset(
            environment_setup_cls,
            current_folder,
            include_maintainer_steps=False,
            setup_label='force setup',
        )

    return force_setup_command


def create_full_setup_command(
    generator: 'DynamicCLIGenerator',
) -> click.Command:
    """Create the maintainer full-setup command for complete reset and setup."""

    @click.command(
        name='full-setup',
        help=' Delete current setup and force full setup (developer + maintainer steps, maintainer-only)',
        hidden=role_gating.hidden_for_non_maintainers(generator.full_config),
    )
    @click.pass_context
    def full_setup_command(_ctx):
        """Delete current setup folder and run full setup including maintainer steps."""
        environment_setup_cls = _get_environment_setup_cls()

        role_gating.require_maintainer(generator.full_config)

        setup = environment_setup_cls()
        current_folder = setup.project_folder
        current_project_name = _call_setup_method(
            setup,
            '_get_project_name_from_config',
        )

        logger.warning(f'  This will delete setup for project: {current_project_name}')
        logger.warning(f'  Folder: {current_folder}')
        logger.warning('  All cached data (Conan packages, Bazel cache) will be removed')
        response = input('\nContinue with full setup? [y/N]: ').strip().lower()

        if response != 'y':
            logger.info('Full setup cancelled')
            return

        _perform_setup_reset(
            environment_setup_cls,
            current_folder,
            include_maintainer_steps=True,
            setup_label='full setup',
        )

    return full_setup_command
