"""Trace32/Lauterbach debugger steps.
"""

from pathlib import Path
from traceback import format_exc
from typing import Any, Dict

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepEvaluationStatus,
    StepExecutionStatus,
)


class T32StepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    't32_setup',
    't32_get_state',
    't32_run_cmm_script',
    't32_run_cmd',
    't32_erase_flash',
    't32_flash_binary',
    't32_flash_hex',
    't32_load_elf',
    't32_close',
)
class T32Step(ExecutionStep):
    params_model = T32StepParams

    """Unified Trace32/Lauterbach debugger step.

    Handles all T32 actions: setup, state queries, CMM script execution,
    command execution, flash operations (erase, binary, hex), ELF loading,
    and teardown.

    The concrete action is determined by the ``action`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action -- see individual methods):
        T32_ID (str):                   Identifier for the Trace32 instance in the
                                        shared resource pool.
        cmm_base_path (str):            Base path for CMM scripts (setup).
        TARGET_ARQUITECTURE (str):      Target architecture string (setup).
        start_cmm (str):                Startup CMM script (setup).
        T32_HOST (str):                 Trace32 API host (setup).
        T32_API_PORT (int):             Trace32 API port (setup).
        T32_API_PACKET_LENGTH (int):    Trace32 API packet length (setup).
        script (str):                   CMM script path (run_cmm_script).
        timeout (int):                  Script execution timeout (run_cmm_script).
        cmd (str):                      T32 command string (run_cmd).
        start (str):                    Flash start address (erase_flash, flash_binary).
        end (str):                      Flash end address (erase_flash).
        start_address (str):            Binary flash start address (flash_binary).
        bin_file (str):                 Binary file path (flash_binary).
        hex_file (str):                 Hex file path (flash_hex).
        elf_file (str):                 ELF file path (load_elf).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

        # t32_setup is always a game-stopper -- without a debugger connection
        # nothing else can proceed.
        step_type = self.config.get('step_type') or self.config.get('type', '')
        if step_type == 't32_setup':
            self.game_stopper = True

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured T32 step."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type') or self.config.get('type', '')
            params = self.config.get('params', {})

            if step_type == 't32_setup':
                self._t32_setup(params)
            elif step_type == 't32_get_state':
                self._t32_get_state(params)
            elif step_type == 't32_run_cmm_script':
                self._t32_run_cmm_script(params)
            elif step_type == 't32_run_cmd':
                self._t32_run_cmd(params)
            elif step_type == 't32_erase_flash':
                self._t32_erase_flash(params)
            elif step_type == 't32_flash_binary':
                self._t32_flash_binary(params)
            elif step_type == 't32_flash_hex':
                self._t32_flash_hex(params)
            elif step_type == 't32_load_elf':
                self._t32_load_elf(params)
            elif step_type == 't32_close':
                self._t32_close(params)
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
            message = f'[{self.name}] Unknown exception: {e!s}'
            logger.error(f'{message}\n{format_exc()}')
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _t32_setup(self, params: Dict[str, Any]) -> None:
        """Set up the Trace32 environment.

        Creates a new ``Trace32Api`` instance, generates the T32 config,
        starts PowerView, loads the T32 API, initialises, and attaches.
        The resulting handle is stored in ``self.resources["lauterbachs"]``
        keyed by the configured ``T32_ID``.
        """
        import os
        import platform

        # Lazy import -- avoid pulling in the lauterbach module at load time
        from xc_ce_utils.trace32.trace32Api import Trace32Api

        try:
            if platform.system() == 'Windows':
                os.environ['OS_SEPARATOR'] = '\\'
                os.environ['T32_TMP_FOLDER'] = 'Temp'
                os.environ['T32_HELP_FOLDER'] = 'pdf'
            else:
                os.environ['OS_SEPARATOR'] = '/'
                os.environ['T32_TMP_FOLDER'] = 'tmp'

            logger.info(
                f"[{self.name}] Setting up Trace32 with cmm path: " f"{params['cmm_base_path']}"
            )

            if params['T32_ID'] in self.resources['lauterbachs']:
                logger.warning(
                    f"[{self.name}] Trace32 with id {params['T32_ID']} already "
                    f"set-up. Already set-up instance will be used. Be aware: "
                    f"config differences were not checked"
                )
                self.add_to_report = False
                return
            else:
                trace32 = Trace32Api(
                    params['cmm_base_path'],
                    log_file=f"{Path.cwd() / 'logs' / self.log_file!s}",
                )

                trace32.generate_trace32_config(params)
                trace32.start_power_view(params['TARGET_ARQUITECTURE'], params['start_cmm'])
                trace32.load_t32api(
                    params['T32_HOST'],
                    params['T32_API_PORT'],
                    params['T32_API_PACKET_LENGTH'],
                )
                trace32.initialize_t32()
                trace32.attach()

                trace32.keep_open = params.get('keep_open', False)
                self.resources['lauterbachs'][params['T32_ID']] = trace32

                self.result_string.append(f"Trace32 {params['T32_ID']} set up successfully")
        except Exception as e:
            message = f"T32 '{params['T32_ID']}' setup failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Trace32 {params['T32_ID']} set up")

    def _t32_get_state(self, params: Dict[str, Any]) -> None:
        """Query the current state of the Trace32 target.

        Raises a ``ExecutionStepError`` if the target is in reset or the state
        query fails.
        """
        try:
            state_message = self.resources['lauterbachs'][params['T32_ID']].get_state()
            if 'target in reset' in state_message:
                message = f'[{self.name}] Target in reset, aborting...'
                self.log_content.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f'[{self.name}] T32 get state failed: {e!s}'
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Last AREA message: {state_message}')

    def _t32_run_cmm_script(self, params: Dict[str, Any]) -> None:
        """Execute a CMM script on the Trace32 instance.

        Supports an optional ``timeout`` parameter (default 100s).
        Specific known non-fatal errors ("A53 Wakeup error",
        "debug port fail") are logged as warnings and do not raise.
        """
        DEFAULT_TIMEOUT_FOR_CMM_SCRIPT_EXECUTION = 100
        timeout = DEFAULT_TIMEOUT_FOR_CMM_SCRIPT_EXECUTION

        try:
            if 'timeout' in params:
                timeout = params['timeout']

            message_area_str = self.resources['lauterbachs'][params['T32_ID']].execute_t32_script(
                params['script'], timeout
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            # Known non-fatal conditions -- log and continue
            if 'A53 Wakeup error' in str(e) or 'debug port fail' in str(e):
                logger.warning(f'[{self.name}] Ignored error: {e!s}')
                return

            message = f'T32 cmm script execution failed: {e!s}'
            self.log_content.extend(message.split('\n'))
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Script run successful: {params['script']}")

    def _t32_run_cmd(self, params: Dict[str, Any]) -> None:
        """Execute a single T32 command."""
        try:
            message_area_str = self.resources['lauterbachs'][params['T32_ID']].execute_t32_command(
                params['cmd']
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            message = f'T32 run command failed: {e!s}'
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Command run successful: {params['cmd']}")

    def _t32_erase_flash(self, params: Dict[str, Any]) -> None:
        """Erase a flash memory range on the target."""
        try:
            message_area_str = self.resources['lauterbachs'][params['T32_ID']].erase_flash(
                params['start'], params['end']
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            message = f"T32 erase flash failed " f"({params['start']}-{params['end']}): {e!s}"
            self.log_content.extend(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Erased memory block " f"{params['start']}-{params['end']}")

    def _t32_flash_binary(self, params: Dict[str, Any]) -> None:
        """Flash a binary file to the target at the given start address."""
        try:
            message_area_str = self.resources['lauterbachs'][params['T32_ID']].flash_binary(
                params['bin_file'], params['start_address']
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            message = (
                f"T32 flash binary failed ({params['bin_file']}, "
                f"start_address: {params['start_address']}): {e!s}"
            )
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(
            f"[{self.name}] Binary flashed T32: {params['bin_file']}, "
            f"start_address={params['start_address']}"
        )

    def _t32_flash_hex(self, params: Dict[str, Any]) -> None:
        """Flash a hex file to the target."""
        try:
            message_area_str = self.resources['lauterbachs'][params['T32_ID']].flash_hex(
                params['hex_file']
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            message = f"T32 flash hex file ({params['hex_file']}) " f"failed: {e!s}"
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Hex flashed T32: {params['hex_file']}")

    def _t32_load_elf(self, params: Dict[str, Any]) -> None:
        """Load an ELF file onto the target for debug symbol resolution."""
        try:
            message_area_str = self.resources['lauterbachs'][params['T32_ID']].load_elf(
                params['elf_file']
            )
            self.log_content.append(message_area_str)
        except Exception as e:
            message = f"T32 load elf file ({params['elf_file']}) " f"failed: {e!s}"
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Loading elf file: {params['elf_file']}")

    def _t32_close(self, params: Dict[str, Any]) -> None:
        """Close the Trace32 connection and remove it from the resource pool."""
        try:
            t32 = self.resources['lauterbachs'][params['T32_ID']]
            if getattr(t32, 'keep_open', False):
                logger.info(
                    f"[{self.name}] Trace32 '{params['T32_ID']}' keep_open is set â€” skipping close"
                )
                self.resources['lauterbachs'].pop(params['T32_ID'], None)
            else:
                message_area_str = t32.close()
                logger.info(message_area_str)
                self.resources['lauterbachs'].pop(params['T32_ID'], None)
        except Exception as e:
            message = f"Closing T32 '{params['T32_ID']}' failed: {e!s}"
            self.log_content.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Closing T32: {params['T32_ID']}")
