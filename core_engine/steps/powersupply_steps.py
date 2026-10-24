"""Generic power supply steps.

Provides hardware-agnostic step types that work with any PowerSupplyBase
implementation. The concrete power supply type (``voltcraft``, ``vector_vh``)
is selected via the ``type`` parameter in the step configuration.
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

# ---------------------------------------------------------------------------
# Factory for creating the right PowerSupplyBase subclass
# ---------------------------------------------------------------------------

_PS_RESOURCE_KEY = 'power_supplies'


def _create_power_supply(ps_type: str, params: Dict[str, Any]):
    """Instantiate a PowerSupplyBase subclass based on ``ps_type``."""
    if ps_type == 'voltcraft':
        from xc_ce_utils.powersupply.voltcraft import VoltcraftPowerSupply

        return VoltcraftPowerSupply(
            ps_id=params['id'],
            port=params['port'],
            off_voltage=params['off_voltage'],
            on_voltage=params['on_voltage'],
            max_current_off_state=params['max_current_off_state'],
            min_current_normal_operation=params['min_current_normal_operation'],
        )

    if ps_type == 'vector_vh':
        from xc_ce_utils.powersupply.vector_vh import VectorVHPowerSupply

        return VectorVHPowerSupply(
            ps_id=params['id'],
            dll_path=params.get('dll_path'),
        )

    if ps_type == 'vector_vh_canoe':
        from xc_ce_utils.powersupply.vector_vh_canoe import (
            VectorVHCanoePowerSupply,
        )

        return VectorVHCanoePowerSupply(
            ps_id=params['id'],
            voltage=params.get('voltage', 12.5),
            settle_time=params.get('settle_time', 0.3),
        )

    if ps_type == 'nano_car':
        from xc_ce_utils.powersupply.nano_car import NanoCarPowerSupply

        return NanoCarPowerSupply(
            ps_id=params['id'],
            port=params.get('port'),
        )

    raise ValueError(f"Unknown power supply type: '{ps_type}'")


# ---------------------------------------------------------------------------
# Generic PowerSupply step
# ---------------------------------------------------------------------------


class PowerSupplyStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'power_supply_init',
    'power_supply_on',
    'power_supply_off',
    'power_supply_reset',
    'power_supply_set_voltage',
    category='Hardware',
)
class PowerSupplyStep(ExecutionStep):
    params_model = PowerSupplyStepParams

    """Unified power supply step for any PowerSupplyBase implementation.

    The ``type`` parameter in the step config selects the concrete
    implementation (``voltcraft``, ``vector_vh``).

    Config parameters (vary per action):
        type (str):             Power supply type (``voltcraft`` | ``vector_vh``).
        id (str):               Identifier for the supply in the shared pool.
        port (str):             Serial port (voltcraft only).
        dll_path (str):         Path to VHDevDLL.dll (vector_vh, optional).
        off_voltage (float):    Voltage threshold for off state (voltcraft).
        on_voltage (float):     Voltage threshold for on state (voltcraft).
        max_current_off_state (float):      Max current in off state (voltcraft).
        min_current_normal_operation (float): Min current in normal op (voltcraft).
        voltage (float):        Target voltage (power_supply_set_voltage).
        reset_delay (float):    Seconds between off/on during reset (default 3.5).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    def execute(self) -> None:
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'power_supply_init':
                self._ps_init(params)
            elif step_type == 'power_supply_on':
                self._ps_on(params)
            elif step_type == 'power_supply_off':
                self._ps_off(params)
            elif step_type == 'power_supply_reset':
                self._ps_reset(params)
            elif step_type == 'power_supply_set_voltage':
                self._ps_set_voltage(params)
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
    # Helpers
    # ------------------------------------------------------------------

    def _log_status(self, power_supply, ps_id: str, label: str) -> None:
        """Log current voltage and current readings if supported."""
        try:
            voltage = power_supply.get_voltage()
            current = power_supply.get_current()
            if voltage == 0.0 and current == 0.0:
                return
            logger.info(
                f"[{self.name}] {label} - Supply '{ps_id}': " f'{voltage:.3f} V, {current:.3f} A'
            )
            self.result_string.append(f"{label} - '{ps_id}': {voltage:.3f} V, {current:.3f} A")
        except Exception as e:
            logger.warning(f"[{self.name}] Could not read status for '{ps_id}': {e}")

    def _get_supply(self, params: Dict[str, Any]):
        """Retrieve an initialized power supply from shared resources."""
        ps_id = params['id']
        try:
            return self.resources[_PS_RESOURCE_KEY][ps_id]
        except KeyError:
            message = (
                f"Power supply '{ps_id}' not found in resources. "
                f'Was power_supply_init executed?'
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _ps_init(self, params: Dict[str, Any]) -> None:
        """Initialize a power supply and store it in shared resources."""
        try:
            ps_id = params['id']
            ps_type = params['type']

            if _PS_RESOURCE_KEY not in self.resources:
                self.resources[_PS_RESOURCE_KEY] = {}

            if ps_id in self.resources[_PS_RESOURCE_KEY]:
                logger.warning(
                    f"[{self.name}] Power supply '{ps_id}' already "
                    f'initialized. Reusing existing instance.'
                )
                self.add_to_report = False
                return

            logger.info(f"[{self.name}] Initializing {ps_type} power supply '{ps_id}'")

            power_supply = _create_power_supply(ps_type, params)
            power_supply.connect()

            self.resources[_PS_RESOURCE_KEY][ps_id] = power_supply

            self.result_string.append(f"{ps_type} power supply '{ps_id}' initialized successfully")

        except Exception as e:
            message = f"Power supply '{params.get('id', 'unknown')}' " f"init failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Power supply '{ps_id}' initialized")

    def _ps_on(self, params: Dict[str, Any]) -> None:
        """Turn on the power supply."""
        try:
            ps_id = params['id']
            power_supply = self._get_supply(params)

            logger.info(f"[{self.name}] Turning on power supply '{ps_id}'")
            self._log_status(power_supply, ps_id, 'Before power on')
            result = power_supply.turn_on()

            if not result:
                message = f"Power supply '{ps_id}' turn on returned unsuccessful"
                self.result_string.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self._log_status(power_supply, ps_id, 'After power on')
            self.result_string.append(f"Power supply '{ps_id}' powered on successfully")

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f"Power supply '{params.get('id', 'unknown')}' power on failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Power supply '{ps_id}' powered on")

    def _ps_off(self, params: Dict[str, Any]) -> None:
        """Turn off the power supply."""
        try:
            ps_id = params['id']
            power_supply = self._get_supply(params)

            logger.info(f"[{self.name}] Turning off power supply '{ps_id}'")
            self._log_status(power_supply, ps_id, 'Before power off')
            result = power_supply.turn_off()

            if not result:
                message = f"Power supply '{ps_id}' turn off returned unsuccessful"
                self.result_string.append(message)
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self._log_status(power_supply, ps_id, 'After power off')
            self.result_string.append(f"Power supply '{ps_id}' powered off successfully")

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f"Power supply '{params.get('id', 'unknown')}' power off failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Power supply '{ps_id}' powered off")

    def _ps_reset(self, params: Dict[str, Any]) -> None:
        """Power-cycle the supply: off -> delay -> on."""
        try:
            ps_id = params['id']
            power_supply = self._get_supply(params)
            delay = params.get('reset_delay', 3.5)

            logger.info(f"[{self.name}] Power reset for supply '{ps_id}'")
            self._log_status(power_supply, ps_id, 'Before power reset')

            power_supply.turn_off()
            logger.info(f'[{self.name}] Power off, waiting {delay}s before power on')
            time.sleep(delay)
            power_supply.turn_on()

            self._log_status(power_supply, ps_id, 'After power reset')
            self.result_string.append(f"Power supply '{ps_id}' power reset successful")

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f"Power supply '{params.get('id', 'unknown')}' power reset failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Power supply '{ps_id}' reset complete")

    def _ps_set_voltage(self, params: Dict[str, Any]) -> None:
        """Set the power supply output voltage."""
        try:
            ps_id = params['id']
            voltage = params['voltage']
            power_supply = self._get_supply(params)

            logger.info(f"[{self.name}] Setting power supply '{ps_id}' " f'voltage to {voltage} V')
            power_supply.set_voltage(voltage)

            self.result_string.append(f"Power supply '{ps_id}' voltage set to {voltage} V")

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f"Power supply '{params.get('id', 'unknown')}' " f"set voltage failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Power supply '{ps_id}' voltage set to {voltage} V")
