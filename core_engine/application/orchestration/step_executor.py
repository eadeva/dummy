"""Step and execution-set creation/execution for the execution orchestrator.

Extracted from the former ``ExecutionAction`` god-class (``execution_engine.py``).
"""

from __future__ import annotations

import traceback
from importlib import import_module
from typing import TYPE_CHECKING, Any, Dict, Optional

# Triggers @StepRegistry.register() decorators for all concrete step classes.
import xc_ce_utils.core_engine.steps  # noqa: F401
from xc_ce_utils import logger
from xc_ce_utils.core_engine.application.orchestration import error_recovery
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ConfigurationError,
    ContinueWithErrorsError,
    ErrorRecoveryStrategy,
    is_reported,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.execution_set import ExecutionSet

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )
    from xc_ce_utils.core_engine.steps.base import ExecutionNode


def _get_config_loader_cls() -> type:
    module = import_module('xc_ce_utils.conf_file_loader.conf_file_loader')
    return module.ConfigLoader


class StepExecutor:
    """Creates and executes steps/execution-sets for a single action run.

    Owns the shared mutable ``resources``/``global_variables`` state injected
    into every created step, and dispatches step failures to the appropriate
    :class:`~xc_ce_utils.core_engine.domain.exceptions.ErrorRecoveryStrategy`.
    """

    def __init__(
        self,
        config: 'ActionConfiguration',
        resources: Dict[str, Any],
        global_variables: Dict[str, Any],
    ) -> None:
        self.config = config
        self.resources = resources
        self.global_variables = global_variables

    def execution_set_shared_state(self) -> ExecutionSet.SharedState:
        """Build shared mutable state passed to ExecutionSet nodes."""
        return ExecutionSet.SharedState(
            resources=self.resources,
            global_variables=self.global_variables,
        )

    def create_execution_set(
        self,
        set_name: str,
        set_conf: Dict[str, Any],
    ) -> ExecutionSet:
        """Create an ExecutionSet node with injected shared state."""
        return ExecutionSet(
            name=set_name,
            config=set_conf,
            context=self.config,
            step_factory=self.create_step,
            shared_state=self.execution_set_shared_state(),
        )

    def create_step(
        self, phase_name: str, phase_config: Dict[str, Any]
    ) -> Optional['ExecutionNode']:
        """Create a node from phase/step configuration.

        If the config has a ``steps`` key, creates an ``ExecutionSet`` (composite).
        Otherwise creates a leaf ``ExecutionStep`` via StepRegistry.

        Injects shared resources and global_variables into the config
        so that nodes can access them.
        """
        phase_config = self._resolve_phase_config(phase_name, phase_config)
        self._inject_step_shared_state(phase_config)

        if 'steps' in phase_config:
            return self.create_execution_set(phase_name, phase_config)

        phase_type = self._resolve_phase_type(phase_name, phase_config)
        if phase_type == 'test_report_collect':
            logger.info(
                f"Phase '{phase_name}' uses 'test_report_collect' and is skipped; "
                'unified reporting now runs automatically at action end'
            )
            return None

        step_class = StepRegistry.get(phase_type)
        return step_class(phase_name, phase_config, self.config)

    def _resolve_phase_config(
        self,
        phase_name: str,
        phase_config: Any,
    ) -> Dict[str, Any]:
        """Resolve lazy-included phase config into a mapping."""
        if not isinstance(phase_config, str):
            return phase_config

        # Lazy-load: phase config given as a string is a deferred file include
        # left in place by the loader (see ConfigLoader.LAZY_INCLUDE_BOUNDARY_KEYS).
        # The file is opened only when the step is actually constructed so
        # machine-/variant-dependent includes fail only for the active action.
        config_loader_cls = _get_config_loader_cls()
        lazy_loader = config_loader_cls(global_variables=self.global_variables)
        try:
            loaded_config = lazy_loader.load_file(
                phase_config,
                allow_missing_env_vars=False,
            )
        except FileNotFoundError as error:
            msg = (
                f"Phase '{phase_name}' references a configuration file that is "
                f'not available on this machine: {error}'
            )
            raise ConfigurationError(msg) from error

        if not isinstance(loaded_config, dict):
            msg = (
                f"Phase '{phase_name}': lazy-loaded config must be a mapping, "
                f'got {type(loaded_config).__name__}'
            )
            raise ConfigurationError(msg)

        return loaded_config

    def _inject_step_shared_state(self, phase_config: Dict[str, Any]) -> None:
        """Inject resources and globals into a phase config mapping."""
        phase_config.setdefault('_resources', self.resources)
        phase_config.setdefault('_global_variables', self.global_variables)

    @staticmethod
    def _resolve_phase_type(
        phase_name: str,
        phase_config: Dict[str, Any],
    ) -> str:
        """Resolve configured step type for a leaf phase."""
        phase_type = phase_config.get('type') or phase_config.get('step_type')
        if phase_type:
            return str(phase_type)

        msg = f"Phase '{phase_name}' missing 'type' (or 'step_type')"
        raise ConfigurationError(msg)

    def execute(self, step: 'ExecutionNode') -> bool:
        """Execute a single node with error handling.

        Returns:
            ``True`` when the failure should be recorded as a non-fatal
            ``errors`` flag by the caller (game_stopper=False style
            outcomes); ``False`` when the step succeeded or the failure was
            silently skipped per the registry-declared recovery strategy.
            Abort-worthy failures propagate as
            :class:`~xc_ce_utils.core_engine.domain.exceptions.ExecutionStepError`.

        Recovery routing:
        - Legacy ``AbortError`` from the step (``game_stopper=True`` path) is
          always treated as ABORT and re-raised as ``ExecutionStepError``.
        - Legacy ``ContinueWithErrorsError`` (``game_stopper=False`` path) is
          logged and reported back to the caller without aborting.
        - For other exceptions, the registry-declared
          :class:`ErrorRecoveryStrategy` for the step type is consulted:

          * ``ABORT`` (default) — re-raise as ``ExecutionStepError``.
          * ``CONTINUE_WITH_ERRORS`` — log and report back, do not raise.
          * ``RETRY_ONCE`` — run the step a second time; if it fails again,
            fall back to ABORT.
          * ``SKIP`` — log at debug level and swallow the exception.
        """
        try:
            step.run()
            return False
        except AbortError as error:
            logger.debug(f"Phase '{step.name}' aborted: {error}\n{traceback.format_exc()}")
            error_recovery.raise_phase_failure(step, error)
            return False  # unreachable — raise_phase_failure always raises
        except ContinueWithErrorsError as error:
            if is_reported(error):
                logger.debug(f"Phase '{step.name}' completed with errors: {error}")
            else:
                logger.warning(f"Phase '{step.name}' completed with errors: {error}")
            return True
        except Exception as error:
            return self._handle_step_failure(step, error)

    @staticmethod
    def _handle_step_failure(
        step: 'ExecutionNode',
        error: Exception,
    ) -> bool:
        """Route step failures according to the declared recovery strategy."""
        strategy = error_recovery.get_recovery_strategy(step)
        error_recovery.log_step_failure(step, error, strategy)

        if strategy is ErrorRecoveryStrategy.SKIP:
            logger.debug(f"Phase '{step.name}' failure skipped per registry strategy")
            return False

        if strategy is ErrorRecoveryStrategy.CONTINUE_WITH_ERRORS:
            detail = '' if is_reported(error) else f': {error}'
            logger.warning(
                f"Phase '{step.name}' failed but continuing per registry strategy{detail}"
            )
            return True

        if strategy is ErrorRecoveryStrategy.RETRY_ONCE:
            error_recovery.retry_step_once(step, error)
            return False

        # ABORT (default) — preserve historical behaviour
        error_recovery.raise_phase_failure(step, error)
        return False  # unreachable — raise_phase_failure always raises
