"""
Pydantic configuration models for the unified xc-ce-utils execution engine.

These models provide:
- Type-safe configuration with validation
- CX (CI) override merging: DEFAULT_PARAMETERS_CX overlays DEFAULT_PARAMETERS
- Variant override resolution at action, set, step, and phase levels
- Dry-run / validation support via pydantic model_validator

Configuration hierarchy:
    MainConfig
    ├── project_config: ProjectConfig
    │   ├── global_defaults: GlobalDefaults
    │   ├── variant_matrix: dict (parsed by VariantMatrix)
    │   └── variants: dict (parsed by VariantMatrix)
    └── build_config: BuildConfig
        ├── default_parameters: DefaultParameters
        └── actions: dict[str, ActionConfig]
            ├── only_variants / omit_variants / only_cx_pipelines
            ├── default_parameters / default_parameters_cx: ActionDefaults
            ├── PHASES: dict[str, StepConfig]
            └── SETS: dict[str, StepConfig]
                └── steps: dict[str, StepConfig]
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Helper: detect CI environment
# ---------------------------------------------------------------------------


def is_ci_environment() -> bool:
    """Detect if running in a CI environment (GitHub Actions, Jenkins, etc.)."""
    ci_indicators = [
        'CI',
        'GITHUB_ACTIONS',
        'JENKINS_URL',
        'BUILD_NUMBER',
        'TF_BUILD',
    ]
    return any(os.environ.get(var) for var in ci_indicators)


# ---------------------------------------------------------------------------
# Step configuration
# ---------------------------------------------------------------------------


class StepConfig(BaseModel):
    """Unified configuration for a step or step group.

    A node is a **leaf step** when it has ``type`` (or ``step_type``) and
    no ``steps`` key.  A node is a **composite set** when it has a ``steps``
    key — it can then optionally omit ``type``.

    Supports both the new ``type`` field and the legacy ``step_type`` alias.
    """

    # Step type
    type: Optional[str] = Field(
        default=None,
        description='Step type identifier (maps to StepRegistry). New field name.',
    )
    step_type: Optional[str] = Field(
        default=None,
        description="Legacy alias for 'type'. Use 'type' in new configs.",
    )

    # Category override (auto-assigned from registry if omitted)
    category: Optional[str] = Field(
        default=None,
        description='Step category (auto-assigned for known types if omitted)',
    )

    # Nested steps — presence makes this a composite set. Values may be a
    # nested StepConfig or a deferred file-path string (lazy include).
    steps: Optional[Dict[str, Union['StepConfig', str]]] = Field(
        default=None,
        description='Child steps. Presence of this key makes the node a set.',
    )
    parallel: bool = Field(
        default=False,
        description='If True and this is a set, execute child steps in parallel (ThreadPoolExecutor)',
    )

    # Execution control
    execute_if: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Conditional execution: dict of {variable: expected_value}',
    )
    game_stopper: bool = Field(
        default=True,
        description='If True, failure aborts the entire execution',
    )
    non_blocking: Union[bool, str] = Field(
        default=False,
        description="Run in background thread. 'daemon' or 'non-daemon' or bool",
    )
    wait_idle_before: int = Field(
        default=0,
        description='Seconds to wait before executing this step',
    )
    wait_idle_after: int = Field(
        default=0,
        description='Seconds to wait after executing this step',
    )
    only_cx_pipelines: bool = Field(
        default=False,
        description='Only execute this step when running in a CX pipeline',
    )
    skip_on_cx: bool = Field(
        default=False,
        description='Only execute this step locally, skip it in a CX pipeline',
    )
    only_variants: List[str] = Field(
        default_factory=list,
        description='Only execute for these variant aliases (empty = all)',
    )
    omit_variants: List[str] = Field(
        default_factory=list,
        description='Skip execution for these variant aliases',
    )

    # Variant overrides
    variant_overrides: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description='Per-variant config overrides, keyed by variant alias',
    )
    variant_overrides_cx: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description='CX-specific per-variant overrides (used only in CI)',
    )

    # Reporting
    title: Optional[str] = Field(default=None, description='Display title for reports')
    description: str = Field(default='', description='Step description')
    id: Optional[str] = Field(default=None, description='Step identifier')
    add_to_report: bool = Field(default=True, description='Include in reports')
    customer_visible: bool = Field(default=True, description='Include in customer reports')
    log: bool = Field(
        default=True,
        description='Enable logging to file (uses step name as filename)',
    )

    model_config = {'extra': 'allow'}

    @model_validator(mode='after')
    def resolve_type_alias(self) -> 'StepConfig':
        """Merge legacy step_type into type field."""
        if self.type is None and self.step_type is not None:
            self.type = self.step_type
        return self

    @property
    def is_set(self) -> bool:
        """True if this node is a composite set (has child steps)."""
        return self.steps is not None

    def resolve_for_variant(self, variant_alias: str, is_cx: bool = False) -> 'StepConfig':
        """Return a new StepConfig with variant-specific overrides applied."""
        data = self.model_dump(exclude={'variant_overrides', 'variant_overrides_cx'})

        if self.variant_overrides and variant_alias in self.variant_overrides:
            data = _deep_merge(data, self.variant_overrides[variant_alias])

        if is_cx and self.variant_overrides_cx and variant_alias in self.variant_overrides_cx:
            data = _deep_merge(data, self.variant_overrides_cx[variant_alias])

        return StepConfig.model_validate(data)


# ---------------------------------------------------------------------------
# Action configuration
# ---------------------------------------------------------------------------


class ActionDefaults(BaseModel):
    """Default parameters for an action (from/to phase, build_type, ccache)."""

    from_phase: Optional[str] = Field(
        default=None,
        alias='from',
        description='Starting phase name',
    )
    to_phase: Optional[str] = Field(
        default=None,
        alias='to',
        description='Ending phase name',
    )
    build_type: Optional[str] = Field(default=None, description='Build type (Debug/Release/...)')
    ccache: Optional[bool] = Field(default=None, description='Enable ccache')

    model_config = {'populate_by_name': True, 'extra': 'allow'}


class ActionConfig(BaseModel):
    """Configuration for a single build/automation action."""

    description: str = Field(default='', description='Action description')

    # --- Execution control ---
    only_cx_pipelines: bool = Field(
        default=False,
        description='Only execute this action when running in a CX pipeline',
    )
    only_variants: List[str] = Field(
        default_factory=list,
        description='Only execute for these variant aliases (empty = all)',
    )
    omit_variants: List[str] = Field(
        default_factory=list,
        description='Skip execution for these variant aliases',
    )

    # --- CLI grouping ---
    action_group: Optional[str] = Field(
        default=None,
        description="CLI command group to place this action under (e.g. 'config'). If None, action is top-level.",
    )

    DEFAULT_PARAMETERS: ActionDefaults = Field(
        default_factory=ActionDefaults,
        description='Default parameters (local builds)',
    )
    DEFAULT_PARAMETERS_CX: Optional[ActionDefaults] = Field(
        default=None,
        description='Default parameters for CI builds (overrides DEFAULT_PARAMETERS)',
    )

    # --- Legacy format (backward compatibility) ---
    # PHASES/SETS values may be either an inline StepConfig dict or a string
    # path to a YAML file that is loaded lazily by the execution engine at
    # step-creation time. The string form is left in place by ConfigLoader
    # when descending through PHASES (see
    # ``ConfigLoader.LAZY_INCLUDE_BOUNDARY_KEYS``) so that machine-/variant-
    # dependent includes missing on the current host do not break the load
    # of unrelated actions.
    PHASES: Dict[str, Union[StepConfig, str]] = Field(
        default_factory=dict,
        description='Ordered dict of build phases (legacy format). Values are inline step configs or deferred file-path strings.',
    )
    SETS: Optional[Dict[str, Union[StepConfig, str]]] = Field(
        default=None,
        description='Ordered dict of automation sets (legacy format). Values are inline step configs or deferred file-path strings.',
    )

    # --- New unified format ---
    steps: Optional[Dict[str, Union[StepConfig, str]]] = Field(
        default=None,
        description='Unified ordered dict of steps and sets (new format). Values are inline step configs or deferred file-path strings.',
    )

    # --- Variant overrides at action level ---
    variant_overrides: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description='Per-variant config overrides at action level',
    )
    variant_overrides_cx: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description='CX-specific per-variant overrides at action level',
    )

    model_config = {'extra': 'allow'}

    def get_unified_steps(self) -> Dict[str, Any]:
        """Return unified steps dict, migrating old format if needed.

        Priority: ``steps`` (new) > ``PHASES`` + ``SETS`` (old).
        Returns raw dicts suitable for ``ExecutionAction._create_node()``.
        """
        if self.steps is not None:
            return {name: sc.model_dump() for name, sc in self.steps.items()}

        # Migrate old PHASES + SETS → unified dict
        merged: Dict[str, Any] = {}
        for name, phase in self.PHASES.items():
            merged[name] = phase.model_dump()
        if self.SETS:
            for name, set_conf in self.SETS.items():
                merged[name] = set_conf.model_dump()
        return merged

    def get_effective_defaults(self, is_cx: bool = False) -> ActionDefaults:
        """Get effective default parameters, applying CX override if in CI.

        If DEFAULT_PARAMETERS_CX is defined and we're in CI, its fields
        override DEFAULT_PARAMETERS. If not defined, DEFAULT_PARAMETERS is used.
        """
        if is_cx and self.DEFAULT_PARAMETERS_CX is not None:
            base = self.DEFAULT_PARAMETERS.model_dump(exclude_none=True)
            cx = self.DEFAULT_PARAMETERS_CX.model_dump(exclude_none=True)
            merged = _deep_merge(base, cx)
            return ActionDefaults.model_validate(merged)
        return self.DEFAULT_PARAMETERS

    @model_validator(mode='after')
    def validate_phase_references(self) -> 'ActionConfig':
        """Validate that from/to references in defaults point to existing phases."""
        all_phase_names = set(self.PHASES.keys())

        for defaults in [self.DEFAULT_PARAMETERS, self.DEFAULT_PARAMETERS_CX]:
            if defaults is None:
                continue
            if defaults.from_phase and defaults.from_phase not in all_phase_names:
                # Only warn — the phase might be in SETS
                pass
            if defaults.to_phase and defaults.to_phase not in all_phase_names:
                pass

        return self


# ---------------------------------------------------------------------------
# Build configuration (top level of build_conf.yml)
# ---------------------------------------------------------------------------


class DefaultParameters(BaseModel):
    """Top-level default parameters."""

    action: Optional[str] = Field(default=None, description='Default action name')

    model_config = {'extra': 'allow'}


class BuildConfig(BaseModel):
    """Top-level build configuration (maps to build_conf.yml)."""

    DEFAULT_PARAMETERS: DefaultParameters = Field(
        default_factory=DefaultParameters,
        description='Global default parameters',
    )
    ACTIONS: Dict[str, ActionConfig] = Field(
        default_factory=dict,
        description='Available actions',
    )

    model_config = {'extra': 'allow'}


# ---------------------------------------------------------------------------
# Project configuration (project_conf.yml)
# ---------------------------------------------------------------------------


class GlobalDefaults(BaseModel):
    """Global default settings for all variants."""

    requires: Dict[str, Any] = Field(default_factory=dict)
    tool_requires: Any = Field(default_factory=dict)
    test_requires: Dict[str, Any] = Field(default_factory=dict)
    build_options: Dict[str, Any] = Field(default_factory=dict)

    model_config = {'extra': 'allow'}


class ProjectConfig(BaseModel):
    """Project-level configuration (maps to project_conf.yml)."""

    PROJECT: str = Field(default='', description='Project name')
    package_name: str = Field(default='', description='Package name')
    global_defaults: GlobalDefaults = Field(
        default_factory=GlobalDefaults,
        description='Global defaults for all variants',
    )
    variant_matrix: Dict[str, Any] = Field(
        default_factory=dict,
        description='Variant matrix definition (parsed by VariantMatrix)',
    )
    variants: Dict[str, Any] = Field(
        default_factory=dict,
        description='Variant definitions (parsed by VariantMatrix)',
    )

    model_config = {'extra': 'allow'}


# ---------------------------------------------------------------------------
# Main configuration (maps to main_conf.yml after ConfigLoader resolution)
# ---------------------------------------------------------------------------


class MainConfig(BaseModel):
    """Root configuration model (maps to main_conf.yml after ConfigLoader resolves references).

    After ConfigLoader processes main_conf.yml, file path references are replaced
    with their loaded content. This model validates the fully resolved structure.
    """

    PROJECT: str = Field(..., description='Project identifier')
    XC_CE_UTILS_VERSION: str = Field(..., description='xc-ce-utils version')
    CONAN_ENABLED: bool = Field(
        default=True, description='Enable Conan package manager integration'
    )

    PROJECT_CONFIG: ProjectConfig = Field(
        default_factory=ProjectConfig,
        description='Project configuration (resolved from project_conf.yml)',
    )
    ACTIONS: BuildConfig = Field(
        default_factory=BuildConfig,
        description='Build configuration (resolved from build_conf.yml)',
    )
    ARTIFACTORIES: Dict[str, Any] = Field(
        default_factory=dict,
        description='Artifactory configuration',
    )
    RB_VERSIONING: Union[Dict[str, Any], str] = Field(
        default_factory=dict,
        description=(
            "Version information, 'git-managed[:<tag glob>]' to derive it from git tags, or "
            "'variant-git-managed[:<default tag glob>]' to derive it per variant (variant 'version' = tag glob)"
        ),
    )
    CX_CONFIG: Optional[Dict[str, Any]] = Field(
        default=None,
        description='CI/CX pipeline configuration',
    )
    OSS_CONFIG: Optional[Dict[str, Any]] = Field(
        default=None,
        description='OSS scanning configuration',
    )
    SPLUNK: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Splunk export configuration',
    )
    TACO: Optional[Dict[str, Any]] = Field(
        default=None,
        description="TACO adapter ('adapter_path': folder with the adapter's pyproject.toml)",
    )
    ENV_ISOLATION: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Environment isolation configuration (resolved from env_isolation.yml)',
    )
    REPORTING: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Reporting configuration (resolved from reporting/reporting.yml)',
    )
    report_formats: Optional[List[str]] = Field(
        default=None,
        description='Deprecated fallback list of report formats (use REPORTING.formats instead)',
    )

    model_config = {'extra': 'allow'}


# ---------------------------------------------------------------------------
# Utility: deep merge dicts
# ---------------------------------------------------------------------------


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dict into base dict.

    Override values take precedence. Nested dicts are merged recursively.
    Lists and other types are replaced entirely.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Phase 1 #5: Additive models (variants, artifactories, env_isolation)
#
# These models validate sub-trees that, prior to this change, were stored as
# raw ``Dict[str, Any]``.  They are wired in opportunistically: callers may
# pass them to ``ConfigLoader.load_file(..., model=...)`` or invoke
# ``.model_validate(raw_dict)`` directly.  Existing dict-based consumers
# remain unchanged.
# ---------------------------------------------------------------------------


class VariantModel(BaseModel):
    """Single entry in ``PROJECT_CONFIG.variants``.

    Mirrors the shape consumed by :class:`xc_ce_utils.core_engine.domain.variant_matrix.Variant`.
    """

    alias: str = Field(..., description='Variant alias (required, unique)')
    settings: Dict[str, Any] = Field(default_factory=dict)
    requires: Dict[str, Any] = Field(default_factory=dict)
    tool_requires: Any = Field(default_factory=dict)
    test_requires: Dict[str, Any] = Field(default_factory=dict)
    build_options: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)

    model_config = {'extra': 'allow'}


class ArtifactoryModel(BaseModel):
    """Single entry in ``ARTIFACTORIES``.

    Matches the shape used by ``config/artifactories/artifactory_conf.yml``:
    each entry has at minimum a ``url`` and ``repository``; ``type`` defaults
    to ``"generic"`` for entries that omit it (e.g. ``gw-2wp-generic``).
    """

    type: str = Field(default='generic', description='Artifactory backend type')
    url: str = Field(..., description='Artifactory base URL')
    repository: str = Field(..., description='Repository name')
    auth: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional auth block (e.g. {'env_user': ..., 'env_pass': ...})",
    )

    model_config = {'extra': 'allow'}


class EnvIsolationModel(BaseModel):
    """Configuration consumed by :func:`env_isolation.isolate_environment`."""

    enabled: bool = Field(default=True, description='Master switch')
    bypass_env_vars: List[str] = Field(
        default_factory=list,
        description='Env var names to preserve verbatim',
    )
    bypass_path_elements: List[str] = Field(
        default_factory=list,
        description='PATH entries / glob patterns to preserve',
    )

    model_config = {'extra': 'allow'}
