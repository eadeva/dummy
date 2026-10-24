"""Shell execution and script runner steps.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ConfigurationError,
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepConfStatus,
    StepEvaluationStatus,
    StepExecutionStatus,
    WrappedStep,
)
from xc_ce_utils.global_modules.aux_helper import run_command


class ShellRunCommandStepParams(BaseStepParams):
    check_output: Optional[Any] = Field(default=None)
    cmd: Optional[Any] = Field(default=None)
    command: Optional[Any] = Field(default=None)
    working_dir: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('shell_run_command')
class ShellRunCommandStep(ExecutionStep):
    params_model = ShellRunCommandStepParams

    """Run a shell command.

    Executes an arbitrary shell command via ``subprocess.run``, optionally
    changing the working directory beforehand and verifying expected strings
    in the command output afterwards.

    Config parameters:
        cmd (str):              The shell command to execute (alias: ``command``).
        working_dir (str):      Optional working directory for the command.
        check_output (dict):    Optional output verification with keys
                                ``expected_strs`` (list[str]) and
                                ``order_relevant`` (bool).
    """

    def execute(self) -> None:
        """Execute the shell_run_command step."""
        try:
            self.pre_processing()
            cmd = self.config.get('cmd', self.config.get('command', ''))

            logger.info(f'[{self.name}] Running command: {cmd}')

            working_dir = self.config.get('working_dir', None)
            if working_dir and not Path(working_dir).exists():
                message = f'[{self.name}] Specified working dir: ' f"'{working_dir}' doesn't exist"
                raise ExecutionStepError(message, phase=self.name)

            needs_capture = 'check_output' in self.config
            output = run_command(
                cmd,
                cwd=working_dir,
                capture_output=needs_capture,
            )

            if needs_capture:
                order_relevant = self.config['check_output'].get('order_relevant', False)
                self.check_output(
                    output,
                    self.config['check_output']['expected_strs'],
                    order_relevant,
                )
            else:
                self.test_status = StepEvaluationStatus.PASSED

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(f"[{self.name}] Command '{cmd}' executed successfully")

        except subprocess.CalledProcessError as e:
            message = f"[{self.name}] Command '{cmd}' failed with return code {e.returncode}"
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
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
            message = f'[{self.name}] Command execution failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )


class CustomScriptStepParams(BaseStepParams):
    path: Optional[Any] = Field(default=None)
    return_success_codes: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('custom_script')
class CustomScriptStep(WrappedStep):
    params_model = CustomScriptStepParams

    """Run an external script (.py, .ps1, .sh).

    Delegates to :class:`~xc_ce_utils.core_engine.wrappers.rb_script_runner.RBScriptRunner`
    which detects the script type and builds the appropriate command.
    When running as a frozen executable, Python scripts are executed
    in-process via ``runpy``.

    File logging is handled by the ``run()`` lifecycle (``file_scope``);
    subprocess output is captured by ``run_command`` into the step log
    folder when logging is enabled.

    Config parameters:
        path (str):                     Path to the script to execute.
        params (dict | list):           Optional arguments passed to the script.
        return_success_codes (list):    Acceptable return codes (default ``[0]``).
    """

    WRAPPER_NAME = 'script'

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate custom script configuration."""
        if 'path' not in self.config:
            raise ConfigurationError("Custom script step requires 'path' configuration")

        if 'params' in self.config and not isinstance(self.config.get('params'), (dict, list)):
            raise ConfigurationError("Custom script step 'params' must be a dict or list")

        script_path = Path(self.config['path'])
        if not script_path.exists():
            raise ConfigurationError(f'Script path does not exist: {script_path}')

    def execute(self) -> None:
        """Execute custom script."""
        RBScriptRunner = self.get_wrapper()

        script_runner = RBScriptRunner()

        acceptable_return_codes = self.config.get('return_success_codes', [0])
        script_runner.run_script(
            self.config['path'],
            acceptable_return_codes,
            self.config.get('params', {}),
        )
