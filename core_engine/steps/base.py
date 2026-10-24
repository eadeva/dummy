"""Unified step base classes.

Provides:
- ``ExecutionNode`` -- lightweight shared base for all execution nodes
- ``ExecutionStep`` -- leaf step with full lifecycle (validate/execute/pre/post),
  built-in test result collection, and JUnit XML report generation
- Status enums: ``StepConfStatus``, ``StepExecutionStatus``, ``StepEvaluationStatus``

Every step can produce test verdicts by populating ``self.test_results``
and calling ``self.report_results()``.  When the optional ``test:`` config
block is present, the step auto-reports results in post-processing with
test specification traceability via Sphinx-Needs IDs.  The ``test:`` block
is validated via the :class:`StepTestConfig` Pydantic model which references
a :class:`TestSpecRef` containing the Sphinx-Needs directive type and ID.

The ``ExecutionSet`` composite is defined in ``execution_set.py``.
"""

import json
import os
import time
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Optional, Set, Union

import yaml
from pydantic import BaseModel, Field, model_validator

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import ConfigLoader
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ContinueWithErrorsError,
    RuntimeConfigError,
    is_reported,
    mark_reported,
)
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

# ---------------------------------------------------------------------------
# Pydantic model for step-level test: config
# ---------------------------------------------------------------------------


class TestSpecRef(BaseModel):
    """Reference to a Sphinx-Needs test case directive.

    Used in both ``StepTestConfig`` and ``TimerThresholdTestConfig``.
    The ``id`` must match a directive ID in the project's RST test
    specification files (resolved at report-collection time via needs.json).
    """

    type: Literal['tc-sysf', 'tc-swf', 'tc-swc', 'tc-swu'] = Field(
        ..., description='Sphinx-Needs directive type'
    )
    id: str = Field(
        ...,
        description='Sphinx-Needs test case ID (e.g. TST_SysF_Flash_ProcedureAndExecution)',
    )


class StepTestConfig(BaseModel):
    """Validated schema for the step-level ``test:`` configuration block.

    The ``test_spec`` field references a Sphinx-Needs test case whose
    metadata (verification_criteria, verification_level, validates, etc.)
    is resolved at report-collection time from ``needs.json``.
    """

    suite: Optional[str] = Field(
        None,
        description='Suite name for report grouping (defaults to test_spec.id)',
    )
    test_spec: TestSpecRef = Field(..., description='Reference to a Sphinx-Needs test case')


class TimerThresholdTestConfig(BaseModel):
    """Validated schema for timer threshold tests.

    Used in ``timers[].threshold_test`` and ``time_threshold_test`` blocks.
    """

    time: float = Field(..., description='Threshold time in seconds')
    suite: Optional[str] = Field(
        None,
        description='Suite name for report grouping (defaults to test_spec.id)',
    )
    test_spec: TestSpecRef = Field(..., description='Reference to a Sphinx-Needs test case')


class BaseStepParams(BaseModel):
    """Base Pydantic model for all step parameter configurations."""

    type: Optional[str] = Field(
        default=None,
        description='Step type identifier (maps to StepRegistry).',
    )
    step_type: Optional[str] = Field(default=None, description="Legacy alias for 'type'.")
    category: Optional[str] = Field(default=None, description='Step category override.')
    steps: Optional[Dict[str, Any]] = Field(
        default=None, description='Child steps if this is a set.'
    )
    parallel: bool = Field(
        default=False,
        description='If True and this is a set, execute child steps in parallel.',
    )
    execute_if: Optional[Dict[str, Any]] = Field(default=None, description='Conditional execution.')
    game_stopper: bool = Field(default=True, description='If True, failure aborts execution.')
    non_blocking: Union[bool, str] = Field(default=False, description='Run in background.')
    wait_idle_before: int = Field(default=0, description='Seconds to wait before executing.')
    wait_idle_after: int = Field(default=0, description='Seconds to wait after executing.')
    only_cx_pipelines: bool = Field(default=False, description='Only execute in CI.')
    skip_on_cx: bool = Field(default=False, description='Only execute locally, skip in CI.')
    only_variants: List[str] = Field(
        default_factory=list, description='Only execute for these variants.'
    )
    omit_variants: List[str] = Field(default_factory=list, description='Skip for these variants.')
    variant_overrides: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None, description='Per-variant config overrides.'
    )
    variant_overrides_cx: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None, description='CX-specific overrides.'
    )
    title: Optional[str] = Field(default=None, description='Display title.')
    description: str = Field(default='', description='Step description.')
    id: Optional[str] = Field(default=None, description='Step identifier.')
    add_to_report: bool = Field(default=True, description='Include in reports.')
    customer_visible: bool = Field(default=True, description='Include in customer reports.')
    log: bool = Field(default=True, description='Enable logging to file.')
    test: Optional[Union[StepTestConfig, Dict[str, Any]]] = Field(
        default=None, description='Test config block.'
    )
    time_threshold_test: Optional[Union[TimerThresholdTestConfig, Dict[str, Any]]] = Field(
        default=None, description='Time threshold test block.'
    )
    set_env: Optional[Dict[str, Any]] = Field(
        default=None, description='Environment variables to set.'
    )
    set_global: Optional[Dict[str, Any]] = Field(
        default=None, description='Global variables to set.'
    )
    timers: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(
        default=None, description='Timer configuration.'
    )
    params: Optional[Dict[str, Any]] = Field(default=None, description='Step custom params.')
    allow_unknown_config_keys: bool = Field(
        default=False, description='Bypass unknown config validation.'
    )

    @model_validator(mode='after')
    def validate_type_presence(self) -> 'BaseStepParams':
        """Ensure type (or step_type) is present if this is a leaf step (no child steps)."""
        # 1. Alias step_type -> type for backward compatibility
        if self.type is None and self.step_type is not None:
            self.type = self.step_type

        # 2. If 'steps' is not present, then 'type' is mandatory
        if not self.steps and self.type is None:
            raise ValueError("Field 'type' (or 'step_type') is mandatory for leaf steps.")
        return self

    model_config = {'extra': 'allow'}


# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------


class StepConfStatus(Enum):
    CONF_INIT = 'INIT'
    CONFIGURED = 'OK'
    CONFIGURE_FAILED = 'FAILED'
    USER_INTERRUPTED = 'USER_INTERRUPT'


class StepExecutionStatus(Enum):
    NOT_EXECUTED = 'NOT_EXECUTED'
    EXECUTE_FAILED = 'FAILED'
    EXECUTE_SUCCESS = 'SUCCESS'
    USER_INTERRUPTED = 'USER_INTERRUPT'


class StepEvaluationStatus(Enum):
    NOT_APPLICABLE = 'n.a.'
    PASSED = 'PASSED'
    PARTLY_PASSED = 'PARTLY_PASSED'
    FAILED = 'FAILED'
    USER_INTERRUPTED = 'USER_INTERRUPT'


class _ConfigAccessTrackingDict(dict):
    """Dict wrapper that records top-level key access during step runtime."""

    def __init__(self, payload: Dict[str, Any]):
        super().__init__(payload)
        self._accessed_keys: Set[str] = set()

    def __getitem__(self, key):
        self._accessed_keys.add(str(key))
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._accessed_keys.add(str(key))
        return super().get(key, default)

    def __contains__(self, key):
        self._accessed_keys.add(str(key))
        return super().__contains__(key)

    def pop(self, key, default=None):
        self._accessed_keys.add(str(key))
        return super().pop(key, default)

    def setdefault(self, key, default=None):
        self._accessed_keys.add(str(key))
        return super().setdefault(key, default)

    @property
    def accessed_keys(self) -> Set[str]:
        return set(self._accessed_keys)


# ---------------------------------------------------------------------------
# ExecutionNode  lightweight shared base for all nodes (steps and sets)
# ---------------------------------------------------------------------------


class ExecutionNode(ABC):
    """Lightweight base shared by ExecutionStep (leaf) and ExecutionSet (composite).

    Holds the fields that both leaf steps and composite sets need:
    name, config, context, execution control flags, status, and reporting fields.
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        self.name = name
        self.config = config
        self.context = context

        # --- Execution control ---
        self.omit_variants: List[str] = config.get('omit_variants', [])
        self.only_variants: List[str] = config.get('only_variants', [])
        self.only_cx_pipelines: bool = config.get('only_cx_pipelines', False)
        self.skip_on_cx: bool = config.get('skip_on_cx', False)
        self.game_stopper: bool = config.get('game_stopper', True)
        self.non_blocking = config.get('non_blocking', False)
        self.execute_if: Optional[Dict] = config.get('execute_if')

        # --- Omitted resolution ---
        self.omitted = self._resolve_omitted()

        # --- Status ---
        self.execution_status = StepExecutionStatus.NOT_EXECUTED

        # --- Reporting ---
        self.title: str = config.get('title', self.name)
        self.description: str = config.get('description', '')

    def _resolve_omitted(self) -> bool:
        """Check execution control flags and return True if this node should be skipped."""
        if self.only_cx_pipelines and not is_running_in_ci():
            logger.debug(
                f'[{self.name}] Skipping execution (only_cx_pipelines=True and not in CX pipeline)'
            )
            return True

        if self.skip_on_cx and is_running_in_ci():
            logger.debug(f'[{self.name}] Skipping execution (skip_on_cx=True and in CX pipeline)')
            return True

        variant = getattr(self.context, 'variant', None)
        current_variant = variant.get_variant_alias() if variant is not None else None
        if self.only_variants and current_variant not in self.only_variants:
            logger.debug(
                f'[{self.name}] Skipping execution (current variant: {current_variant} not in only_variants)'
            )
            return True

        if self.omit_variants and current_variant in self.omit_variants:
            logger.debug(
                f'[{self.name}] Skipping execution (current variant: {current_variant} in omit_variants)'
            )
            return True

        return False

    @abstractmethod
    def run(self) -> None:
        """Run this node. Called by the execution engine."""
        ...

    @property
    def type(self) -> str:
        return self.config.get('type', self.config.get('step_type', ''))

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'


# ---------------------------------------------------------------------------
# ExecutionStep  leaf step with full lifecycle
# ---------------------------------------------------------------------------


class ExecutionStep(ExecutionNode):
    """Leaf execution step with full lifecycle: validate -> pre -> execute -> post.

    Combines config loading via ConfigLoader, validate/execute pattern,
    folder helpers, status tracking, pre/post processing,
    game_stopper, non_blocking, execute_if, wait_idle, timers, logging,
    output checking, and abort handling.

    Class-level metadata (override in subclasses for introspection):

    - ``config_fields``: declared configuration parameters
    - ``env_vars``: environment variables expected/set at runtime
    - ``args``: declared argument schema
    """

    # Class-level metadata  overridden by subclasses
    config_fields: ClassVar[Dict[str, Any]] = {}
    env_vars: ClassVar[Dict[str, str]] = {}
    args: ClassVar[Dict[str, Any]] = {}

    _BASE_ALLOWED_CONFIG_KEYS: ClassVar[Set[str]] = {
        'type',
        'step_type',
        'category',
        'steps',
        'parallel',
        'execute_if',
        'game_stopper',
        'non_blocking',
        'wait_idle_before',
        'wait_idle_after',
        'only_cx_pipelines',
        'skip_on_cx',
        'only_variants',
        'omit_variants',
        'variant_overrides',
        'variant_overrides_cx',
        'title',
        'description',
        'id',
        'add_to_report',
        'customer_visible',
        'log',
        'test',
        'time_threshold_test',
        'set_env',
        'set_global',
        'timers',
        'params',
        'allow_unknown_config_keys',
    }

    build_folder: Path = None
    log_folder: Path = None
    reports_folder: Path = None
    deploy_folder: Path = None

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        """Initialize the execution step.

        Args:
            name: Step/phase name (e.g., "cmake-build", "t32_connect").
            config: Phase/step configuration dict (from YAML/JSON config).
            context: Execution context (``ActionConfiguration``).
        """
        # Initialize shared node fields first (sets self.omitted, etc.)
        super().__init__(name, config, context)

        # Early exit if omitted  no need to set up the rest
        if self.omitted:
            return

        self.get_step_build_folder()  # Ensure build folder exists for this step
        self.get_step_log_folder()  # Ensure log folder exists for this step
        self.get_step_reports_folder()  # Just getting the path, reports folder will be created by steps that need it
        self.get_step_deploy_folder()  # Just getting the path, reports folder will be created by steps that need it

        logger.trace(f'[{self.name}] Build folder: {self.build_folder}')
        logger.trace(f'[{self.name}] Log folder: {self.log_folder}')
        logger.trace(f'[{self.name}] Reports folder: {self.reports_folder}')
        logger.trace(f'[{self.name}] Config: {config}')

        # --- Config loading ---
        # Dump config through ConfigLoader to resolve any file references
        # and env variable substitutions within the phase config
        # Write resolved config back for traceability
        # Exclude internal keys that may contain non-serializable objects
        # (e.g. COM handles in _resources)
        INTERNAL_KEYS = {'_resources', '_global_variables'}
        serializable_config = {k: v for k, v in self.config.items() if k not in INTERNAL_KEYS}

        # Grab global_variables early so ConfigLoader can resolve $VAR{} references
        global_variables_local = config.get(
            '_global_variables', getattr(context, 'global_variables', {})
        )

        phase_config_dump = self.build_folder / f'step_config_{self.name}.yml'
        with open(phase_config_dump, 'w') as f:
            yaml.dump(
                serializable_config,
                f,
                default_flow_style=False,
                sort_keys=False,
            )

        config_loader = ConfigLoader(global_variables=global_variables_local)
        try:
            # Step payloads may contain file paths like *.json that must stay
            # as plain strings (not auto-included), while still resolving
            # variable and environment placeholders.
            self.config = config_loader.load_file(
                phase_config_dump,
                allow_missing_env_vars=False,
                defer_includes=True,
                normalize_deferred_paths=False,
            )
        except Exception as e:
            raise RuntimeConfigError(f'[{self.name}] {e}')

        logger.trace(f'[{self.name}] Config loaded')

        # Write resolved config back for traceability
        with open(phase_config_dump, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

        logger.trace(f'[{self.name}] Config dumped to {phase_config_dump}')

        self.wait_idle_before: int = self.config.get('wait_idle_before', 0)
        self.wait_idle_after: int = self.config.get('wait_idle_after', 0)

        # --- Status tracking ---
        self.conf_status = StepConfStatus.CONFIGURED
        self.test_status = StepEvaluationStatus.NOT_APPLICABLE

        # --- Test results (available on every step) ---
        from xc_ce_utils.core_engine.reporting.adapters.exporters import (  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415
            TestResult,
        )

        self.test_results: List['TestResult'] = []

        # --- Test configuration (optional `test:` block) ---
        raw_test_config = self.config.get('test', None)
        self.test_config: Optional[StepTestConfig] = None
        if raw_test_config is not None:
            try:
                self.test_config = StepTestConfig(**raw_test_config)
            except Exception as e:
                raise RuntimeConfigError(f'[{self.name}] Invalid test: config  {e}')

        # --- Timing ---
        self.step_timer = None

        # --- Time threshold test (optional `time_threshold_test:` block) ---
        raw_time_threshold = self.config.get('time_threshold_test', None)
        self.time_threshold_test: Optional[TimerThresholdTestConfig] = None
        if raw_time_threshold is not None:
            try:
                self.time_threshold_test = TimerThresholdTestConfig(**raw_time_threshold)
            except Exception as e:
                raise RuntimeConfigError(f'[{self.name}] Invalid time_threshold_test: config  {e}')

        # --- Logging and reporting ---
        self.id: Optional[str] = self.config.get('id', None)
        self.add_to_report: bool = self.config.get('add_to_report', True)
        # For customer reports, default to True unless explicitly set to False
        self.customer_visible: bool = self.config.get('customer_visible', True)
        self.result_string: List[str] = []
        self.log_enabled: bool = self.config.get('log', True)
        self.allow_unknown_config_keys: bool = bool(
            self.config.get('allow_unknown_config_keys', False)
        )

        # --- Resource references (shared resource pool) ---
        # Injected by ExecutionAction._create_node(), fall back to context attrs
        self.resources: Dict = config.get('_resources', getattr(context, 'resources', {}))
        self.global_variables: Dict = config.get(
            '_global_variables', getattr(context, 'global_variables', {})
        )

        # Wrap config to track which top-level keys are actually consumed by runtime.
        self.config = _ConfigAccessTrackingDict(self.config)

        # Logging in trace level all the initialized attributes for debugging
        logger.trace(f'[{self.name}] Initialized with attributes:')
        for attr, value in self.__dict__.items():
            if attr != 'context':
                logger.trace(f'  {attr}: {value}')

    # ------------------------------------------------------------------
    # Core interface (must/can be overridden by subclasses)
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Validate step configuration. Override in subclasses if needed."""
        pass

    @abstractmethod
    def execute(self) -> None:
        """Execute the step. Must be implemented by subclasses."""
        ...

    def run(self) -> None:
        """Run the full step lifecycle: validate -> pre -> execute -> post.

        This is the method called by the execution engine. Subclasses
        should override ``execute()`` (and optionally ``validate()``),
        not this method.

        When ``log_enabled`` is True, a file logger is active during the
        entire lifecycle so every ``logger.*`` call is written to
        ``<log_folder>/<step_name>.log`` automatically.
        """
        if self.omitted:
            logger.info(
                f'[{self.name}] Step is omitted based on configuration. Skipping execution.'
            )
            return

        logger.log_phase_header(f'STEP {self.name.upper()}')
        with logger.step_scope(self.name):
            try:
                if self.log_enabled:
                    log_path = self.log_folder / f'{self.name}.log'
                    with logger.file_scope(self.name, log_path):
                        try:
                            self.validate()
                            self._validate_unknown_config_keys()
                            self.pre_processing()
                            self.execute()
                        except Exception as exc:
                            self._log_step_exception(exc)
                            raise
                else:
                    try:
                        self.validate()
                        self._validate_unknown_config_keys()
                        self.pre_processing()
                        self.execute()
                    except Exception as exc:
                        self._log_step_exception(exc)
                        raise
                self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            except Exception:
                self.execution_status = StepExecutionStatus.EXECUTE_FAILED
                raise
            finally:
                self.post_processing()
                logger.log_phase_header(f'STEP {self.name.upper()} - END')

    def _log_step_exception(self, exc: Exception) -> None:
        """Print an unreported step failure once: summary header plus traceback."""
        if is_reported(exc):
            return
        logger.error(
            'EXCEPTION_SUMMARY '
            f'scope=step step={self.name} '
            f'step_type={self.type or "unknown"} '
            'category=StepExecutionError '
            f'exception_type={type(exc).__name__}\n'
            f'{traceback.format_exc()}'
        )
        mark_reported(exc)

    def _validate_unknown_config_keys(self) -> None:
        """Validate step configuration against its declared Pydantic params_model.

        Keys are consumed at runtime and we validate that no undefined fields
        are passed using the step's specific Pydantic params_model.
        """
        if self.allow_unknown_config_keys:
            return

        if not isinstance(self.config, _ConfigAccessTrackingDict):
            return

        # If the step class defines a Pydantic params_model, use it!
        params_model = getattr(self.__class__, 'params_model', None)
        if params_model is not None:
            # We filter out internal keys (keys starting with '_') before validating
            clean_config = {k: v for k, v in self.config.items() if not str(k).startswith('_')}
            try:
                # model_validate will validate types, missing keys, and extra keys (if extra='forbid')
                params_model.model_validate(clean_config)
            except Exception as e:
                # Formatting a clean error message from Pydantic's ValidationError
                # e.g., if there's an extra field, Pydantic raises: "1 validation error for X... extra fields not permitted"
                raise RuntimeConfigError(
                    f"[{self.name}] Configuration validation failed for step_type '{self.type}':\n{e}"
                )
            return

        # Fallback for unmigrated legacy classes using `config_fields`
        allowed = set(self._BASE_ALLOWED_CONFIG_KEYS)
        class_fields = getattr(self.__class__, 'config_fields', {})
        if isinstance(class_fields, dict):
            allowed.update(str(key) for key in class_fields.keys())

        accessed = self.config.accessed_keys
        unknown_unused = sorted(
            key
            for key in self.config.keys()
            if str(key) not in allowed and str(key) not in accessed and not str(key).startswith('_')
        )

        if unknown_unused:
            step_type = self.type or 'unknown'
            keys = ', '.join(unknown_unused)
            msg = (
                f"[{self.name}] Unknown/unused configuration key(s) for step_type '{step_type}': {keys}. "
                'Fix the key name, or set allow_unknown_config_keys: true for this step if intentional.'
            )

    # ------------------------------------------------------------------
    # Pre/Post processing (lifecycle hooks)
    # ------------------------------------------------------------------

    def pre_processing(self) -> None:
        """Pre-processing: timers (when: before), time_threshold_test, wait_idle_before."""
        logger.debug(f'[{self.name}] Preparing step')

        # Lazy import to avoid circular dependency / heavy import at load time
        from xc_ce_utils.rb_timer.rb_timer import RBTimer

        self.step_timer = RBTimer(self.name)

        # --- Generic timers with when: before ---
        timer_conf = self.config.get('timers')
        if timer_conf:
            timer_entries = timer_conf if isinstance(timer_conf, list) else [timer_conf]
            for entry in timer_entries:
                if isinstance(entry, dict) and entry.get('when', 'after').lower() == 'before':
                    self._process_timer_action(entry)

        # --- time_threshold_test: auto-start a timer for this step ---
        if self.time_threshold_test:
            self._process_timer_action(
                {
                    'id': f'{self.name}_time_threshold',
                    'action': 'start',
                    'threshold_test': self.time_threshold_test.model_dump(),
                }
            )

        if self.wait_idle_before > 0:
            logger.info(f'[{self.name}] Waiting {self.wait_idle_before}s before execution')
            try:
                time.sleep(self.wait_idle_before)
            except KeyboardInterrupt:
                self.execution_status = StepExecutionStatus.USER_INTERRUPTED
                raise AbortError(f'[{self.name}] Interrupted by user during pre-wait')

    def post_processing(self) -> None:
        """Post-processing: set_env, set_global, timer actions, wait_idle_after."""
        # --- Generic set_env: set environment variables ---
        set_env = self.config.get('set_env')
        if set_env and isinstance(set_env, dict):
            for var_name, var_value in set_env.items():
                os.environ[str(var_name)] = str(var_value)
                logger.info(f'[{self.name}] set_env: {var_name}={var_value}')

        # --- Generic set_global: set global variables ---
        set_global = self.config.get('set_global')
        if set_global and isinstance(set_global, dict):
            for var_name, var_value in set_global.items():
                self.global_variables[str(var_name)] = var_value
                logger.info(f'[{self.name}] set_global: {var_name}={var_value}')

        # --- time_threshold_test: auto-stop the step timer ---
        if self.time_threshold_test:
            self._process_timer_action(
                {
                    'id': f'{self.name}_time_threshold',
                    'action': 'stop',
                }
            )

        # --- Generic timers: start/stop/checkpoint on shared timers ---
        timer_conf = self.config.get('timers')
        if timer_conf:
            timer_entries = timer_conf if isinstance(timer_conf, list) else [timer_conf]
            for entry in timer_entries:
                if isinstance(entry, dict) and entry.get('when', 'after').lower() != 'before':
                    self._process_timer_action(entry)

        # --- Auto-report test results when test: is configured ---
        if self.test_config and self.test_results:
            suite_name = self.test_config.suite or self.test_config.test_spec.id
            props = {
                'test_spec_id': self.test_config.test_spec.id,
                'test_spec_type': self.test_config.test_spec.type,
            }
            # report_results will also enrich individual TestResult objects
            self.report_results(
                suite_name=suite_name,
                properties=props,
            )

        if self.wait_idle_after > 0 and self.execution_status != StepExecutionStatus.EXECUTE_FAILED:
            logger.info(f'[{self.name}] Waiting {self.wait_idle_after}s after execution')
            try:
                time.sleep(self.wait_idle_after)
            except KeyboardInterrupt:
                self.execution_status = StepExecutionStatus.USER_INTERRUPTED
                raise AbortError(f'[{self.name}] Interrupted by user during post-wait')

        if self.step_timer is not None:
            self.step_timer.stop()
            if self.execution_status == StepExecutionStatus.EXECUTE_FAILED:
                logger.error(
                    f'[{self.name}] Failed '
                    f'(elapsed={self.step_timer.get_elapsed_time_string()})'
                )
            else:
                logger.success(
                    f'[{self.name}] Completed '
                    f'(elapsed={self.step_timer.get_elapsed_time_string()})'
                )

        self._write_execution_step_report()

    def _write_execution_step_report(self) -> None:
        """Write a canonical execution-step artifact for unified reporting."""
        try:
            reports_folder = self.get_step_reports_folder()
            reports_folder.mkdir(parents=True, exist_ok=True)

            # Stable in-process sequence for execution ordering in reports.
            try:
                current_index = int(getattr(self.context, '_execution_step_counter', 0))
            except Exception:
                current_index = 0
            execution_index = current_index + 1
            self.context._execution_step_counter = execution_index

            elapsed_seconds = None
            elapsed_human = ''
            if self.step_timer is not None:
                try:
                    elapsed_seconds = float(self.step_timer.get_elapsed_time(unit='s'))
                except Exception:
                    elapsed_seconds = None
                try:
                    elapsed_human = self.step_timer.get_elapsed_time_string()
                except Exception:
                    elapsed_human = ''

            execution_status = (
                self.execution_status.value
                if isinstance(self.execution_status, StepExecutionStatus)
                else str(self.execution_status)
            )
            test_status = (
                self.test_status.value
                if isinstance(self.test_status, StepEvaluationStatus)
                else str(self.test_status)
            )

            payload = {
                'report_kind': 'execution-step',
                'schema_version': '1.0.0',
                'execution_index': execution_index,
                'action': os.getenv('XC_CE_UTILS_ACTION', ''),
                'variant': os.getenv('XC_CE_UTILS_VARIANT_ALIAS', ''),
                'step': {
                    'name': self.name,
                    'step_type': self.type,
                    'title': self.title,
                    'description': self.description,
                    'game_stopper': self.game_stopper,
                    'non_blocking': self.non_blocking,
                    'customer_visible': self.customer_visible,
                    'script_ref': self._resolve_script_ref_for_reporting(),
                },
                'status': {
                    'execution_status': execution_status,
                    'test_status': test_status,
                },
                'timing': {
                    'elapsed_seconds': elapsed_seconds,
                    'elapsed_human': elapsed_human,
                },
                'params': self.config.get('params', self.config),
                'results': [str(item) for item in self.result_string],
                'artifacts': {
                    'step_log': str(self.get_step_log_folder() / f'{self.name}.log'),
                    'step_jsonl': str(self.get_step_log_folder() / f'{self.name}.jsonl'),
                    'step_reports_folder': str(reports_folder),
                    'step_build_folder': str(self.get_step_build_folder()),
                },
            }

            output_path = reports_folder / 'execution-step.json'
            output_path.write_text(
                json.dumps(payload, indent=2, default=str),
                encoding='utf-8',
            )
            logger.trace(f'[{self.name}] Execution step report written: {output_path}')
        except Exception as exc:
            logger.warning(f'[{self.name}] Failed to write execution-step report artifact: {exc}')

    def _resolve_script_ref_for_reporting(self) -> str:
        """Return script/command reference for reporting classification."""
        step_type = str(self.type or '').strip().lower()
        if step_type == 'custom_script':
            return str(
                self.config.get('path')
                or self.config.get('script')
                or self.config.get('script_path')
                or ''
            ).strip()

        if step_type == 'shell_run_command':
            command = str(self.config.get('cmd', self.config.get('command', '')) or '').strip()
            if command:
                return command.split()[0].strip('"\'')

        return ''

    def _process_timer_action(self, timer_conf: Dict[str, Any]) -> None:
        """Process a generic timer action (start/stop/checkpoint).

        Parameters
        ----------
        timer_conf : dict
            Must contain ``id`` and ``action``.
            Actions: ``start``, ``stop``, ``checkpoint``.
            For ``start``: optional ``threshold_test`` block (validated via
                :class:`TimerThresholdTestConfig`).
            For ``stop``: generates JUnit pass/fail if the timer has a
                threshold_test config.
            For ``checkpoint``: optional ``checkpoint_id``, ``threshold``.
            ``when``: ``before`` or ``after`` (default: ``after``).
        """
        from xc_ce_utils.rb_timer.rb_timer import RBTimer

        timer_id = timer_conf.get('id')
        action = timer_conf.get('action', '').lower()

        if not timer_id or not action:
            logger.warning(f"[{self.name}] timer config requires 'id' and 'action' keys")
            return

        if 'timers' not in self.resources:
            self.resources['timers'] = {}

        if action == 'start':
            # Parse threshold_test block if present
            raw_threshold_test = timer_conf.get('threshold_test')
            threshold_test: Optional[TimerThresholdTestConfig] = None
            threshold = -1
            if raw_threshold_test:
                try:
                    threshold_test = TimerThresholdTestConfig(**raw_threshold_test)
                    threshold = threshold_test.time
                except Exception as e:
                    raise RuntimeConfigError(
                        f"[{self.name}] Invalid threshold_test config on timer '{timer_id}'  {e}"
                    )

            timer = RBTimer(timer_id, threshold)
            # Store report folder so stop action can write JUnit there
            timer._report_folder = str(self.reports_folder)
            timer._started_by_step = self.name
            # Store the validated threshold test config for use at stop time
            timer._threshold_test = threshold_test
            self.resources['timers'][timer_id] = timer
            logger.info(
                f"[{self.name}] Timer '{timer_id}' started"
                + (f' (threshold={threshold}s)' if threshold != -1 else '')
            )

        elif action == 'stop':
            timer = self.resources['timers'].get(timer_id)
            if timer is None:
                logger.warning(
                    f"[{self.name}] Timer '{timer_id}' not found  "
                    f'cannot stop (was timer_start executed?)'
                )
                return
            timer.stop()
            elapsed = timer.get_elapsed_time_string()
            logger.info(f"[{self.name}] Timer '{timer_id}' stopped " f'(elapsed={elapsed})')

            # Generate JUnit verdict if threshold_test was configured
            if timer.threshold != -1:
                self._generate_timer_junit_report(timer, timer_id)

        elif action == 'checkpoint':
            timer = self.resources['timers'].get(timer_id)
            if timer is None:
                logger.warning(
                    f"[{self.name}] Timer '{timer_id}' not found  " f'cannot add checkpoint'
                )
                return
            checkpoint_id = timer_conf.get('checkpoint_id', self.name)
            threshold = timer_conf.get('threshold', -1)
            timer.add_checkpoint(checkpoint_id, threshold)
            logger.info(
                f"[{self.name}] Checkpoint '{checkpoint_id}' added to " f"timer '{timer_id}'"
            )

        else:
            logger.warning(
                f"[{self.name}] Unknown timer action '{action}'. "
                f'Valid actions: start, stop, checkpoint'
            )

    def _generate_timer_junit_report(self, timer: Any, timer_id: str) -> None:
        """Generate a JUnit XML report for a timer with a threshold.

        Writes a pass/fail test result based on whether the timer's
        threshold was exceeded.  When a ``threshold_test`` config was
        provided at start time, the report is enriched with ASPICE
        traceability fields (test_spec_id, test_level, expected_result).
        """
        from xc_ce_utils.core_engine.reporting.adapters.exporters import (  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415
            TestResult,
            generate_junit_xml,
        )

        elapsed_s = timer.get_elapsed_time(unit='s')
        threshold_s = timer.threshold
        exceeded = timer.threshold_exceeded
        threshold_test: Optional[TimerThresholdTestConfig] = getattr(timer, '_threshold_test', None)

        status = 'failed' if exceeded else 'passed'
        message = f"Timer '{timer_id}' elapsed {elapsed_s}s " f'(threshold: {threshold_s}s)  ' + (
            'EXCEEDED' if exceeded else 'OK'
        )

        # Build description and properties from threshold_test config
        description = ''
        tc_properties: Dict[str, str] = {}
        if threshold_test:
            tc_properties = {
                'test_spec_id': threshold_test.test_spec.id,
                'test_spec_type': threshold_test.test_spec.type,
            }

        result = TestResult(
            name=f'timer_{timer_id}',
            status=status,
            duration=elapsed_s,
            message=message if exceeded else '',
            output=message,
            description=description,
            properties=tc_properties,
        )

        # Use the report folder stored at start time
        report_dir = getattr(timer, '_report_folder', str(self.reports_folder))
        output_path = os.path.join(report_dir, f'timer_{timer_id}.xml')

        # Use suite_name from threshold_test config if provided
        suite_name = (
            (threshold_test.suite or threshold_test.test_spec.id)
            if threshold_test
            else f'timer_{timer_id}'
        )

        os.makedirs(report_dir, exist_ok=True)
        report_path = generate_junit_xml(
            [result],
            suite_name=suite_name,
            output_path=output_path,
            properties={
                'timer_id': timer_id,
                'threshold_s': str(threshold_s),
                'elapsed_s': str(elapsed_s),
                'started_by': getattr(timer, '_started_by_step', 'unknown'),
                'stopped_by': self.name,
            },
        )

        if exceeded:
            logger.warning(
                f"[{self.name}] Timer '{timer_id}' FAILED  "
                f'{elapsed_s}s > {threshold_s}s threshold. '
                f'Report: {report_path}'
            )
        else:
            logger.success(
                f"[{self.name}] Timer '{timer_id}' PASSED  "
                f'{elapsed_s}s <= {threshold_s}s threshold. '
                f'Report: {report_path}'
            )

    # ------------------------------------------------------------------
    # Folder helpers
    # ------------------------------------------------------------------

    def get_step_build_folder(self) -> Path:
        """Get/create step-specific build folder."""
        if self.build_folder is not None:
            return self.build_folder

        logger.trace(f'[{self.name}] Resolving build folder')
        step_build_folder = self.context.build_folder / self.name
        step_build_folder.mkdir(parents=True, exist_ok=True)
        self.build_folder = step_build_folder
        logger.trace(f'[{self.name}] Build folder resolved: {self.build_folder}')
        return self.build_folder

    def get_step_log_folder(self) -> Path:
        """Get/create step-specific log folder."""
        if self.log_folder is not None:
            return self.log_folder

        step_log_folder = self.context.logs_folder / self.name
        step_log_folder.mkdir(parents=True, exist_ok=True)
        self.log_folder = step_log_folder
        return self.log_folder

    def get_step_reports_folder(self) -> Path:
        """Get/create step-specific reports folder."""
        if self.reports_folder is not None:
            return self.reports_folder

        # step_reports_folder.mkdir(parents=True, exist_ok=True) --> to be created by steps that need it,
        # since not all steps produce reports and we want to avoid empty folders
        self.reports_folder = self.context.reports_folder / self.name
        return self.reports_folder

    def get_step_deploy_folder(self) -> Path:
        """Get/create step-specific deploy folder."""
        if self.deploy_folder is not None:
            return self.deploy_folder

        # step_deploy_folder.mkdir(parents=True, exist_ok=True) --> to be created by steps that need it,
        # since not all steps produce deployables and we want to avoid empty folders
        self.deploy_folder = self.context.deploy_folder / self.name
        return self.deploy_folder

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def abort(self, exception, abort_execution=False):
        """Handle step failure  raise AbortError or ContinueWithErrorsError.

        Args:
            exception: The original exception.
            abort_execution: If True, always abort regardless of game_stopper.
        """
        if self.step_timer is not None:
            self.step_timer.stop()

        if self.game_stopper or abort_execution:
            logger.critical(str(exception))
            raise mark_reported(AbortError(str(exception), phase=self.name))
        else:
            logger.error(str(exception))
            logger.warning(f'[{self.name}] Step ended with errors (non-game-stopper)')
            raise mark_reported(ContinueWithErrorsError(str(exception), phase=self.name))

    # ------------------------------------------------------------------
    # Output checking (test evaluation)
    # ------------------------------------------------------------------

    def check_output(self, content: str, texts: List[str], order_relevant: bool = False):
        """Check if expected texts appear in content.

        Sets test_status to PASSED or FAILED accordingly.

        Args:
            content: The output content to search in.
            texts: List of expected strings.
            order_relevant: If True, texts must appear in the given order.
        """
        failed = False

        if order_relevant:
            current_index = 0
            for text in texts:
                current_index = content.find(text, current_index)
                if current_index == -1:
                    if text in content:
                        msg = f"String not found in order: '{text}'"
                    else:
                        msg = f"String not found: '{text}'"
                    logger.error(f'[{self.name}] {msg}')
                    self.result_string.append(msg)
                    failed = True
                else:
                    logger.info(f"[{self.name}] String '{text}' found")
                current_index += len(text)
        else:
            for text in texts:
                if text not in content:
                    msg = f"String not found: '{text}'"
                    logger.error(f'[{self.name}] {msg}')
                    self.result_string.append(msg)
                    failed = True
                else:
                    logger.info(f"[{self.name}] String '{text}' found")

        if failed:
            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            self.test_status = StepEvaluationStatus.FAILED
        else:
            self.test_status = StepEvaluationStatus.PASSED
            self.result_string.append('All expected strings found.')
            logger.success(f'[{self.name}] All expected strings found')

    # ------------------------------------------------------------------
    # Metadata properties
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Test result reporting
    # ------------------------------------------------------------------

    def report_results(
        self,
        suite_name: str,
        report_dir: Optional[str] = None,
        report_filename: Optional[str] = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Generate a JUnit XML report from ``self.test_results``.

        When a step-level ``test:`` config block is present (validated by
        :class:`StepTestConfig`), its metadata is merged into each
        :class:`TestResult`:

        - ``test_spec.id`` is stored as each result's ``test_spec_id`` property
        - ``test_spec.type`` is stored as each result's ``test_spec_type`` property
        - ``suite`` (or ``test_spec.id``) overrides the *suite_name* argument

        Parameters
        ----------
        suite_name : str
            Name for the ``<testsuite>`` element.
        report_dir : str, optional
            Directory for the XML file.  Defaults to ``self.reports_folder``.
        report_filename : str, optional
            Filename for the XML file.  Defaults to ``<step_name>.xml``.
        properties : dict, optional
            Extra key-value pairs added as suite-level ``<property>`` elements.

        Returns
        -------
        str or None
            Absolute path to the written XML file, or *None* when there
            are no results.
        """
        from xc_ce_utils.core_engine.reporting.adapters.exporters import (  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415  # noqa: PLC0415
            generate_junit_xml,
        )

        if not self.test_results:
            logger.warning(f'[{self.name}] No test results to report')
            return None

        # --- Enrich results from step-level test: config ---
        if self.test_config:
            suite_name = self.test_config.suite or self.test_config.test_spec.id

            for result in self.test_results:
                result.properties.setdefault('test_spec_id', self.test_config.test_spec.id)
                result.properties.setdefault('test_spec_type', self.test_config.test_spec.type)

        out_dir = report_dir or str(self.reports_folder)
        filename = report_filename or f'{self.name}.xml'
        output_path = os.path.join(out_dir, filename)

        report_path = generate_junit_xml(
            self.test_results,
            suite_name=suite_name,
            output_path=output_path,
            properties=properties,
        )

        # Derive status from results
        failures = sum(1 for r in self.test_results if r.status in ('failed', 'error'))

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        if failures > 0:
            self.test_status = StepEvaluationStatus.FAILED
        else:
            self.test_status = StepEvaluationStatus.PASSED

        self.result_string.append(f'JUnit report: {report_path}')
        return report_path

    @property
    def category(self) -> str:
        """Category for this step  from user override or registry auto-mapping."""
        from xc_ce_utils.core_engine.domain.step_registry import StepRegistry

        override = self.config.get('category')
        if override:
            return override
        step_type = self.type
        if step_type and StepRegistry.is_registered(step_type):
            return StepRegistry.get_category(step_type)
        return 'Uncategorized'


# ---------------------------------------------------------------------------
# WrappedStep  ExecutionStep with WrapperRegistry-backed wrapper access
# ---------------------------------------------------------------------------


class WrappedStep(ExecutionStep):
    """Execution step that resolves build-tool wrappers via WrapperRegistry.

    Subclasses set ``WRAPPER_NAME`` and call ``self.get_wrapper()`` inside
    ``execute()`` instead of importing the wrapper module directly. Tests can
    swap a wrapper implementation by calling ``WrapperRegistry.register(name,
    Fake)`` without touching the step's import graph. Unhandled exceptions
    are converted to ``ExecutionStepError`` by the execution-engine recovery
    wiring (default strategy = ABORT), so the ``try/except ImportError /
    except Exception`` boilerplate is no longer required in migrated steps.

    Step-specific orchestration (cache cleanup, definitions generation,
    preset/argument branching, dev-mode post-processing, ...) remains in
    each subclass's ``execute()``; this base deliberately does not impose a
    fully declarative execute().
    """

    # Override in subclasses (registry key, e.g. "cmake").
    WRAPPER_NAME: Optional[str] = None

    def get_wrapper(self, name: Optional[str] = None):
        """Resolve a wrapper class from :class:`WrapperRegistry`."""
        key = name or self.WRAPPER_NAME
        if not key:
            raise RuntimeConfigError(
                f'[{self.name}] WrappedStep requires WRAPPER_NAME or an explicit name argument'
            )
        from xc_ce_utils.core_engine.domain.wrapper_registry import (
            WrapperRegistry,
        )

        return WrapperRegistry.get(key)
