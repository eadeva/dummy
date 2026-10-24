"""Toolbase installation step.
"""

import os
from pathlib import Path

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
    StepExecutionStatus,
)


class ToolbaseStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('tb_installation')
class ToolbaseStep(ExecutionStep):
    params_model = ToolbaseStepParams

    """Toolbase tool installation step."""

    def __init__(self, name, config, context):
        super().__init__(name, config, context)

    def execute(self):
        try:
            self.pre_processing()
            action = self.config.get('step_type', '')

            if action == 'tb_installation':
                self._tb_installation()
            else:
                raise RuntimeConfigError(f'[{self.name}] Unknown action: {action}')

        except (ExecutionStepError, AbortError, RuntimeConfigError):
            raise
        except KeyboardInterrupt:
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(
                AbortError(f'[{self.name}] Interrupted by user'),
                abort_execution=True,
            )
        except Exception as e:
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(e, abort_execution=self.game_stopper)

    def _tb_installation(self):
        from xc_ce_utils.tool_installers.toolbase_installer import (
            add_tool_for_installation,
            run_toolbase_update,
        )

        params = self.config.get('params', {})
        log_prefix = f'[{self.name}]'

        try:
            logger.info(f'{log_prefix} Toolbase installation')
            toolbase_environment = params['env']
            run_tb_update = False
            installed_tools = []

            for tool_name, tool_param in params['tools'].items():
                try:
                    if add_tool_for_installation(
                        toolbase_environment, tool_name, tool_param['version']
                    ):
                        logger.debug(
                            f"{log_prefix} {tool_name}/{tool_param['version']} "
                            "missing - Adding to tool installation"
                        )
                        installed_tools.append(f"{tool_name}/{tool_param['version']}")
                        run_tb_update = True

                    if 'subfolder' in tool_param['env_variable']:
                        tool_path = (
                            Path(os.environ['TB_HOMEDIR'])
                            / tool_name
                            / tool_param['version']
                            / tool_param['env_variable']['subfolder']
                        )
                    else:
                        tool_path = (
                            Path(os.environ['TB_HOMEDIR']) / tool_name / tool_param['version']
                        )

                    env_key = f"TB_{tool_param['env_variable']['name']}"
                    os.environ[env_key] = str(tool_path)
                    self.global_variables[env_key] = str(tool_path)

                except KeyError as e:
                    message = f'{log_prefix} Missing environment variable: {e}'
                    logger.error(message)
                    raise ExecutionStepError(message, phase=self.name)

                except Exception as e:
                    message = f'{log_prefix} Error processing tool {tool_name}: {e}'
                    logger.error(message)
                    raise ExecutionStepError(message, phase=self.name)

            if run_tb_update:
                try:
                    if run_toolbase_update() == 1:
                        message = f'{log_prefix} Failed to run TBUpdate'
                        self.result_string.append('Step failed running TBUpdate.')
                        logger.error(message)
                        raise ExecutionStepError(message, phase=self.name)
                except ExecutionStepError:
                    raise
                except Exception as e:
                    message = f'{log_prefix} Error running TBUpdate: {e}'
                    self.result_string.append('Step failed running TBUpdate.')
                    logger.error(message)
                    raise ExecutionStepError(message, phase=self.name)

            if installed_tools:
                self.result_string.append('Installed tools: ')
                for tool in installed_tools:
                    self.result_string.append(f'{tool}')
            else:
                self.result_string.append('All tools already installed.')

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(
                f'{log_prefix} Toolbase installation finished. '
                f'Installed tools: {installed_tools}'
            )

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f'{log_prefix} Toolbase installation failed: {e}'
            logger.critical(message)
            raise ExecutionStepError(message, phase=self.name)
