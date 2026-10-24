"""Thread management steps.
"""

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


class ThreadStopStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('thread_stop')
class ThreadStopStep(ExecutionStep):
    params_model = ThreadStopStepParams

    """Thread stop step.

    Stops a running thread from the shared resource pool by setting its
    stop signal and joining with a timeout.

    Config parameters:
        id (str):   Identifier of the thread in the shared resource pool.
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the thread_stop action."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'thread_stop':
                self._thread_stop(params)
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
    # Action implementation
    # ------------------------------------------------------------------

    def _thread_stop(self, params: Dict[str, Any]) -> None:
        """Stop a thread managed via the resource pool.

        Retrieves the thread from ``self.resources["threads"]`` by its ``id``,
        sets the stop signal, and joins with a 5-second timeout. Raises a
        ``ExecutionStepError`` if the thread does not stop within the timeout.
        """
        try:
            thread_id = params['id']
            thread = self.resources['threads'][thread_id]

            logger.info(f"[{self.name}] Stopping thread '{thread_id}'")

            thread.stop_signal.set()
            thread.join(timeout=5)

            if thread.is_alive():
                message = f"Thread '{thread_id}' did not stop within 5s timeout"
                self.result_string.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self.result_string.append(f"Thread '{thread_id}' stopped successfully")

        except ExecutionStepError:
            raise
        except KeyError:
            message = (
                f"Thread '{params.get('id', 'unknown')}' not found in resources. "
                f"Was the thread started?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = f"Thread '{params.get('id', 'unknown')}' stop failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Thread '{thread_id}' stopped")
