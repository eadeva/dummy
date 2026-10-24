"""Voltcraft power supply steps.
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


class VoltcraftStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'voltcraft_init',
    'voltcraft_power_reset',
    'voltcraft_power_on',
    'voltcraft_power_off',
)
class VoltcraftStep(ExecutionStep):
    params_model = VoltcraftStepParams

    """Unified Voltcraft power supply step.

    Handles all Voltcraft actions: initialization, power reset, power on,
    and power off. The concrete action is determined by the ``step_type``
    field in the step configuration and dispatched internally.

    Config parameters (vary per action):
        id (str):                           Identifier for the power supply in
                                            the shared resource pool.
        port (str):                         Serial port for the power supply (init).
        off_voltage (float):                Voltage threshold for off state (init).
        on_voltage (float):                 Voltage threshold for on state (init).
        max_current_off_state (float):      Maximum current in off state (init).
        min_current_normal_operation (float): Minimum current in normal operation (init).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured Voltcraft action."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'voltcraft_init':
                self._voltcraft_init(params)
            elif step_type == 'voltcraft_power_reset':
                self._voltcraft_power_reset(params)
            elif step_type == 'voltcraft_power_on':
                self._voltcraft_power_on(params)
            elif step_type == 'voltcraft_power_off':
                self._voltcraft_power_off(params)
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

    def _voltcraft_init(self, params: Dict[str, Any]) -> None:
        """Initialize a Voltcraft power supply.

        Creates a new ``VoltcraftPowerSupply`` instance and stores it in
        ``self.resources["voltcrafts"]`` keyed by the configured ``id``.
        Skips initialization if a power supply with the same id already exists.
        """
        from xc_ce_utils.powersupply.voltcraft import VoltcraftPowerSupply

        try:
            ps_id = params['id']

            if 'voltcrafts' not in self.resources:
                self.resources['voltcrafts'] = {}

            if ps_id in self.resources['voltcrafts']:
                logger.warning(
                    f"[{self.name}] Voltcraft with id '{ps_id}' already "
                    f'initialized. Already initialized instance will be used. '
                    f'Be aware: config differences were not checked'
                )
                self.add_to_report = False
                return

            logger.info(
                f"[{self.name}] Initializing Voltcraft power supply '{ps_id}' "
                f"on port {params['port']}"
            )

            power_supply = VoltcraftPowerSupply(
                ps_id=params['id'],
                port=params['port'],
                off_voltage=params['off_voltage'],
                on_voltage=params['on_voltage'],
                max_current_off_state=params['max_current_off_state'],
                min_current_normal_operation=params['min_current_normal_operation'],
            )

            power_supply.connect()

            self.resources['voltcrafts'][ps_id] = power_supply

            self.result_string.append(f"Voltcraft '{ps_id}' initialized successfully")

        except Exception as e:
            message = f"Voltcraft '{params.get('id', 'unknown')}' init failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Voltcraft '{ps_id}' initialized")

    def _voltcraft_power_reset(self, params: Dict[str, Any]) -> None:
        """Reset the power supply by turning off, waiting, and turning on.

        Turns off the power supply, sleeps for 3.5 seconds, then turns
        it back on.
        """
        try:
            ps_id = params['id']
            power_supply = self.resources['voltcrafts'][ps_id]

            logger.info(f"[{self.name}] Power reset for Voltcraft '{ps_id}'")

            power_supply.turn_off()
            logger.info(f'[{self.name}] Power off, waiting 3.5s before power on')
            time.sleep(3.5)
            power_supply.turn_on()

            self.result_string.append(f"Voltcraft '{ps_id}' power reset successful")

        except KeyError:
            message = (
                f"Voltcraft '{params.get('id', 'unknown')}' not found in resources. "
                f"Was voltcraft_init executed?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = f"Voltcraft '{params.get('id', 'unknown')}' power reset failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Voltcraft '{ps_id}' power reset complete")

    def _voltcraft_power_on(self, params: Dict[str, Any]) -> None:
        """Turn on the power supply and verify success."""
        try:
            ps_id = params['id']
            power_supply = self.resources['voltcrafts'][ps_id]

            logger.info(f"[{self.name}] Turning on Voltcraft '{ps_id}'")

            result = power_supply.turn_on()

            if not result:
                message = f"Voltcraft '{ps_id}' power on returned unsuccessful"
                self.result_string.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self.result_string.append(f"Voltcraft '{ps_id}' powered on successfully")

        except ExecutionStepError:
            raise
        except KeyError:
            message = (
                f"Voltcraft '{params.get('id', 'unknown')}' not found in resources. "
                f"Was voltcraft_init executed?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = f"Voltcraft '{params.get('id', 'unknown')}' power on failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Voltcraft '{ps_id}' powered on")

    def _voltcraft_power_off(self, params: Dict[str, Any]) -> None:
        """Turn off the power supply and verify success."""
        try:
            ps_id = params['id']
            power_supply = self.resources['voltcrafts'][ps_id]

            logger.info(f"[{self.name}] Turning off Voltcraft '{ps_id}'")

            result = power_supply.turn_off()

            if not result:
                message = f"Voltcraft '{ps_id}' power off returned unsuccessful"
                self.result_string.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self.result_string.append(f"Voltcraft '{ps_id}' powered off successfully")

        except ExecutionStepError:
            raise
        except KeyError:
            message = (
                f"Voltcraft '{params.get('id', 'unknown')}' not found in resources. "
                f"Was voltcraft_init executed?"
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)
        except Exception as e:
            message = f"Voltcraft '{params.get('id', 'unknown')}' power off failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Voltcraft '{ps_id}' powered off")
