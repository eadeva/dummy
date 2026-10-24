"""Error recovery strategy dispatch for execution steps.

Extracted from the former ``ExecutionAction`` god-class. These functions are
pure with respect to the execution engine's mutable state — they operate on
the failing step/error only and are consulted by
:class:`~xc_ce_utils.core_engine.application.orchestration.step_executor.StepExecutor`.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    ErrorRecoveryStrategy,
    ExecutionStepError,
    is_reported,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.steps.base import ExecutionNode


def get_recovery_strategy(step: 'ExecutionNode') -> ErrorRecoveryStrategy:
    """Resolve the recovery strategy for a step.

    Falls back to ABORT when the step type is unknown to the registry
    (e.g. composite ``ExecutionSet`` nodes or steps registered without an
    explicit ``recovery=`` kwarg).
    """
    step_type = getattr(step, 'type', None)
    if not step_type or not StepRegistry.is_registered(step_type):
        return ErrorRecoveryStrategy.ABORT
    return StepRegistry.get_recovery(step_type)


def log_step_failure(
    step: 'ExecutionNode',
    error: Exception,
    strategy: ErrorRecoveryStrategy,
) -> None:
    """Emit a detailed debug log for an initial step failure."""
    logger.debug(
        f"Phase '{step.name}' failed with {type(error).__name__}: {error} "
        f'(recovery={strategy.value})\n{traceback.format_exc()}'
    )


def retry_step_once(step: 'ExecutionNode', error: Exception) -> None:
    """Retry a failed step once, then fail hard if retry also fails."""
    detail = '' if is_reported(error) else f': {error}'
    logger.warning(f"Phase '{step.name}' failed, retrying once{detail}")
    try:
        step.run()
        return
    except Exception as retry_error:
        logger.debug(
            f"Phase '{step.name}' retry failed with "
            f'{type(retry_error).__name__}: {retry_error}\n'
            f'{traceback.format_exc()}'
        )
        msg = f"Phase '{step.name}' failed after retry: {retry_error}"
        raise ExecutionStepError(msg, phase=step.name) from retry_error


def raise_phase_failure(step: 'ExecutionNode', error: Exception) -> None:
    """Raise a normalized phase failure exception."""
    msg = f"Phase '{step.name}' failed: {error}"
    raise ExecutionStepError(msg, phase=step.name) from error
