"""Variable management steps.
"""

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
    StepConfStatus,
    StepExecutionStatus,
)


class VariableAddStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('variable_add')
class VariableAddStep(ExecutionStep):
    params_model = VariableAddStepParams

    """Add one or more variables to the global variables dict.

    Each key-value pair in ``parameters.variables`` is inserted into
    ``self.global_variables`` unconditionally (creates or overwrites).

    Config parameters:
        variables (dict): Mapping of variable names to their values.
    """

    def execute(self) -> None:
        """Execute the variable_add step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})
            variables = parameters.get('variables', {})

            variable_name = None
            variable_value = None

            for variable_name, variable_value in variables.items():
                self.global_variables[variable_name] = variable_value

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(
                f"[{self.name}] Variable '{variable_name}' added " f'with value: {variable_value}'
            )

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Adding variable failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )


class VariableSetStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('variable_set')
class VariableSetStep(ExecutionStep):
    params_model = VariableSetStepParams

    """Set (update) one or more existing global variables.

    Unlike ``variable_add``, this step requires that each variable already
    exists in ``self.global_variables``.  A ``ExecutionStepError`` is raised if a
    variable is not found.

    Config parameters:
        variables (dict): Mapping of variable names to their new values.
    """

    def execute(self) -> None:
        """Execute the variable_set step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})
            variables = parameters.get('variables', {})

            variable_name = None
            variable_value = None

            for variable_name, variable_value in variables.items():
                if variable_name not in self.global_variables:
                    message = (
                        f"[{self.name}] Variable '{variable_name}' "
                        f'not found in global variables'
                    )
                    raise ExecutionStepError(message, phase=self.name)

                self.global_variables[variable_name] = variable_value

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(
                f"[{self.name}] Variable '{variable_name}' set " f'with value: {variable_value}'
            )

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Setting variable failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )
