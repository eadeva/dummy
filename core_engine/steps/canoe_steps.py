"""CANoe automation steps for the core engine.

Provides 9 step types for Vector CANoe lifecycle, measurement,
system variables, XCP configuration, and test execution.

Test execution steps (``canoe_execute_test_config``,
``canoe_execute_test_env``, ``canoe_execute_test_modules``) inherit
from :class:`~xc_ce_utils.core_engine.steps.base.TestStep` and use
its built-in JUnit XML report generation.
"""

import configparser
import os
import shutil
import tempfile
from pathlib import Path
from traceback import format_exc
from typing import Any, ClassVar, Dict, Optional

from pydantic import Field

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
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci, run_command


class CanoeStepParams(BaseStepParams):
    canoe_close: Optional[Any] = Field(default=None)
    canoe_execute_yaml_tests: Optional[Any] = Field(default=None)
    canoe_execute_test_config: Optional[Any] = Field(default=None)
    canoe_execute_test_env: Optional[Any] = Field(default=None)
    canoe_execute_test_modules: Optional[Any] = Field(default=None)
    canoe_load_xcp_config: Optional[Any] = Field(default=None)
    canoe_open: Optional[Any] = Field(default=None)
    canoe_set_sysvar: Optional[Any] = Field(default=None)
    canoe_start_measurement: Optional[Any] = Field(default=None)
    canoe_stop_measurement: Optional[Any] = Field(default=None)
    canoe_ini_file: Optional[Any] = Field(default=None)
    model_config: ClassVar[Dict[str, str]] = {'extra': 'forbid'}


@StepRegistry.register(
    'canoe_open',
    'canoe_start_measurement',
    'canoe_stop_measurement',
    'canoe_load_xcp_config',
    'canoe_set_sysvar',
    'canoe_execute_test_config',
    'canoe_execute_test_env',
    'canoe_execute_test_modules',
    'canoe_execute_yaml_tests',
    'canoe_ini_file',
    'canoe_close',
)
class CanoeStep(ExecutionStep):
    params_model = CanoeStepParams

    """Unified Vector CANoe step.

    Handles all CANoe actions: open/close, measurement control,
    system variable manipulation, XCP configuration, and test execution
    (configurations, environments, and individual test modules).

    Inherits from :class:`TestStep` so test execution actions can
    populate ``self.test_results`` and call ``self.report_results()``
    for automatic JUnit XML generation and status evaluation.

    The concrete action is determined by the ``action`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action -- see individual methods):
        CANOE_ID (str):            Identifier for the CANoe instance in the
                                   shared resource pool.
        config_path (str):         Path to CANoe configuration file (.cfg).
        xcp_config_path (str):     Path to XCP configuration file.
        namespace (str):           System variable namespace.
        variable (str):            System variable name.
        value (str|int|float):     System variable value.
        test_suite (str):          Comma-separated test configuration names.
        sw_variant (str):          Software variant profile for test configs.
        test_environments (str):   Comma-separated test environment names.
        test_modules (str):        Comma-separated test module names.
    """

    config_fields: ClassVar[Dict[str, Any]] = {
        'canoe_open': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier for the resource pool',
            },
            'config_path': {
                'type': 'str',
                'required': False,
                'description': 'Path to CANoe configuration file (.cfg)',
            },
            'headless': {
                'type': 'bool',
                'required': False,
                'description': 'Run CANoe in headless mode (default: false). Auto-forced to true in CI pipelines.',
            },
            'keep_open': {
                'type': 'bool',
                'required': False,
                'description': 'Keep CANoe open when resources are released (default: false)',
            },
        },
        'canoe_start_measurement': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
        },
        'canoe_stop_measurement': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
        },
        'canoe_load_xcp_config': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'xcp_config_path': {
                'type': 'str',
                'required': True,
                'description': 'Path to XCP configuration file',
            },
        },
        'canoe_set_sysvar': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'namespace': {
                'type': 'str',
                'required': True,
                'description': 'System variable namespace',
            },
            'variable': {
                'type': 'str',
                'required': True,
                'description': 'System variable name',
            },
            'value': {
                'type': 'str',
                'required': True,
                'description': 'System variable value',
            },
        },
        'canoe_execute_test_config': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'test_suite': {
                'type': 'str',
                'required': True,
                'description': 'Comma-separated test configuration names',
            },
            'sw_variant': {
                'type': 'str',
                'required': False,
                'description': 'Software variant profile',
            },
            'vtest_report': {
                'type': 'bool',
                'required': False,
                'description': 'Generate vTEST report output (default: false)',
            },
        },
        'canoe_execute_test_env': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'test_environments': {
                'type': 'str',
                'required': True,
                'description': 'Comma-separated test environment names',
            },
            'vtest_report': {
                'type': 'bool',
                'required': False,
                'description': 'Generate vTEST report output (default: false)',
            },
        },
        'canoe_execute_test_modules': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'test_modules': {
                'type': 'str',
                'required': True,
                'description': 'Comma-separated test module names',
            },
            'vtest_report': {
                'type': 'bool',
                'required': False,
                'description': 'Generate vTEST report output (default: false)',
            },
        },
        'canoe_execute_yaml_tests': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'tests': {
                'type': 'list',
                'required': True,
                'description': 'Folders searched recursively for .vtestunit.yaml files',
            },
            'test_config': {
                'type': 'str',
                'required': False,
                'description': 'CANoe test configuration name (default: CT)',
            },
            'mode': {
                'type': 'int',
                'required': False,
                'description': 'Execution mode: 1 per test unit, 2 all together (default: 1)',
            },
            'vtest_report': {
                'type': 'bool',
                'required': False,
                'description': 'Generate vTEST report output (default: false)',
            },
        },
        'canoe_ini_file': {
            'target_path': {
                'type': 'str',
                'required': True,
                'description': 'Target path for generated INI file',
            },
            'sections': {
                'type': 'dict',
                'required': True,
                'description': 'INI sections mapped to parameter dictionaries',
            },
        },
        'canoe_close': {
            'CANOE_ID': {
                'type': 'str',
                'required': True,
                'description': 'CANoe instance identifier',
            },
            'save_config': {
                'type': 'bool',
                'required': False,
                'description': 'Save configuration before closing (default: false)',
            },
        },
    }

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

        step_type = self.config.get('step_type') or self.config.get('type', '')
        if step_type == 'canoe_open':
            self.game_stopper = True

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured CANoe step."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type') or self.config.get('type', '')
            params = self.config.get('params', {})

            dispatch = {
                'canoe_open': self._canoe_open,
                'canoe_start_measurement': self._canoe_start_measurement,
                'canoe_stop_measurement': self._canoe_stop_measurement,
                'canoe_load_xcp_config': self._canoe_load_xcp_config,
                'canoe_set_sysvar': self._canoe_set_sysvar,
                'canoe_execute_test_config': self._canoe_execute_test_config,
                'canoe_execute_test_env': self._canoe_execute_test_env,
                'canoe_execute_test_modules': self._canoe_execute_test_modules,
                'canoe_execute_yaml_tests': self._canoe_execute_yaml_tests,
                'canoe_ini_file': self._canoe_ini_file,
                'canoe_close': self._canoe_close,
            }

            handler = dispatch.get(step_type)
            if handler is None:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"step_type '{step_type}' not recognized!"
                )
                logger.critical(message)
                raise AbortError(message, phase=self.name)

            handler(params)

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

    def _canoe_open(self, params: Dict[str, Any]) -> None:
        """Open CANoe and optionally load a configuration.

        Creates a :class:`CanoeTestApi` instance and stores it in
        ``self.resources["canoes"]`` keyed by ``CANOE_ID``.
        """
        from xc_ce_utils.canoe.canoe_test_api import CanoeTestApi  # noqa: PLC0415

        try:
            canoe_id = params['CANOE_ID']

            if canoe_id in self.resources['canoes']:
                logger.warning(
                    f'[{self.name}] CANoe with id {canoe_id} already open. Using existing instance.'
                )
                self.add_to_report = False
                return

            canoe = CanoeTestApi()
            headless = params.get('headless', False)
            if is_running_in_ci():
                headless = True
                logger.info(f'[{self.name}] CI pipeline detected â€” forcing headless mode')
            canoe.open(
                config_path=params.get('config_path', ''),
                headless=headless,
            )

            canoe.keep_open = params.get('keep_open', False)
            self.resources['canoes'][canoe_id] = canoe

            self.result_string.append(f'CANoe {canoe_id} opened successfully')
        except Exception as e:
            message = f"CANoe '{params.get('CANOE_ID', '?')}' open failed: {e!s}"
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] CANoe {canoe_id} opened')

    def _canoe_start_measurement(self, params: Dict[str, Any]) -> None:
        """Start CANoe measurement."""
        canoe_id = params['CANOE_ID']
        try:
            self.resources['canoes'][canoe_id].start_measurement()
            self.result_string.append('Measurement started')
        except Exception as e:
            message = f'CANoe start measurement failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Measurement started: {canoe_id}')

    def _canoe_stop_measurement(self, params: Dict[str, Any]) -> None:
        """Stop CANoe measurement."""
        canoe_id = params['CANOE_ID']
        try:
            self.resources['canoes'][canoe_id].stop_measurement()
            self.result_string.append('Measurement stopped')
        except Exception as e:
            message = f'CANoe stop measurement failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Measurement stopped: {canoe_id}')

    def _canoe_load_xcp_config(self, params: Dict[str, Any]) -> None:
        """Load XCP configuration into CANoe."""
        canoe_id = params['CANOE_ID']
        try:
            self.resources['canoes'][canoe_id].add_xcp_configuration(params['xcp_config_path'])
            self.result_string.append(f'XCP config loaded: {params["xcp_config_path"]}')
        except Exception as e:
            message = f'CANoe load XCP config failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] XCP config loaded: {canoe_id}')

    def _canoe_set_sysvar(self, params: Dict[str, Any]) -> None:
        """Set a CANoe system variable."""
        canoe_id = params['CANOE_ID']
        try:
            self.resources['canoes'][canoe_id].set_sysvar_value(
                params['namespace'], params['variable'], params['value']
            )
            self.result_string.append(
                f'SysVar set: {params["namespace"]}::{params["variable"]} = {params["value"]}'
            )
        except Exception as e:
            message = f'CANoe set sysvar failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] SysVar set: {canoe_id}')

    def _set_canoe_test_status(self, results: Dict[str, Any]) -> None:
        """Set the step verdict from CANoe's aggregate result counts."""
        if results.get('failed', 0) > 0 or results.get('other', 0) > 0:
            self.test_status = StepEvaluationStatus.FAILED
        else:
            self.test_status = StepEvaluationStatus.PASSED

    def _copy_canoe_reports(self, results: Dict[str, Any]) -> list[Path]:
        """Copy CANoe XML reports and HTML companions to step reports."""
        source_values = []
        if results.get('report_path'):
            source_values.append(results['report_path'])
        source_values.extend(results.get('report_paths') or [])

        report_dir = self.get_step_reports_folder()
        report_dir.mkdir(parents=True, exist_ok=True)
        copied: list[Path] = []

        for source_value in source_values:
            source = Path(source_value)
            if not source.is_file():
                logger.warning(f'[{self.name}] CANoe report does not exist: {source}')
                continue

            sources = [source]
            html_source = source.with_suffix('.html')
            if html_source.is_file():
                sources.append(html_source)

            suffix_index = 1
            while (report_dir / source.name).exists():
                suffix_index += 1
                candidate = report_dir / (f'{source.stem}_{suffix_index}{source.suffix}')
                if not candidate.exists():
                    break

            for current_source in sources:
                if suffix_index == 1:
                    destination = report_dir / current_source.name
                else:
                    destination = report_dir / (
                        f'{current_source.stem}_{suffix_index}{current_source.suffix}'
                    )
                shutil.copy2(current_source, destination)
                copied.append(destination)

        return copied

    def _run_vtest_report(self, enabled: bool) -> None:
        """Run ReportViewer CLI without changing CANoe test verdicts."""
        if not enabled:
            return

        viewer_dir = os.getenv('ARTIFACT_CANOE_REPORT_VIEWER')
        if not viewer_dir:
            logger.warning(
                f'[{self.name}] ARTIFACT_CANOE_REPORT_VIEWER is not set; '
                'skipping vTEST report generation'
            )
            return

        viewer = Path(viewer_dir) / 'ReportViewerCli.exe'
        if not viewer.is_file():
            logger.warning(f'[{self.name}] ReportViewerCli.exe does not exist: {viewer}')
            return

        report_dir = self.get_step_reports_folder()
        report_dir.mkdir(parents=True, exist_ok=True)
        try:
            run_command([str(viewer), '-d', str(report_dir), '-xu'])
        except Exception as error:
            logger.warning(f'[{self.name}] vTEST report generation failed: {error}')

    def _canoe_execute_test_config(self, params: Dict[str, Any]) -> None:
        """Execute vTESTstudio test configuration(s) and generate JUnit XML."""
        canoe_id = params['CANOE_ID']
        test_suite = params['test_suite']
        sw_variant = params.get('sw_variant')

        try:
            results = self.resources['canoes'][canoe_id].execute_test_configuration(
                test_suite, sw_variant=sw_variant
            )

            self._set_canoe_test_status(results)
            self._copy_canoe_reports(results)
            self._run_vtest_report(params.get('vtest_report', False))

            self.result_string.append(
                f"Test config '{test_suite}': "
                f'{results["passed"]}/{results["total"]} passed, '
                f'{results["failed"]} failed'
            )

        except Exception as e:
            message = f'CANoe execute test config failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        if results['failed'] > 0:
            logger.warning(
                f"[{self.name}] Test config '{test_suite}': {results['failed']} test(s) failed"
            )
        else:
            logger.success(
                f"[{self.name}] Test config '{test_suite}': all {results['total']} passed"
            )

    def _canoe_execute_test_env(self, params: Dict[str, Any]) -> None:
        """Execute CAPL/XML test environment(s) and generate JUnit XML."""
        canoe_id = params['CANOE_ID']
        test_environments = params['test_environments']

        try:
            results = self.resources['canoes'][canoe_id].execute_test_environment(test_environments)

            self._set_canoe_test_status(results)
            self._copy_canoe_reports(results)
            self._run_vtest_report(params.get('vtest_report', False))

            self.result_string.append(
                f"Test env '{test_environments}': "
                f'{results["passed"]}/{results["total"]} passed, '
                f'{results["failed"]} failed'
            )

        except Exception as e:
            message = f'CANoe execute test env failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        if results['failed'] > 0:
            logger.warning(
                f"[{self.name}] Test env '{test_environments}': {results['failed']} test(s) failed"
            )
        else:
            logger.success(
                f"[{self.name}] Test env '{test_environments}': all {results['total']} passed"
            )

    def _canoe_execute_test_modules(self, params: Dict[str, Any]) -> None:
        """Execute specific test module(s) by name and generate JUnit XML."""
        canoe_id = params['CANOE_ID']
        test_modules = params['test_modules']

        try:
            results = self.resources['canoes'][canoe_id].execute_test_modules(test_modules)

            self._set_canoe_test_status(results)
            self._copy_canoe_reports(results)
            self._run_vtest_report(params.get('vtest_report', False))

            self.result_string.append(
                f"Test modules '{test_modules}': "
                f'{results["passed"]}/{results["total"]} passed, '
                f'{results["failed"]} failed'
            )

        except Exception as e:
            message = f'CANoe execute test modules failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        if results['failed'] > 0:
            logger.warning(
                f"[{self.name}] Test modules '{test_modules}': {results['failed']} test(s) failed"
            )
        else:
            logger.success(
                f"[{self.name}] Test modules '{test_modules}': all {results['total']} passed"
            )

    def _canoe_execute_yaml_tests(self, params: Dict[str, Any]) -> None:
        """Execute YAML vTESTstudio test units and generate reports."""
        canoe_id = params['CANOE_ID']
        test_config = params.get('test_config', 'CT')
        mode = params.get('mode', 1)

        try:
            results = self.resources['canoes'][canoe_id].execute_yaml_tests(
                params['tests'], test_config_name=test_config, mode=mode
            )
            self._set_canoe_test_status(results)
            self._copy_canoe_reports(results)
            self._run_vtest_report(params.get('vtest_report', False))
            self.result_string.append(
                f"YAML tests '{test_config}': "
                f'{results["passed"]}/{results["total"]} passed, '
                f'{results["failed"]} failed'
            )
        except Exception as e:
            message = f'CANoe execute YAML tests failed: {e!s}'
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name) from e

    def _canoe_ini_file(self, params: Dict[str, Any]) -> None:
        """Create a CANoe INI file."""
        temporary_path: Optional[Path] = None
        try:
            target_value = params.get('target_path')
            if not isinstance(target_value, str) or not target_value:
                raise ValueError('target_path must be a non-empty string')

            sections = params.get('sections')
            if not isinstance(sections, dict) or not sections:
                raise ValueError('sections must be a non-empty dictionary')

            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            for section_name, section_values in sections.items():
                if not isinstance(section_name, str) or not section_name:
                    raise ValueError('section names must be non-empty strings')
                if not isinstance(section_values, dict) or not section_values:
                    raise ValueError(f"section '{section_name}' must be a non-empty dictionary")

                parser.add_section(section_name)
                for parameter_name, parameter_value in section_values.items():
                    if not isinstance(parameter_name, str) or not parameter_name:
                        raise ValueError(
                            f"section '{section_name}' parameter names must be strings"
                        )
                    if not isinstance(parameter_value, (str, int, float, bool)):
                        raise ValueError(f"section '{section_name}' values must be scalar")
                    parser.set(
                        section_name,
                        parameter_name,
                        str(parameter_value),
                    )

            target = Path(target_value)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                newline='\n',
                prefix=f'.{target.name}.',
                suffix='.tmp',
                dir=target.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                parser.write(temporary_file, space_around_delimiters=False)

            temporary_path.replace(target)
            temporary_path = None
            self.result_string.append(f'CANoe INI file created: {target}')
            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            self.test_status = StepEvaluationStatus.PASSED
            logger.success(f'[{self.name}] CANoe INI file created: {target}')
        except Exception as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ExecutionStepError(
                f'[{self.name}] CANoe INI file creation failed: {error}',
                phase=self.name,
            ) from error

    def _canoe_close(self, params: Dict[str, Any]) -> None:
        """Close the CANoe application and remove it from the resource pool."""
        canoe_id = params['CANOE_ID']
        save_config = params.get('save_config', False)
        try:
            canoe = self.resources['canoes'][canoe_id]
            if getattr(canoe, 'keep_open', False):
                logger.info(f"[{self.name}] CANoe '{canoe_id}' keep_open is set â€” skipping close")
            else:
                canoe.quit(save_cfg=save_config)
            self.resources['canoes'].pop(canoe_id, None)
            self.result_string.append(f'CANoe {canoe_id} closed')
        except Exception as e:
            message = f"Closing CANoe '{canoe_id}' failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] CANoe closed: {canoe_id}')
