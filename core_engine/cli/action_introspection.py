"""
Action introspection helpers for the dynamic CLI.

Pure-ish helper functions that inspect action configurations to answer
questions such as "does this action contain CMake phases?", "what are the
default from/to phases?", or "is this variant allowed for this action?".

Extracted from :class:`DynamicCLIGenerator` in Phase 4 sub-commit 5 of
PR #47.  Behavioural change must be zero.  Each function accepts a
``generator`` argument used solely as a read-only view onto the loaded
configuration (``generator.actions``, ``generator.variant_matrix``,
``generator.project_config``, ``generator.repo_root``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError
from xc_ce_utils.core_engine.domain.variant_matrix import Variant
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


# ---------------------------------------------------------------------------
# Phase introspection
# ---------------------------------------------------------------------------
def has_step_types_recursive(phases: dict, target_step_types: list) -> bool:
    """Recursively check if any phase or nested step has one of the target step_types."""
    for _name, config in phases.items():
        if not isinstance(config, dict):
            continue
        if config.get('step_type') in target_step_types:
            return True
        nested = config.get('steps')
        if isinstance(nested, dict) and has_step_types_recursive(
            nested, target_step_types
        ):
            return True
    return False


def has_cmake_phases(generator: 'DynamicCLIGenerator', action: str) -> bool:
    """Check if action contains CMake phases (including nested steps)."""
    try:
        action_config = get_action_config(generator, action)
        phases = action_config.get('PHASES', action_config.get('phases', {}))
        return has_step_types_recursive(phases, ['cmake_set-up', 'cmake_build'])
    except Exception:
        return False


def has_bazel_phases(generator: 'DynamicCLIGenerator', action: str) -> bool:
    """Check if action contains Bazel phases (including nested steps)."""
    try:
        action_config = get_action_config(generator, action)
        phases = action_config.get('PHASES', action_config.get('phases', {}))
        return has_step_types_recursive(
            phases, ['bazel_build', 'bazel_test', 'bazel_run', 'bazel_query']
        )
    except Exception:
        return False


def has_docascode_phases(generator: 'DynamicCLIGenerator', action: str) -> bool:
    """Check if action contains docascode phases (including nested steps)."""
    try:
        action_config = get_action_config(generator, action)
        phases = action_config.get('PHASES', action_config.get('phases', {}))
        return has_step_types_recursive(phases, ['docascode'])
    except Exception:
        return False


# ---------------------------------------------------------------------------
# ccache helpers
# ---------------------------------------------------------------------------
def get_ccache_default_from_config(
    generator: 'DynamicCLIGenerator', action: str
) -> Optional[bool]:
    """Get ccache default setting from action config."""
    try:
        default_params = get_default_parameters(generator, action)

        ccache_setting = default_params.get('ccache')
        if ccache_setting is not None:
            if isinstance(ccache_setting, str):
                return ccache_setting.lower() in {'true', '1', 'yes', 'on'}
            return bool(ccache_setting)
        return None
    except Exception:
        return None


def get_default_ccache_dir(
    generator: 'DynamicCLIGenerator', variant_path: str
) -> Path:
    """Get default ccache directory based on project and variant."""
    home_dir = Path.home()

    project_name = generator.project_config.get(
        'package_name', 'unknown-project'
    )
    repo_name = generator.repo_root.name

    variant_suffix = variant_path.replace('/', '_').replace('\\', '_')

    cache_dir = (
        home_dir
        / f'.{project_name.lower()}'
        / f'ccache_{repo_name}_{variant_suffix}'
    )
    return cache_dir


# ---------------------------------------------------------------------------
# Action / parameter accessors
# ---------------------------------------------------------------------------
def get_action_config(
    generator: 'DynamicCLIGenerator', action: str
) -> Dict[str, Any]:
    """Get configuration for a specific action."""
    if action not in generator.actions:
        msg = f'Action unknown: {action}'
        raise ConfigurationError(msg)
    return generator.actions[action]


def get_default_parameters(
    generator: 'DynamicCLIGenerator', action: str
) -> Dict[str, Any]:
    """
    Get default parameters for an action based on the current environment.

    Returns:
        Dict containing default parameters from either DEFAULT_PARAMETERS_CX (CI)
        or DEFAULT_PARAMETERS (local), with appropriate fallbacks.
    """
    action_config = get_action_config(generator, action)

    if is_running_in_ci():
        if 'DEFAULT_PARAMETERS_CX' in action_config:
            logger.debug(f"Using CI-specific parameters for action '{action}'")
            return action_config['DEFAULT_PARAMETERS_CX']
        else:
            logger.debug(
                f"No CI-specific parameters found for action '{action}', using standard defaults"
            )
            return action_config.get(
                'DEFAULT_PARAMETERS',
                action_config.get('default_parameters', {}),
            )
    else:
        return action_config.get(
            'DEFAULT_PARAMETERS', action_config.get('default_parameters', {})
        )


# ---------------------------------------------------------------------------
# Variant constraint helpers
# ---------------------------------------------------------------------------
def validate_variant_constraints(
    generator: 'DynamicCLIGenerator', action: str, variant: Variant
) -> bool:
    """Validate if a variant is allowed for a specific action."""
    action_config = get_action_config(generator, action)

    only_variants = action_config.get('only_variants', [])
    omit_variants = action_config.get('omit_variants', [])

    variant_alias = str(variant.get_variant_alias())

    variant_name = None
    for name, var in generator.variant_matrix.get_variants().items():
        if var.get_variant_alias() == variant.get_variant_alias():
            variant_name = name
            break

    if only_variants:
        allowed = False
        for item in only_variants:
            item_str = str(item)
            if variant_alias == item_str or (
                variant_name and variant_name == item_str
            ):
                allowed = True
                break
        if not allowed:
            return False

    if omit_variants:
        for item in omit_variants:
            item_str = str(item)
            if variant_alias == item_str or (
                variant_name and variant_name == item_str
            ):
                return False

    return True


def get_allowed_variants_for_action(
    generator: 'DynamicCLIGenerator', action: str
) -> List[str]:
    """Get list of allowed variants for a specific action."""
    allowed_variants = []

    for (
        variant_name,
        variant,
    ) in generator.variant_matrix.get_variants().items():
        if validate_variant_constraints(generator, action, variant):
            allowed_variants.append(variant_name)

    return allowed_variants


def get_action_default_from_and_to_phases(
    generator: 'DynamicCLIGenerator', action: str
) -> Tuple[str, str, Dict[str, Any]]:
    """Get action default ``from`` and ``to`` phases plus the phase map.

    Note: declared return type is a 3-tuple. The original method was
    annotated ``Tuple[str, str]`` but returned 3 elements; the runtime
    behaviour is preserved verbatim.
    """
    action_config = get_action_config(generator, action)
    action_phases = action_config.get('phases', {})
    if len(action_phases) == 0:
        action_phases = action_config.get('PHASES', {})
        if len(action_phases) == 0:
            msg = f'Action {action} has no phases defined'
            raise ConfigurationError(msg)

    default_parameters = get_default_parameters(generator, action)

    env_type = 'CI' if is_running_in_ci() else 'local'
    has_cx_params = 'DEFAULT_PARAMETERS_CX' in action_config

    if is_running_in_ci() and has_cx_params:
        logger.info(
            f"Using CI-specific parameters for action '{action}': "
            f"from={default_parameters.get('from')} to={default_parameters.get('to')}"
        )
    else:
        logger.debug(
            f"Using {env_type} parameters for action '{action}': "
            f"from={default_parameters.get('from')} to={default_parameters.get('to')}"
        )

    action_phase_list = list(action_phases.keys())

    default_from = default_parameters.get('from', action_phase_list[0])
    default_to = default_parameters.get('to', action_phase_list[-1])

    return (default_from, default_to, action_phases)


def get_default_variant_alias(generator: 'DynamicCLIGenerator') -> str:
    """Get default variant alias."""
    return generator.variant_matrix.get_default_variant_alias()


# ---------------------------------------------------------------------------
# Help / metadata
# ---------------------------------------------------------------------------
def _is_unit_test_action(action_lower_case: str) -> bool:
    return action_lower_case in {
        'ut',
        'unit_test',
        'unit-test',
    } or action_lower_case.startswith(('ut_', 'unit_test', 'unit-test'))


def _get_default_help_string(
    action: str, action_lower_case: str, config_description: str
) -> str:
    help_string = f'custom: {action}'

    if action_lower_case == 'build':
        help_string = 'Build selected variant'
    elif 'doc' in action_lower_case:
        help_string = 'Generate documentation'
    elif 'sfa' in action_lower_case:
        help_string = 'Run Delta Static Code Analysis \n(Single File Analysis)'
    elif 'sca' in action_lower_case:
        help_string = 'Run Full Static Code Analysis'
    elif 'oss' in action_lower_case:
        help_string = 'Run Open Source Scan \n(reserved for CI/CD pipelines)'
    elif _is_unit_test_action(action_lower_case):
        help_string = 'Run unit tests'
    elif 'sbom' in action_lower_case:
        help_string = 'Generate Software Bill of Materials (SBOM)'
    elif config_description:
        help_string = config_description

    return help_string


def get_action_help_string(
    generator: 'DynamicCLIGenerator', action: str
) -> str:
    """Get a help string for a specific action."""
    action_config = get_action_config(generator, action)

    action_lower_case = action.lower()

    short_description = action_config.get('short_description', '')
    config_description = action_config.get('description', '')

    if short_description:
        help_string = short_description
    else:
        help_string = _get_default_help_string(
            action,
            action_lower_case,
            config_description,
        )

    only_variants = action_config.get('only_variants', [])
    omit_variants = action_config.get('omit_variants', [])
    no_variants = action_config.get('no_variants', False)
    if only_variants:
        help_string += (
            f" - Only variants: {', '.join(str(v) for v in only_variants)}"
        )
    if omit_variants:
        help_string += (
            f" - Variants omitted: {', '.join(str(v) for v in omit_variants)}"
        )
    if no_variants:
        help_string += ' - Variant independent'

    return help_string


def is_ci_only_action(generator: 'DynamicCLIGenerator', action: str) -> bool:
    """Check if an action is marked as CI/CX-only.

    An action is considered CI-only if it has ``only_cx_pipelines: true``
    in its configuration.
    """
    action_config = get_action_config(generator, action)
    return action_config.get('only_cx_pipelines', False)
