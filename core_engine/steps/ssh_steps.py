"""SSH connection and command execution steps.
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


class SSHStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('ssh_connection_setup', 'ssh_disconnect', 'ssh_run_cmd')
class SSHStep(ExecutionStep):
    params_model = SSHStepParams

    """Unified SSH step for connection management and remote command execution.

    Handles all SSH actions: establishing connections with retry logic,
    executing remote commands with optional output verification, and
    disconnecting / cleaning up sessions.

    The concrete action is determined by the ``step_type`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action -- see individual methods):
        SSH_IP_ADDRESS (str):   Target host IP address.
        USER_ID (str):          SSH username.
        USER_PWD (str):         SSH password (optional, default empty string).
        PORT (int):             SSH port (optional, default 22).
        retries (int):          Number of connection attempts (optional, default 6).
        cmd (str):              Remote command to execute (ssh_run_cmd).
        check_output (dict):    Optional output verification with keys
                                ``expected_strs`` (list[str]) and
                                ``order_relevant`` (bool).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured SSH action."""
        try:
            # Lazy import -- avoid pulling in paramiko at module load time
            import paramiko

            self.pre_processing()

            step_type = self.config.get('step_type', '')
            parameters = self.config.get('params', {})

            if step_type == 'ssh_connection_setup':
                self._ssh_connection_setup(parameters, paramiko)
            elif step_type == 'ssh_run_cmd':
                self._ssh_run_cmd(parameters, paramiko)
            elif step_type == 'ssh_disconnect':
                self._ssh_disconnect(parameters, paramiko)
            else:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"step_type '{step_type}' not recognized!"
                )
                logger.critical(message)
                raise AbortError(message, phase=self.name)

        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] SSH operation failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _ssh_connection_setup(self, parameters: Dict[str, Any], paramiko) -> None:
        """Establish an SSH connection with retry logic.

        Creates a ``paramiko.SSHClient`` and connects to the target host.
        If a connection to the same IP already exists in the shared resource
        pool, the step is skipped.  On success the connection is stored in
        ``self.resources["ssh_connections"]`` keyed by ``SSH_IP_ADDRESS``.
        """
        target_ip = parameters['SSH_IP_ADDRESS']

        if target_ip in self.resources['ssh_connections']:
            logger.warning(f'[{self.name}] SSH connection already established ' f'with {target_ip}')
            self.add_to_report = False
            return

        logger.info(f'[{self.name}] Establishing SSH connection')

        ssh_user_password = parameters.get('USER_PWD', '')
        ssh_port = parameters.get('PORT', 22)
        retries = parameters.get('retries', 6)

        connection_established = False
        for attempt in range(retries):
            try:
                if attempt > 0:
                    message = f'[{self.name}] SSH connection failed, ' f'retry number {attempt}...'
                    logger.warning(message)

                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(
                    target_ip,
                    ssh_port,
                    username=parameters['USER_ID'],
                    password=ssh_user_password,
                    timeout=15,
                )
                connection_established = True
                break
            except Exception:
                message = f'[{self.name}] SSH connection failed'
                logger.warning(message)

        if not connection_established:
            message = f'[{self.name}] SSH connection failed'
            raise ExecutionStepError(message, phase=self.name)

        self.resources['ssh_connections'][target_ip] = {
            'ssh_user': parameters['USER_ID'],
            'ssh_connection': ssh_client,
        }

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] SSH connection to {target_ip} established')

    def _ssh_run_cmd(self, parameters: Dict[str, Any], paramiko) -> None:
        """Execute a command on a remote host via an existing SSH connection.

        Reads both stdout and stderr.  If stderr contains output the step is
        marked as failed.  When ``check_output`` is provided in the
        parameters, the command output is verified against the expected
        strings using ``ExecutionStep.check_output()``.
        """
        exception_occurred = False
        message = ''

        try:
            target_ip = parameters['SSH_IP_ADDRESS']

            if target_ip not in self.resources['ssh_connections']:
                message = f'[{self.name}] SSH connection with ' f"{target_ip} doesn't exist"
                raise RuntimeConfigError(message, phase=self.name)

            ssh_connection = self.resources['ssh_connections'][target_ip]['ssh_connection']

            logger.info(f"[{self.name}] SSH command: {parameters['cmd']}")

            stdin, stdout, stderr = ssh_connection.exec_command(parameters['cmd'])

            error = stderr.read().decode()
            if error:
                message = f"[{self.name}] {parameters['cmd']} failed: {error}"
                self.log_content = error.split('\n')
                self.result_string = error.split('\n')
                exception_occurred = True
                self.test_status = StepEvaluationStatus.FAILED
            else:
                command_output = stdout.read().decode()
                self.log_content = command_output.split('\n')

                if 'check_output' in parameters:
                    order_relevant = parameters['check_output'].get('order_relevant', False)
                    self.check_output(
                        command_output,
                        parameters['check_output']['expected_strs'],
                        order_relevant,
                    )
                else:
                    self.result_string = command_output.split('\n')
                    self.test_status = StepEvaluationStatus.PASSED

        except paramiko.SSHException as e:
            message = f"[{self.name}] SSH command '{parameters['cmd']}' " f"execution failed: {e}"
            exception_occurred = True
        except RuntimeConfigError:
            raise
        except Exception as e:
            message = f'[{self.name}] SSH command execution failed: {e}'
            exception_occurred = True

        if exception_occurred:
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[{self.name}] SSH command executed successfully')

    def _ssh_disconnect(self, parameters: Dict[str, Any], paramiko) -> None:
        """Close an SSH connection and remove it from the shared resource pool.

        Raises ``RuntimeConfigError`` if no connection exists for the given
        IP address.  Handles various paramiko-specific exceptions during
        teardown.
        """
        exception_occurred = False
        message = ''

        try:
            target_ip = parameters['SSH_IP_ADDRESS']

            if target_ip not in self.resources['ssh_connections']:
                message = f'[{self.name}] SSH connection with ' f"{target_ip} doesn't exist"
                raise RuntimeConfigError(message, phase=self.name)

            ssh_client = self.resources['ssh_connections'][target_ip]['ssh_connection']
            ssh_client.close()
            self.resources['ssh_connections'].pop(target_ip, None)

        except RuntimeConfigError:
            raise
        except paramiko.AuthenticationException as e:
            message = (
                f'[{self.name}] SSH disconnection failed due to ' f'authentication error: {e!s}'
            )
            exception_occurred = True
        except paramiko.SSHException as e:
            message = f'[{self.name}] SSH disconnection failed due to ' f'SSH error: {e!s}'
            exception_occurred = True
        except Exception as e:
            message = f'[{self.name}] SSH disconnection failed: {e!s}'
            exception_occurred = True

        if exception_occurred:
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f"[{self.name}] SSH connection with '{target_ip}' disconnected")
