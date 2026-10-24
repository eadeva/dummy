"""
Variant Executor for XC-CE Build System

Module-level functions that orchestrate execution of build actions on one or
many variants. Extracted from ``DynamicCLIGenerator`` so the orchestrator class
remains a thin facade focused on CLI construction.

Each function takes a ``generator`` argument (the ``DynamicCLIGenerator``
instance) to access configuration, repository context, tracking helpers, etc.
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import rich_click as click

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    ConfigLoader,
    get_project_config_root,
)
from xc_ce_utils.core_engine.application import (
    ActionExecutionOptions,
    ExecutionAction,
    ExecutionRuntime,
    execute_action,
)
from xc_ce_utils.core_engine.cli import action_introspection as introspection
from xc_ce_utils.core_engine.cli.option_parser import parse_multiple_options
from xc_ce_utils.core_engine.config.action_configuration import (
    ActionConfiguration,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    BuildError,
    ConfigurationError,
)
from xc_ce_utils.core_engine.domain.variant_matrix import Variant, VariantMatrix
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci, run_command

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


LOCAL_VARIANT_PARALLEL_THRESHOLD = 4


@dataclass(frozen=True)
class VariantActionOptions:
    """Options for single-variant action execution."""

    clean: bool
    rebuild: bool
    no_cache: bool
    kwargs: Dict[str, Any]


@dataclass(frozen=True)
class _ActionConfigurationParts:
    """Resolved parts used to build ActionConfiguration."""

    build_type: str | None
    ccache_enabled: bool
    ccache_dir: Path | None
    from_phase: str
    to_phase: str
    additional_params: Dict[str, Any]
    artifact_params: Dict[str, Any]
    action_config: Dict[str, Any]
    dev_mode: bool


def get_max_parallel_builds(num_variants: int) -> int:
    """
    Determine optimal number of parallel builds based on system resources.

    Strategy:
    - CI: Use 2 workers (conservative for shared runners)
    - Local, few variants (<=4): Run all in parallel
    - Local, many variants (>4): Use 30-50% of CPU cores (min 2, max 8)
    - User override: Set MAX_PARALLEL_BUILDS env variable
    """
    if 'MAX_PARALLEL_BUILDS' in os.environ:
        try:
            user_max = int(os.environ['MAX_PARALLEL_BUILDS'])
            if user_max > 0:
                logger.info(f'Using user-configured MAX_PARALLEL_BUILDS={user_max}')
                return min(user_max, num_variants)
        except ValueError:
            logger.warning(
                f"Invalid MAX_PARALLEL_BUILDS value: {os.environ['MAX_PARALLEL_BUILDS']}, using auto-detection"
            )

    available_cores = multiprocessing.cpu_count()

    if is_running_in_ci():
        return 2

    if num_variants <= LOCAL_VARIANT_PARALLEL_THRESHOLD:
        return min(num_variants, available_cores)

    optimal = max(2, min(8, int(available_cores * 0.4)))
    return min(optimal, num_variants)


def setup_cpu_cores(generator: 'DynamicCLIGenerator', *, all_variants: bool = False) -> None:
    """Set up available CPU cores for parallel builds."""
    available_cores = multiprocessing.cpu_count()

    if is_running_in_ci():
        os.environ['AVAILABLE_CORES'] = str(max(2, int(available_cores * 0.3)))
        logger.info(
            f"CI detected: Setting AVAILABLE_CORES to {os.environ['AVAILABLE_CORES']} (total cores: {available_cores})"
        )
    elif all_variants:
        num_variants = len(generator.variant_matrix.get_variants())
        max_parallel = get_max_parallel_builds(num_variants)
        cores_per_build = max(2, int(available_cores / max_parallel))
        os.environ['AVAILABLE_CORES'] = str(cores_per_build)
        logger.info(
            f'Building all variants ({num_variants}): Setting AVAILABLE_CORES to {cores_per_build} per build (total cores: {available_cores}, {max_parallel} parallel)'
        )
    else:
        os.environ['AVAILABLE_CORES'] = str(available_cores)


def get_variants_to_execute(
    generator: 'DynamicCLIGenerator',
    action: str,
    *,
    all_variants: bool,
    variant_alias: str,
) -> List[Tuple[str, Variant]]:
    """
    Get list of variants to execute based on --all-variants flag or
    comma-separated -var parameter.

    Raises:
        ConfigurationError: If any specified variant is invalid
    """
    if all_variants:
        return _collect_all_allowed_variants(generator, action)

    return _collect_selected_allowed_variants(generator, action, variant_alias)


def _collect_all_allowed_variants(
    generator: 'DynamicCLIGenerator',
    action: str,
) -> List[Tuple[str, Variant]]:
    allowed_variants: List[Tuple[str, Variant]] = []
    for (
        variant_name,
        variant,
    ) in generator.variant_matrix.get_variants().items():
        if introspection.validate_variant_constraints(generator, action, variant):
            allowed_variants.append((variant_name, variant))
            continue

        logger.warning(f'Variant {variant_name} is not allowed for action {action}, skipping')
    return allowed_variants


def _collect_selected_allowed_variants(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant_alias: str,
) -> List[Tuple[str, Variant]]:
    allowed_variants: List[Tuple[str, Variant]] = []
    invalid_variants: List[str] = []

    for var_alias in [value.strip() for value in variant_alias.split(',')]:
        variant = _resolve_variant_or_none(generator, var_alias)
        if variant is None:
            invalid_variants.append(var_alias)
            continue

        if not introspection.validate_variant_constraints(generator, action, variant):
            logger.warning(f"Variant '{var_alias}' is not allowed for action '{action}', skipping")
            continue

        allowed_variants.append((_resolve_variant_name(generator, variant, var_alias), variant))

    _raise_for_invalid_variants(generator, invalid_variants)
    return allowed_variants


def _resolve_variant_or_none(
    generator: 'DynamicCLIGenerator',
    alias_or_path: str,
) -> Variant | None:
    try:
        return generator.variant_matrix.get_variant_by_alias_or_path(alias_or_path)
    except Exception:
        return None


def _resolve_variant_name(
    generator: 'DynamicCLIGenerator',
    target_variant: Variant,
    fallback_name: str,
) -> str:
    for name, variant in generator.variant_matrix.get_variants().items():
        if variant.get_variant_alias() == target_variant.get_variant_alias():
            return name
    return fallback_name


def _raise_for_invalid_variants(
    generator: 'DynamicCLIGenerator',
    invalid_variants: List[str],
) -> None:
    if not invalid_variants:
        return

    available_aliases = [
        variant.get_variant_alias() for variant in generator.variant_matrix.get_variants().values()
    ]
    error_msg = f"Invalid variant(s) specified: {', '.join(invalid_variants)}\n"
    error_msg += f"Available variants: {', '.join(available_aliases)}"
    logger.error(error_msg)
    raise ConfigurationError(error_msg)


def execute_variant_action(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant: Variant,
    options: VariantActionOptions,
) -> None:
    """Execute a single action against a single variant."""
    variant_config_options = variant.get_build_options()
    merged_options = _apply_build_option_overrides(
        variant_config_options,
        options.kwargs,
    )

    build_type, ccache_enabled, ccache_dir = _resolve_cache_and_build_settings(
        generator,
        action,
        variant,
        no_cache=options.no_cache,
        kwargs=options.kwargs,
    )

    dev_mode = _configure_dev_mode_environment(options.kwargs)
    additional_params, artifact_params = _configure_misc_and_artifact_environment(options.kwargs)
    from_phase, to_phase = _resolve_phase_range(generator, action, options.kwargs)
    action_config = introspection.get_action_config(generator, action)
    variant.build_options = merged_options

    config_parts = _ActionConfigurationParts(
        build_type,
        ccache_enabled,
        ccache_dir,
        from_phase,
        to_phase,
        additional_params,
        artifact_params,
        action_config,
        dev_mode,
    )

    config = _create_action_configuration(
        generator,
        action,
        variant,
        options,
        config_parts,
    )

    _run_execution_action(generator, action, config)


def _apply_build_option_overrides(
    variant_config_options: Dict[str, Any],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    merged_options = variant_config_options.copy()
    if not kwargs.get('build_option'):
        return merged_options

    parsed_options = parse_multiple_options(kwargs['build_option'])
    before = merged_options.copy()
    merged_options.update(parsed_options)

    _log_option_overrides(before, merged_options)
    _export_prefixed_env('BO_', parsed_options)
    logger.debug(f'Applied option overrides: {parsed_options}')
    return merged_options


def _log_option_overrides(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> None:
    added_or_changed = {key: value for key, value in after.items() if before.get(key) != value}
    if not added_or_changed:
        return

    logger.info('Overriden build options:')
    for key, value in added_or_changed.items():
        logger.info(f'  {key}: {value}')


def _export_prefixed_env(prefix: str, values: Dict[str, Any]) -> None:
    for key, value in values.items():
        env_key = f"{prefix}{key.upper().replace('-', '_')}"
        os.environ[env_key] = str(value)
        logger.debug(f'  env: {env_key}={value}')


def _resolve_cache_and_build_settings(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant: Variant,
    *,
    no_cache: bool,
    kwargs: Dict[str, Any],
) -> tuple[str | None, bool, Path | None]:
    has_cmake = introspection.has_cmake_phases(generator, action)
    has_bazel = introspection.has_bazel_phases(generator, action)
    requires_build_type = has_cmake or has_bazel

    build_type = _resolve_build_type(
        generator,
        action,
        variant,
        kwargs,
        requires_build_type=requires_build_type,
    )

    if not requires_build_type and kwargs.get('ccache'):
        logger.warning(f"ccache option ignored for action '{action}' (no CMake phases)")
        return build_type, False, None

    if no_cache and kwargs.get('ccache'):
        msg = 'Cannot use both --no-cache and --ccache flags together'
        raise click.UsageError(msg)

    ccache_enabled, ccache_dir = _resolve_ccache_settings(
        generator,
        action,
        variant,
        no_cache=no_cache,
        kwargs=kwargs,
    )

    if has_bazel:
        if no_cache:
            logger.info('Bazel remote cache disabled via --no-cache option')
        else:
            logger.debug('Bazel remote cache enabled (default)')

    return build_type, ccache_enabled, ccache_dir


def _resolve_build_type(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant: Variant,
    kwargs: Dict[str, Any],
    *,
    requires_build_type: bool,
) -> str | None:
    if not requires_build_type:
        return None

    if kwargs.get('build_type') is not None:
        build_type = kwargs['build_type']
        variant.settings['build_type'] = build_type
        return build_type

    default_parameters = introspection.get_default_parameters(generator, action)
    default_build_type = default_parameters.get(
        'build_type',
        default_parameters.get('build-type', 'RelWithDebInfo'),
    )
    variant.settings['build_type'] = default_build_type
    logger.info(f'Using default build type from config: {default_build_type}')
    return default_build_type


def _resolve_ccache_settings(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant: Variant,
    *,
    no_cache: bool,
    kwargs: Dict[str, Any],
) -> tuple[bool, Path | None]:
    has_cmake = introspection.has_cmake_phases(generator, action)
    if not has_cmake:
        return False, None

    if kwargs.get('ccache') is not None:
        ccache_enabled = bool(kwargs['ccache'])
        logger.info(f"ccache {'enabled' if ccache_enabled else 'disabled'} via CLI option")
    elif no_cache:
        ccache_enabled = False
        logger.info('ccache disabled via --no-cache option')
    else:
        config_default = introspection.get_ccache_default_from_config(
            generator,
            action,
        )
        if config_default is None:
            logger.debug('ccache will be auto-detected')
            ccache_enabled = False
        else:
            ccache_enabled = config_default
            logger.info(
                f"ccache {'enabled' if ccache_enabled else 'disabled'} via action configuration"
            )

    if not ccache_enabled:
        return False, None

    ccache_dir = introspection.get_default_ccache_dir(
        generator,
        variant.get_variant_path(),
    )
    logger.info(f'ccache directory: {ccache_dir}')
    return True, ccache_dir


def _configure_dev_mode_environment(kwargs: Dict[str, Any]) -> bool:
    dev_mode = bool(kwargs.get('dev_mode'))
    single_file = kwargs.get('single_file')

    if single_file:
        single_file_path = Path(single_file).resolve()
        if single_file_path.suffix.lower() != '.c':
            msg = f'Single-file build expects a .c file, got: {single_file_path.suffix}'
            raise click.BadParameter(msg, param_hint="'--single-file'")

        single_file_resolved = str(single_file_path).replace('\\', '/')
        os.environ['XC_CE_UTILS_DEVELOPER_MODE'] = 'true'
        os.environ['XC_CE_UTILS_SINGLE_FILE_BUILD'] = 'true'
        os.environ['XC_CE_UTILS_FULL_PATH_SINGLE_FILE'] = single_file_resolved
        logger.info(f' Single-file build activated: {single_file_resolved}')
        logger.info(' Developer mode activated (implied by --single-file)')
        return True

    if dev_mode:
        os.environ['XC_CE_UTILS_DEVELOPER_MODE'] = 'true'
        logger.info(' Developer mode activated')

    return dev_mode


def _configure_misc_and_artifact_environment(
    kwargs: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    additional_params = _parse_misc_params(kwargs)
    artifact_params = _parse_artifact_params(kwargs)
    return additional_params, artifact_params


def _parse_misc_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    if not kwargs.get('misc_param'):
        return {}

    additional_params = parse_multiple_options(kwargs['misc_param'])
    logger.info('Additional parameters:')
    for key, value in additional_params.items():
        logger.info(f'  {key}: {value}')

    _export_prefixed_env('MISC_PARAM_', additional_params)
    return additional_params


def _parse_artifact_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    if not kwargs.get('artifact'):
        return {}

    artifact_params = parse_multiple_options(kwargs['artifact'])
    logger.info('Artifact overrides:')
    for key, value in artifact_params.items():
        logger.info(f'  {key}: {value}')

    for key, value in artifact_params.items():
        _export_artifact_env_value(key, value)

    return artifact_params


def _export_artifact_env_value(key: str, value: Any) -> None:
    env_key = key.upper().replace('-', '_')
    string_value = str(value)

    if string_value.startswith('local:'):
        local_path = string_value[6:]
        os.environ[f'ARTIFACT_{env_key}'] = local_path
        os.environ[f'ARTIFACT_{env_key}_SOURCE'] = 'local'
        logger.info(f'  env: ARTIFACT_{env_key}={local_path} (local)')
        return

    if string_value.startswith('version:'):
        version = string_value[8:]
        os.environ[f'ARTIFACT_{env_key}_VERSION'] = version
        os.environ[f'ARTIFACT_{env_key}_SOURCE'] = 'remote'
        logger.info(f'  env: ARTIFACT_{env_key}_VERSION={version} (remote)')
        return

    os.environ[f'ARTIFACT_{env_key}'] = string_value
    logger.info(f'  env: ARTIFACT_{env_key}={string_value}')


def _resolve_phase_range(
    generator: 'DynamicCLIGenerator',
    action: str,
    kwargs: Dict[str, Any],
) -> tuple[str, str]:
    from_phase = kwargs.get('from')
    to_phase = kwargs.get('to')

    if kwargs.get('single_file'):
        to_phase = _resolve_single_file_to_phase(generator, action, to_phase)

    if from_phase and to_phase:
        return from_phase, to_phase

    default_from, default_to, _action_phases = introspection.get_action_default_from_and_to_phases(
        generator, action
    )

    if not from_phase:
        from_phase = default_from
    if not to_phase:
        to_phase = default_to

    return from_phase, to_phase


def _resolve_single_file_to_phase(
    generator: 'DynamicCLIGenerator',
    action: str,
    current_to_phase: str | None,
) -> str | None:
    action_config = introspection.get_action_config(generator, action)
    phases = action_config.get('PHASES', action_config.get('phases', {}))
    last_build_phase = _find_last_build_phase(phases)

    if last_build_phase is None:
        logger.warning(
            'Single-file build: no cmake_build/bazel_build phase found, running all phases'
        )
        return current_to_phase

    logger.info(f" Single-file build: stopping after phase '{last_build_phase}'")
    return last_build_phase


def _find_last_build_phase(phases: Dict[str, Any]) -> str | None:
    build_phase_types = {'cmake_build', 'bazel_build'}
    last_build_phase = None
    for phase_name, phase_config in phases.items():
        if not isinstance(phase_config, dict):
            continue
        if phase_config.get('step_type') in build_phase_types:
            last_build_phase = phase_name
    return last_build_phase


def _resolve_artifact_version(generator: 'DynamicCLIGenerator', variant: Variant) -> str:
    """Project-wide RB version, or the variant's own one for RB_VERSIONING 'variant-git-managed'."""
    version_pattern = getattr(variant, 'version_pattern', None)
    if version_pattern is None:
        return generator.artifact_version
    from xc_ce_utils.utils.git_version_resolver import (  # noqa: PLC0415
        export_git_managed_environment,
        version_string,
    )

    version_dict = variant.get_version()
    export_git_managed_environment(version_dict, version_pattern)
    return version_string(version_dict)


def _create_action_configuration(
    generator: 'DynamicCLIGenerator',
    action: str,
    variant: Variant,
    options: VariantActionOptions,
    parts: _ActionConfigurationParts,
) -> ActionConfiguration:
    single_file = options.kwargs.get('single_file')
    single_file_resolved = None
    if single_file:
        single_file_resolved = str(Path(single_file).resolve()).replace('\\', '/')

    return ActionConfiguration(
        artifact=generator.project_config['package_name'],
        version=_resolve_artifact_version(generator, variant),
        oss_config=generator.oss_config,
        splunk_config=generator.splunk_config,
        reporting_config=generator.full_config.get('REPORTING'),
        report_formats=generator.full_config.get('report_formats'),
        interactive_failure_assistance=bool(
            generator.full_config.get('INTERACTIVE_FAILURE_ASSISTANCE', True)
        ),
        action=action,
        build_type=parts.build_type,
        ccache_active=parts.ccache_enabled,
        ccache_dir=parts.ccache_dir,
        no_cache=options.no_cache,
        force_gen=options.kwargs.get('force_gen', False),
        from_phase=parts.from_phase,
        to_phase=parts.to_phase,
        additional_params=parts.additional_params,
        artifact_params=parts.artifact_params,
        artifactories=generator.artifactories,
        action_config=parts.action_config,
        variant=variant,
        variant_matrix=generator.variant_matrix,
        clean=options.clean,
        rebuild=options.rebuild,
        dev_mode=parts.dev_mode,
        single_file=single_file_resolved,
    )


def _run_execution_action(
    generator: 'DynamicCLIGenerator',
    action: str,
    config: ActionConfiguration,
) -> None:
    build_start = time.time()
    try:
        handler = ExecutionAction(config)
        handler.run()
        build_duration = time.time() - build_start
        generator.track_operation(f'Build Action: {action}', 'success', build_duration)
    except Exception:
        build_duration = time.time() - build_start
        generator.track_operation(f'Build Action: {action}', 'error', build_duration)
        raise


def build_python_command(variant_alias: str) -> int:
    """Re-invoke the current CLI process for a single variant.

    Used to fan out ``--all-variants``/multi-variant builds into one
    subprocess per variant (see ``_resolve_variant_runner`` in the
    application execution facade).
    """
    # Copy the original arguments
    args = sys.argv[1:]

    logger.debug(f'Original sys.argv[1:]: {args}')

    # Simple replacement: just replace comma-separated variant value with single variant
    final_args = []
    i = 0
    while i < len(args):
        arg = args[i]

        # Skip -all and --all-variants
        if arg in {'-all', '--all-variants'}:
            i += 1
            continue

        # Handle --variant=value format
        if arg.startswith(('--variant=', '-var=')):
            value = arg.split('=', 1)[1]
            if ',' in value or ' ' in value:
                prefix = arg.split('=', 1)[0]
                final_args.append(f'{prefix}={variant_alias}')
            else:
                final_args.append(arg)
            i += 1
            continue

        # Check if this is the value after -var or --variant
        if len(final_args) > 0 and final_args[-1] in {'-var', '--variant'}:
            # Replace multi-variant value (comma or space separated) with single variant
            if ',' in arg or ' ' in arg:
                final_args.append(variant_alias)
            else:
                final_args.append(arg)
            i += 1
            continue

        # Keep all other arguments untouched
        final_args.append(arg)
        i += 1

    logger.debug(f'Final args (with replaced variant): {final_args}')

    # Check if running from frozen executable (PyInstaller bundle)
    if getattr(sys, 'frozen', False):
        # Running from bundled executable - call the executable directly
        # sys.executable will be something like xc-ce_builder.exe
        command = [sys.executable, *final_args]
    else:
        # Running from Python source - use module execution
        # This ensures the subprocess uses the same venv/Python as the parent process
        command = [
            sys.executable,
            '-m',
            'xc_ce_utils.core_engine.cli.entrypoint',
            *final_args,
        ]

    logger.debug(f"Final command: {' '.join(command)}")

    # Run the command and wait for it to finish
    result = subprocess.run(command, check=False)
    return result.returncode


def execute_action_with_arguments(
    generator: 'DynamicCLIGenerator',
    ctx: click.Context,
    action: str,
    kwargs: Dict[str, Any],
) -> None:
    """Execute a build action with variant arguments.

    Acts as a CLI adapter: extracts click context values and forwards a
    typed request to the application facade.
    """

    execution_options = ActionExecutionOptions(
        clean=ctx.obj.get('clean', False),
        rebuild=ctx.obj.get('rebuild', False),
        no_cache=ctx.obj.get('no_cache', False),
        force_gen=ctx.obj.get('force_gen', False),
        all_variants=ctx.obj.get('all_variants', False),
        variant_alias=ctx.obj.get(
            'variant',
            generator.variant_matrix.get_default_variant_alias(),
        ),
        verbose=ctx.obj.get('verbose', False),
        kwargs=kwargs,
    )

    from rich.console import Console  # noqa: PLC0415

    def _report_unexpected_error(error: Exception) -> None:
        Console().print(f'[red]Unexpected error:[/red] {error}')

    runtime = ExecutionRuntime(
        variant_executor=sys.modules[__name__],
        build_python_command=build_python_command,
        build_error_cls=BuildError,
        configuration_error_cls=ConfigurationError,
        unexpected_error_reporter=_report_unexpected_error,
    )
    exit_code = execute_action(generator, action, execution_options, runtime)
    sys.exit(exit_code)


def build_all_variants(generator: 'DynamicCLIGenerator') -> None:
    """
    Build all variant combinations defined in the variant matrix.

    NOTE: This is legacy code path that references ``generator.context`` and
    ``generator.config`` which are not present on the current
    ``DynamicCLIGenerator``. Preserved verbatim for backwards compatibility;
    will raise ``AttributeError`` if invoked. No known callers.
    """
    config_loader = ConfigLoader()
    config_root = get_project_config_root(generator.context.repo_root)
    project_config_file = config_root / 'project' / 'project_conf.yml'
    if not project_config_file.exists():
        project_config_file = config_root / 'project' / 'project_conf.json'
        if not project_config_file.exists():
            msg = f'Project configuration file not found: {project_config_file}'
            raise ConfigurationError(msg)

    project_conf = config_loader.load_file(project_config_file)
    variant_combinations = _extract_variant_combinations(project_conf)

    action = generator.config.action or 'BUILD'
    build_type = generator.config.build_type.value

    for combination in variant_combinations:
        variant_values = combination['variants']
        variant_name = '_'.join([f'{k}_{v}' for k, v in variant_values.items()])

        script_path = str(Path(__file__).parent.resolve())

        variant_args = ' '.join([f"--{k.replace('_', '-')} {v}" for k, v in variant_values.items()])
        command = f'python {script_path}/build_cli.py {generator.config.action.lower()} {variant_args} --build-type {build_type}'

        if generator.config.from_phase:
            command += f' --from-phase {generator.config.from_phase}'
        if generator.config.to_phase:
            command += f' --to-phase {generator.config.to_phase}'
        if generator.config.clean:
            command += ' --clean'
        if generator.config.rebuild:
            command += ' --rebuild'

        logger.progress(f'Building variant: {variant_name}...')
        logger.progress(f'Command: {command}')

        log_file = (
            generator.context.logs_folder / variant_name / action.lower() / f'{action.lower()}.log'
        )
        run_command(command, log_file)


def _extract_variant_combinations(
    project_conf: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if 'variant_combinations' in project_conf:
        return [
            {'variants': combination.get('values', {})}
            for combination in project_conf['variant_combinations']
        ]

    if 'variant_matrix' in project_conf:
        variant_matrix = VariantMatrix(project_conf)
        return [
            {'variants': variant.get_variant_values()}
            for variant in variant_matrix.get_variants().values()
        ]

    msg = 'No variant_combinations or variant_matrix found in project configuration'
    raise ConfigurationError(msg)
