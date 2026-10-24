"""Binary handling steps (convert, split, CRC)."""

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


class BinaryStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'bin_convert_to_bin',
    'bin_split_in_chunks',
    'bin_convert_to_hex',
    'bin_compute_file_crc',
)
class BinaryStep(ExecutionStep):
    params_model = BinaryStepParams

    """Unified binary handling step.

    Handles all binary-related actions: conversion to binary, splitting
    into chunks, conversion to hex/srec, and CRC computation. The concrete
    action is determined by the ``step_type`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action):
        input_path (str):                   Input file path (convert_to_bin, convert_to_hex).
        output_dir (str):                   Output directory path.
        output_variable (str):              Global variable name to store the result path.
        flip_endianness (bool):             Whether to flip endianness (convert_to_bin).
        endianness_byte_group_size (int):   Byte group size for endianness (convert_to_bin).
        chunk_size (int):                   Chunk size for splitting (split_in_chunks).
        chunk_size_unit (str):              Chunk size unit (split_in_chunks).
        hex_type (str):                     Hex format type: "intel" or "motorolla" (convert_to_hex).
        input_file (str):                   Input file path (compute_file_crc).
        crc_type (str):                     CRC algorithm type (compute_file_crc).
        polynom (str):                      CRC polynomial (compute_file_crc).
        start_address (str):               Start address for CRC computation (compute_file_crc).
        end_address (str):                 End address for CRC computation (compute_file_crc).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured binary handling action."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'bin_convert_to_bin':
                self._bin_convert_to_bin(params)
            elif step_type == 'bin_split_in_chunks':
                self._bin_split_in_chunks(params)
            elif step_type == 'bin_convert_to_hex':
                self._bin_convert_to_hex(params)
            elif step_type == 'bin_compute_file_crc':
                self._bin_compute_file_crc(params)
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

    def _bin_convert_to_bin(self, params: Dict[str, Any]) -> None:
        """Convert a file to binary format.

        Calls ``bin_converter.convert_to_bin`` and stores the result path
        in ``self.global_variables[output_variable]``.
        """
        from xc_ce_utils.binary_handling import bin_converter

        try:
            input_path = params['input_path']
            output_dir = params['output_dir']
            output_variable = params['output_variable']
            flip_endianness = params.get('flip_endianness', False)
            endianness_byte_group_size = params.get('endianness_byte_group_size', 4)

            logger.info(
                f"[{self.name}] Converting '{input_path}' to binary "
                f'(flip_endianness={flip_endianness}, '
                f'byte_group_size={endianness_byte_group_size})'
            )

            result_path = bin_converter.convert_to_bin(
                input_path,
                output_dir,
                flip_endianness,
                endianness_byte_group_size,
            )

            self.global_variables[output_variable] = result_path

            self.result_string.append(f'Binary conversion successful: {result_path}')

        except Exception as e:
            message = f'Binary conversion failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Binary conversion complete: {result_path}')

    def _bin_split_in_chunks(self, params: Dict[str, Any]) -> None:
        """Split a binary file into chunks.

        Calls ``bin_splittler.split_file`` and stores the output directory
        in ``self.global_variables[output_variable]``.
        """
        from xc_ce_utils.binary_handling import bin_splittler

        try:
            input_path = params['input_path']
            chunk_size = params['chunk_size']
            chunk_size_unit = params.get('chunk_size_unit', 'bytes')
            output_dir = params['output_dir']
            output_variable = params['output_variable']

            logger.info(
                f"[{self.name}] Splitting '{input_path}' into chunks "
                f'(size={chunk_size} {chunk_size_unit})'
            )

            bin_splittler.split_file(
                input_path,
                chunk_size,
                chunk_size_unit,
                output_dir,
            )

            self.global_variables[output_variable] = output_dir

            self.result_string.append(f'Binary split successful: output in {output_dir}')

        except Exception as e:
            message = f'Binary split failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Binary split complete: output in {output_dir}')

    def _bin_convert_to_hex(self, params: Dict[str, Any]) -> None:
        """Convert a binary file to hex (Intel) or srec (Motorola) format.

        Dispatches to ``hex_converter.convert_bin_to_hex`` for Intel hex or
        ``hex_converter.convert_bin_to_srec`` for Motorola S-record based on
        the ``hex_type`` parameter.
        """
        from xc_ce_utils.binary_handling import hex_converter

        try:
            input_path = params['input_path']
            output_dir = params['output_dir']
            output_variable = params['output_variable']
            hex_type = params.get('hex_type', 'intel')

            logger.info(f"[{self.name}] Converting '{input_path}' to " f'{hex_type} hex format')

            if hex_type == 'intel':
                result_path = hex_converter.convert_bin_to_hex(
                    input_path,
                    output_dir,
                )
            elif hex_type == 'motorolla':
                result_path = hex_converter.convert_bin_to_srec(
                    input_path,
                    output_dir,
                )
            else:
                message = (
                    f"Unknown hex_type '{hex_type}'. " f"Supported types: 'intel', 'motorolla'"
                )
                raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            self.global_variables[output_variable] = result_path

            self.result_string.append(f'Hex conversion ({hex_type}) successful: {result_path}')

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f'Hex conversion failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Hex conversion ({hex_type}) complete: {result_path}')

    def _bin_compute_file_crc(self, params: Dict[str, Any]) -> None:
        """Compute a CRC for a binary file.

        Calls ``bin_crc_calculator.process_file`` and stores the CRC result
        in ``self.global_variables[output_variable]``.
        """
        from xc_ce_utils.binary_handling import bin_crc_calculator

        try:
            input_file = params['input_file']
            crc_type = params['crc_type']
            polynom = params.get('polynom')
            start_address = params.get('start_address')
            end_address = params.get('end_address')
            output_dir = params.get('output_dir')
            output_variable = params['output_variable']

            logger.info(f"[{self.name}] Computing CRC for '{input_file}' " f'(type={crc_type})')

            crc_result = bin_crc_calculator.process_file(
                input_file,
                crc_type,
                polynom,
                start_address,
                end_address,
                output_dir,
            )

            self.global_variables[output_variable] = crc_result

            self.result_string.append(f'CRC computation successful: {crc_result}')

        except Exception as e:
            message = f'CRC computation failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] CRC computation complete: {crc_result}')
