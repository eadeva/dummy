"""Timer and wait/idle steps.
"""

import time
from typing import Any, Dict

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepEvaluationStatus,
    StepExecutionStatus,
)


class TimerStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'timer_start',
    'timer_stop',
    'timer_checkpoint',
    'wait_idle',
)
class TimerStep(ExecutionStep):
    params_model = TimerStepParams

    """Unified timer and wait step.

    Handles all timer-related actions: start, stop, checkpoint, and
    wait_idle. The concrete action is determined by the ``step_type``
    field in the step configuration and dispatched internally.

    Config parameters (vary per action):
        id (str):               Identifier for the timer in the shared resource pool.
        threshold (float):      Time threshold for the timer (timer_start).
        checkpoint_id (str):    Identifier for a checkpoint (timer_checkpoint).
        wait_time (float):      Duration in seconds to wait (wait_idle).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured timer action."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'timer_start':
                self._timer_start(params)
            elif step_type == 'timer_stop':
                self._timer_stop(params)
            elif step_type == 'timer_checkpoint':
                self._timer_checkpoint(params)
            elif step_type == 'wait_idle':
                self._wait_idle(params)
            else:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"step_type '{step_type}' not recognized!"
                )
                logger.critical(message)
                raise AbortError(message, phase=self.name)

        except RuntimeConfigError as e:
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Unknown exception: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _timer_start(self, params: Dict[str, Any]) -> None:
        """Start a new timer.

        Creates a new ``RBTimer`` instance and stores it in
        ``self.resources["timers"]`` keyed by the configured ``id``.
        """
        from xc_ce_utils.rb_timer.rb_timer import RBTimer

        try:
            timer_id = params['id']
            threshold = params.get('threshold')

            if 'timers' not in self.resources:
                self.resources['timers'] = {}

            logger.info(
                f"[{self.name}] Starting timer '{timer_id}'"
                + (f' with threshold {threshold}s' if threshold is not None else '')
            )

            timer = RBTimer(timer_id, threshold)
            self.resources['timers'][timer_id] = timer

            self.result_string.append(f"Timer '{timer_id}' started successfully")

        except Exception as e:
            message = f"Timer '{params.get('id', 'unknown')}' start failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Timer '{timer_id}' started")

    def _timer_stop(self, params: Dict[str, Any]) -> None:
        """Stop a running timer."""
        try:
            timer_id = params['id']
            timer = self.resources['timers'][timer_id]

            logger.info(f"[{self.name}] Stopping timer '{timer_id}'")

            timer.stop()

            self.result_string.append(f"Timer '{timer_id}' stopped successfully")

        except KeyError:
            message = (
                f"Timer '{params.get('id', 'unknown')}' not found in resources. "
                f"Was timer_start executed?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = f"Timer '{params.get('id', 'unknown')}' stop failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Timer '{timer_id}' stopped")

    def _timer_checkpoint(self, params: Dict[str, Any]) -> None:
        """Add a checkpoint to a running timer."""
        try:
            timer_id = params['id']
            checkpoint_id = params['checkpoint_id']
            timer = self.resources['timers'][timer_id]

            logger.info(
                f"[{self.name}] Adding checkpoint '{checkpoint_id}' " f"to timer '{timer_id}'"
            )

            timer.add_checkpoint(checkpoint_id)

            self.result_string.append(f"Checkpoint '{checkpoint_id}' added to timer '{timer_id}'")

        except KeyError:
            message = (
                f"Timer '{params.get('id', 'unknown')}' not found in resources. "
                f"Was timer_start executed?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = (
                f"Timer '{params.get('id', 'unknown')}' checkpoint "
                f"'{params.get('checkpoint_id', 'unknown')}' failed: {e!s}"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Checkpoint '{checkpoint_id}' added to timer '{timer_id}'")

    def _wait_idle(self, params: Dict[str, Any]) -> None:
        """Wait for a specified duration.

        Sleeps for ``wait_time`` seconds.
        """
        try:
            wait_time = params['wait_time']

            logger.info(f'[{self.name}] Waiting idle for {wait_time}s')

            time.sleep(wait_time)

            self.result_string.append(f'Wait idle completed ({wait_time}s)')

        except KeyboardInterrupt:
            raise
        except Exception as e:
            message = f'Wait idle failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Wait idle completed ({wait_time}s)')
