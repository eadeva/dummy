"""COM port steps."""

import queue
import time
from pathlib import Path
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
    StepConfStatus,
    StepEvaluationStatus,
    StepExecutionStatus,
)


class COMStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'com_init',
    'com_interrupt_boot',
    'com_read',
    'com_scan',
    'com_scan_queue',
    'com_send_cmd',
    'com_close',
)
class COMStep(ExecutionStep):
    params_model = COMStepParams

    """Unified COM port step.

    Handles all COM port actions: initialisation, boot interruption,
    reading, scanning (direct and queue-based), sending commands, and
    closing the port.

    The concrete action is determined by the ``step_type`` field in the
    step configuration and dispatched internally.

    Config parameters (vary per action -- see individual methods):
        port (str):             COM port identifier (all actions).
        cmd (str):              Command string to send (com_send_cmd,
                                com_interrupt_boot).
        expected_str (str):     String to detect during boot interruption
                                (com_interrupt_boot).
        timeout (int):          Timeout in seconds (com_interrupt_boot,
                                com_scan, com_scan_queue).
        expected_strs (dict):   Mapping of checkpoint names to search
                                configurations containing ``search_string``
                                and optional ``threshold`` (com_scan,
                                com_scan_queue).
        order_relevant (bool):  Whether the expected strings must appear
                                in order (com_scan, com_scan_queue).
                                Defaults to True.
        log_timings_in_ref_timer (str):
                                Optional reference timer name for adding
                                timing checkpoints (com_scan, com_scan_queue).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured COM port action."""
        # Lazy import -- avoid pulling in the serial module at load time
        from xc_ce_utils.com_io_handler.com_io_handler import (
            SerialPort,  # noqa: F401
        )

        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'com_init':
                self._com_init(params)
            elif step_type == 'com_interrupt_boot':
                self._com_interrupt_boot(params)
            elif step_type == 'com_read':
                self._com_read(params)
            elif step_type == 'com_scan':
                self._com_scan(params)
            elif step_type == 'com_scan_queue':
                self._com_scan_queue(params)
            elif step_type == 'com_send_cmd':
                self._com_send_cmd(params)
            elif step_type == 'com_close':
                self._com_close(params)
            else:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"step_type '{step_type}' not recognized!"
                )
                logger.critical(message)
                self.conf_status = StepConfStatus.CONFIGURE_FAILED
                raise RuntimeConfigError(message, phase=self.name)

        except (RuntimeConfigError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except ExecutionStepError:
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

    def _com_init(self, params: Dict[str, Any]) -> None:
        """Initialize the COM port.

        Creates a new ``SerialPort`` instance and stores it in the shared
        resource pool under ``self.resources["com_ports"]``.  If the port
        is already initialised the step is silently skipped.
        """
        from xc_ce_utils.com_io_handler.com_io_handler import SerialPort

        port = params['port']
        try:
            if port not in self.resources['com_ports']:
                com_port = SerialPort(port)
                self.resources['com_ports'][port] = com_port
            else:
                logger.warning(f'[{self.name}] COM{port} port already initialized')
                self.add_to_report = False
                return
        except Exception as e:
            message = f'[{self.name}] COM{port} port init failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[{self.name}] COM{port} port initialized')

    def _com_read(self, params: Dict[str, Any]) -> None:
        """Read from the COM port in a loop until stop_signal is set.

        Writes all received data to a log file and registers the log path
        in ``self.global_variables`` and ``self.resources["log_files"]``.
        """
        try:
            port_number = params['port']
            step_id = self.id

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            com_port = self.resources['com_ports'][port_number]
            stop_signal = self.resources['threads'][step_id]['stop_signal']

            log_dir = Path.cwd() / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = log_dir / f'{step_id}.log'
            log_id = f'{step_id}_log'.upper()
            self.global_variables[log_id] = log_file_path
            self.resources['log_files'][log_id] = str(log_file_path)

            logger.info(
                f'[{self.name}] Starting to read from COM{port_number}, '
                f'logging into {step_id}.log'
            )

            error = False
            with open(log_file_path, 'a', encoding='utf-8') as f:
                while not stop_signal.is_set():
                    try:
                        current_time = time.time()
                        data = com_port.read_from_port()
                        logger.debug(f'Data read is : {data}')

                        if data:
                            f.write(f'{current_time}' + data + '\n')
                            f.flush()

                        time.sleep(0.05)

                    except Exception as e:
                        logger.error(
                            f'[{self.name}] Error while reading from ' f'COM{port_number}: {e}'
                        )
                        break

            if error:
                self.execution_status = StepExecutionStatus.EXECUTE_FAILED
                logger.warning(
                    f'[{self.name}] Exiting com_read for COM{port_number}. ' f'Errors happened'
                )
            else:
                self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
                logger.success(f'[{self.name}] Exiting com_read for COM{port_number}')

        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = f'[{self.name}] Scan on COM{port_number} failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

    def _com_interrupt_boot(self, params: Dict[str, Any]) -> None:
        """Interrupt the boot sequence on the COM port.

        Repeatedly sends the configured command and reads from the port
        until the expected string is detected or the timeout is exceeded.
        """
        try:
            port_number = params['port']

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            port = self.resources['com_ports'][port_number]
            start_time = time.time()
            last_command_sent_time = 0
            command_interval = 0.5

            while True:
                if time.time() - last_command_sent_time >= command_interval:
                    port.write_to_port(params['cmd'])
                    last_command_sent_time = time.time()

                try:
                    line_read_from_com = port.read_from_port()
                    logger.debug(f'line read: {line_read_from_com}')
                except queue.Empty:
                    if time.time() - start_time > params['timeout']:
                        message = (
                            f'[{self.name}] Timeout exceeded, boot sequence ' f"couldn't be stopped"
                        )
                        raise ExecutionStepError(message, phase=self.name)
                    continue

                if params['expected_str'] in line_read_from_com:
                    logger.info(
                        f"[{self.name}] '{params['expected_str']}' detected, "
                        f"interrupting boot sequence"
                    )
                    break

        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = f'[{self.name}] Interrupt boot on COM{port_number} ' f'failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(
            f'[{self.name}] Interrupt boot on COM{port_number} ' f'executed successfully'
        )

    def _com_scan(self, params: Dict[str, Any]) -> None:
        """Scan the COM port for expected string(s) reading directly from the port.

        Supports ordered and unordered scanning with optional timer
        checkpoint recording.  On timeout the step is marked as failed
        and returns without raising.
        """
        try:
            port_number = params['port']
            search_strings = [
                details['search_string'] for _key, details in params['expected_strs'].items()
            ]
            reference_timer = params.get('log_timings_in_ref_timer')
            timeout = params['timeout']
            order_relevant = params.get('order_relevant', True)

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            port = self.resources['com_ports'][port_number]
            start_time = time.perf_counter()
            search_strings_set = set(search_strings)

            if reference_timer is not None:
                if reference_timer not in self.resources['timers']:
                    message = (
                        f'[{self.name}] Time checkpoints cannot be added '
                        f'since timer {reference_timer} was not initialized'
                    )
                    raise RuntimeConfigError(message, phase=self.name)
                timer = self.resources['timers'][reference_timer]
            else:
                timer = None

            if order_relevant:
                for (
                    checkpoint_display_string,
                    string_to_search_config,
                ) in params['expected_strs'].items():
                    string_to_search = string_to_search_config['search_string']
                    while time.perf_counter() - start_time < timeout:
                        line = port.read_from_port()
                        self.log_content.append(line)
                        if string_to_search in line:
                            if timer:
                                checkpoint_threshold = string_to_search_config.get('threshold', -1)
                                threshold_exceeded = timer.add_checkpoint(
                                    checkpoint_display_string,
                                    checkpoint_threshold,
                                )
                                if threshold_exceeded:
                                    self.test_status = StepEvaluationStatus.FAILED

                                self.result_string.append(
                                    f"String found: '{line}' "
                                    f'(Threshold exceeded = {threshold_exceeded})'
                                )
                            else:
                                self.result_string.append(f"String found: '{line}'")
                            break
                    else:
                        error_string = f"Timeout looking for '{string_to_search}'"
                        self.test_status = StepEvaluationStatus.FAILED
                        self.result_string.append(error_string)
                        logger.error(error_string)
                        return
            else:
                found_strings = set()
                while time.perf_counter() - start_time < timeout:
                    line = port.read_from_port()
                    self.log_content.append(line)

                    for (
                        checkpoint_display_string,
                        string_to_search_config,
                    ) in params['expected_strs'].items():
                        string_to_search = string_to_search_config['search_string']
                        if string_to_search in line:
                            found_strings.add(string_to_search)
                            if timer:
                                checkpoint_threshold = string_to_search_config.get('threshold', -1)
                                threshold_exceeded = timer.add_checkpoint(
                                    checkpoint_display_string,
                                    checkpoint_threshold,
                                )
                                if threshold_exceeded:
                                    self.test_status = StepEvaluationStatus.FAILED

                                self.result_string.append(
                                    f"String found: '{line}' "
                                    f'(Threshold exceeded = {threshold_exceeded})'
                                )
                            else:
                                self.result_string.append(f"String found: '{line}'")
                    if found_strings == search_strings_set:
                        break
                else:
                    missing_strings = search_strings_set - found_strings
                    error_string = f"Timeout looking for " f"'{', '.join(missing_strings)}'"
                    self.test_status = StepEvaluationStatus.FAILED
                    self.result_string.append(error_string)
                    logger.error(error_string)
                    return

        except KeyError as e:
            message = f'[{self.name}] Missing parameter: {e}'
            raise RuntimeConfigError(message, phase=self.name)
        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = f'[{self.name}] Unknown exception: ' f'{type(e).__name__} - {e}'
            raise RuntimeConfigError(message, phase=self.name)

        if self.test_status == StepEvaluationStatus.NOT_APPLICABLE:
            self.test_status = StepEvaluationStatus.PASSED

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[{self.name}] Scan on COM{port_number} executed successfully')

    def _com_scan_queue(self, params: Dict[str, Any]) -> None:
        """Scan the COM port for expected string(s) reading from the queue.

        More reliable but slower than direct port reading.  A previous
        ``com_read`` step must be running to fill the queue.  Supports
        ordered and unordered scanning with optional timer checkpoint
        recording.
        """
        try:
            port_number = params['port']
            search_strings = [
                details['search_string'] for _key, details in params['expected_strs'].items()
            ]
            reference_timer = params.get('log_timings_in_ref_timer')
            timeout = params['timeout']
            order_relevant = params.get('order_relevant', True)

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            port = self.resources['com_ports'][port_number]
            start_time = time.perf_counter()
            search_strings_set = set(search_strings)

            if reference_timer is not None:
                if reference_timer not in self.resources['timers']:
                    message = (
                        f'[{self.name}] Time checkpoints cannot be added '
                        f'since timer {reference_timer} was not initialized'
                    )
                    raise RuntimeConfigError(message, phase=self.name)
                timer = self.resources['timers'][reference_timer]
            else:
                timer = None

            if order_relevant:
                for (
                    checkpoint_display_string,
                    string_to_search_config,
                ) in params['expected_strs'].items():
                    string_to_search = string_to_search_config['search_string']
                    while time.perf_counter() - start_time < timeout:
                        try:
                            line = port.read_from_queue()
                            self.log_content.append(line)
                        except queue.Empty:
                            continue

                        if string_to_search in line:
                            if timer:
                                checkpoint_threshold = string_to_search_config.get('threshold', -1)
                                threshold_exceeded = timer.add_checkpoint(
                                    checkpoint_display_string,
                                    checkpoint_threshold,
                                )
                                if threshold_exceeded:
                                    self.test_status = StepEvaluationStatus.FAILED

                                self.result_string.append(
                                    f"String found: '{line}' "
                                    f'(Threshold exceeded = {threshold_exceeded})'
                                )
                            else:
                                self.result_string.append(f"String found: '{line}'")
                            break
                    else:
                        error_string = f"Timeout looking for '{string_to_search}'"
                        message = f'[{self.name}] {error_string}'
                        self.test_status = StepEvaluationStatus.FAILED
                        self.result_string.append(error_string)
                        raise ExecutionStepError(message, phase=self.name)
            else:
                found_strings = set()
                while time.perf_counter() - start_time < timeout:
                    try:
                        line = port.read_from_queue()
                        self.log_content.append(line)
                    except queue.Empty:
                        continue

                    for (
                        checkpoint_display_string,
                        string_to_search_config,
                    ) in params['expected_strs'].items():
                        string_to_search = string_to_search_config['search_string']
                        if string_to_search in line:
                            found_strings.add(string_to_search)
                            if timer:
                                checkpoint_threshold = string_to_search_config.get('threshold', -1)
                                threshold_exceeded = timer.add_checkpoint(
                                    checkpoint_display_string,
                                    checkpoint_threshold,
                                )
                                if threshold_exceeded:
                                    self.test_status = StepEvaluationStatus.FAILED

                                self.result_string.append(
                                    f'String found: {line} '
                                    f'(Threshold exceeded = {threshold_exceeded})'
                                )
                            else:
                                self.result_string.append(f'String found: {line}')
                    if found_strings == search_strings_set:
                        break
                else:
                    missing_strings = search_strings_set - found_strings
                    error_string = f"Timeout looking for " f"'{', '.join(missing_strings)}'"
                    message = f'[{self.name}] {error_string}'
                    self.test_status = StepEvaluationStatus.FAILED
                    self.result_string.append(error_string)
                    raise ExecutionStepError(message, phase=self.name)

        except KeyError as e:
            message = f'[{self.name}] Missing parameter: {e}'
            raise RuntimeConfigError(message, phase=self.name)
        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = f'[{self.name}] Unknown exception: ' f'{type(e).__name__} - {e}'
            raise RuntimeConfigError(message, phase=self.name)

        if self.test_status == StepEvaluationStatus.NOT_APPLICABLE:
            self.test_status = StepEvaluationStatus.PASSED

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[{self.name}] Scan on COM{port_number} executed successfully')

    def _com_send_cmd(self, params: Dict[str, Any]) -> None:
        """Send a command to the COM port."""
        try:
            port_number = params['port']

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            port = self.resources['com_ports'][port_number]
            port.write_to_port(params['cmd'])
            logger.debug(f"command send: {params['cmd']}")

        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = (
                f"[{self.name}] Send command {params['cmd']} on " f"COM{port_number} failed: {e!s}"
            )
            self.test_status = StepEvaluationStatus.FAILED
            raise ExecutionStepError(message, phase=self.name)

        self.test_status = StepEvaluationStatus.PASSED
        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(
            f"[{self.name}] Send command {params['cmd']} on "
            f"COM{port_number} executed successfully"
        )

    def _com_close(self, params: Dict[str, Any]) -> None:
        """Close the COM port and remove it from the resource pool."""
        try:
            port_number = params['port']

            if port_number not in self.resources['com_ports']:
                message = f'[{self.name}] COM{port_number} not initialized'
                raise RuntimeConfigError(message, phase=self.name)

            port = self.resources['com_ports'][port_number]
            port.close()
            self.resources['com_ports'].pop(port_number, None)

        except (RuntimeConfigError, ExecutionStepError):
            raise
        except Exception as e:
            message = f'[{self.name}] Close COM{port_number} failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[{self.name}] Close COM{port_number} executed successfully')
