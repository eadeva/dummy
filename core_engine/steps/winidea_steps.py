"""WinIDEA/iSYSTEM flashing steps for the core engine.
"""

from pathlib import Path
from traceback import format_exc
from typing import Any, ClassVar, Dict, List, Optional

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
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci


class WinIdeaStepParams(BaseStepParams):
    winidea_check_counters: Optional[Any] = Field(default=None)
    winidea_close: Optional[Any] = Field(default=None)
    winidea_configure_session: Optional[Any] = Field(default=None)
    winidea_flash_all: Optional[Any] = Field(default=None)
    winidea_flash_dflash: Optional[Any] = Field(default=None)
    winidea_flash_pflash: Optional[Any] = Field(default=None)
    winidea_flash_pflash_dflash: Optional[Any] = Field(default=None)
    winidea_flash_ucb: Optional[Any] = Field(default=None)
    winidea_get_cpu_status: Optional[Any] = Field(default=None)
    winidea_load_symbols: Optional[Any] = Field(default=None)
    winidea_read_variables: Optional[Any] = Field(default=None)
    winidea_reset: Optional[Any] = Field(default=None)
    winidea_setup: Optional[Any] = Field(default=None)
    winidea_verify_variables: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'winidea_setup',
    'winidea_configure_session',
    'winidea_flash_pflash',
    'winidea_flash_dflash',
    'winidea_flash_ucb',
    'winidea_flash_pflash_dflash',
    'winidea_flash_all',
    'winidea_load_symbols',
    'winidea_read_variables',
    'winidea_check_counters',
    'winidea_verify_variables',
    'winidea_get_cpu_status',
    'winidea_reset',
    'winidea_close',
)
class WinIdeaStep(ExecutionStep):
    params_model = WinIdeaStepParams

    """Unified WinIDEA/iSYSTEM step.

    Handles all WinIDEA actions: setup, flash operations (PFLASH, DFLASH,
    UCB), target reset, teardown, and test verification steps.

    Inherits from :class:`TestStep` so test-oriented actions
    (``check_counters``, ``verify_variables``) can populate
    ``self.test_results`` and call ``self.report_results()``
    for automatic JUnit XML generation and status evaluation.

    The concrete action is determined by the ``action`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action -- see individual methods):
        WINIDEA_ID (str):       Identifier for the WinIDEA instance in the
                                shared resource pool.
        device (str):           Target device (e.g. ``"TC387QP"``).
        emulator_type (str):    Debug probe type (e.g. ``"iC5000"``).
        com_mode (str):         Communication mode (e.g. ``"USB"``).
        winidea_dir (str):      Path to winIDEA installation.
        workspace_dir (str):    Path to winIDEA workspace directory.
        sym_path (str):         ELF symbol file path (setup, optional).
        hex_file (str):         HEX file path (flash_pflash/flash_dflash/flash_ucb).
    """

    config_fields: ClassVar[Dict[str, Any]] = {
        'winidea_setup': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier for the resource pool',
            },
            'device': {
                'type': 'str',
                'required': True,
                'description': "Target device (e.g. 'TC387QP', 'TC397XA')",
            },
            'emulator_type': {
                'type': 'str',
                'required': True,
                'description': "Debug probe type (e.g. 'iC5000', 'iC5500')",
            },
            'com_mode': {
                'type': 'str',
                'required': True,
                'description': "Communication mode (e.g. 'USB', 'ETH')",
            },
            'winidea_dir': {
                'type': 'str',
                'required': True,
                'description': 'Path to winIDEA installation directory',
            },
            'workspace_dir': {
                'type': 'str',
                'required': False,
                'description': 'Path to winIDEA workspace directory (creates new workspace). Ignored when workspace_file is set.',
            },
            'workspace_file': {
                'type': 'str',
                'required': False,
                'description': 'Path to existing .xjrf workspace file. When set, opens the workspace as-is instead of creating one from scratch.',
            },
            'sym_path': {
                'type': 'str',
                'required': False,
                'description': 'ELF symbol file path (optional)',
            },
            'headless': {
                'type': 'bool',
                'required': False,
                'description': 'Run winIDEA in headless mode (default: false). Auto-forced to true in CI pipelines.',
            },
            'keep_open': {
                'type': 'bool',
                'required': False,
                'description': 'Keep winIDEA open when resources are released (default: false)',
            },
            'connect_timeout': {
                'type': 'int',
                'required': False,
                'description': 'Connection timeout in milliseconds (default: SDK default). Increase for GUI mode startup.',
            },
            'watch_conf': {
                'type': 'str',
                'required': False,
                'description': 'Path to external YAML watch configuration file (auto-resolved by ConfigLoader). Keys become Watch window tab names, values define expressions.',
            },
            'cores': {
                'type': 'dict',
                'required': False,
                'description': 'Multi-core config: dict of core indices to per-core settings (watch_conf, workspace_file). Uses instance_attach() to open per-core debug windows.',
            },
            'default_core': {
                'type': 'str',
                'required': False,
                'description': 'The core used for flash/configure. Default: first key in cores dict.',
            },
            'cores_to_debug': {
                'type': 'str',
                'required': False,
                'description': "Comma-separated list of core indices to debug (e.g. '0,1,2'). Watch configs from all listed cores are merged into the workspace.",
            },
        },
        'winidea_flash_pflash': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'hex_file': {
                'type': 'str',
                'required': True,
                'description': 'HEX file path for PFLASH programming',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Run program_verify after programming (default: true). Disable if get_status crashes.',
            },
        },
        'winidea_flash_dflash': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'hex_file': {
                'type': 'str',
                'required': True,
                'description': 'HEX file path for DFLASH programming',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Run program_verify after programming (default: true). Disable if get_status crashes.',
            },
        },
        'winidea_flash_ucb': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'hex_file': {
                'type': 'str',
                'required': True,
                'description': 'HEX file path for UCB programming',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Run program_verify after programming (default: true). Disable if get_status crashes.',
            },
        },
        'winidea_flash_all': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'hex_file': {
                'type': 'str',
                'required': True,
                'description': 'Merged HEX file path containing PFLASH, DFLASH, and UCB data',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Run program_verify after programming (default: true). Disable if get_status crashes.',
            },
        },
        'winidea_flash_pflash_dflash': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'hex_file': {
                'type': 'str',
                'required': True,
                'description': 'HEX file path containing PFLASH and DFLASH data (UCB skipped)',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Run program_verify after programming (default: true). Disable if get_status crashes.',
            },
        },
        'winidea_load_symbols': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'elf_file': {
                'type': 'str',
                'required': True,
                'description': 'ELF file path to load as symbols on all cores',
            },
            'source_remap': {
                'type': 'str',
                'required': False,
                'description': "Source path remapping rules (semicolon-separated old=new pairs, e.g. 'C:/build=D:/src;/tmp=/local')",
            },
        },
        'winidea_reset': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
        },
        'winidea_close': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
        },
        'winidea_configure_session': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'program_files': {
                'type': 'list',
                'required': False,
                'description': 'List of HEX/ELF file paths to set as program files on the SoC',
            },
            'symbol_files': {
                'type': 'dict',
                'required': False,
                'description': 'Dict mapping application names to ELF symbol file paths (e.g. {app0: path/to/app.elf})',
            },
            'verify': {
                'type': 'bool',
                'required': False,
                'description': 'Enable program_verify for subsequent flash operations (default: true)',
            },
            'source_remap': {
                'type': 'str',
                'required': False,
                'description': 'Source path remapping rules (semicolon-separated old=new pairs)',
            },
            'preset_pc': {
                'type': 'dict',
                'required': False,
                'description': "PC preset config dict with keys 'mode' (none|entry_point|address) and optional 'symbol' (address/symbol name)",
            },
            'use_sym_for_pgm': {
                'type': 'bool',
                'required': False,
                'description': 'Use symbol file also as program file (default: not set)',
            },
            'session_actions': {
                'type': 'list',
                'required': False,
                'description': 'Ordered list of session actions to execute (reset, attach, prepare, program, end, run, stop)',
            },
            'watch': {
                'type': 'dict',
                'required': False,
                'description': 'Inline watch config: dict of group names to {expressions: [...], watch_window: int, partition: str}',
            },
            'watch_conf': {
                'type': 'str',
                'required': False,
                'description': "Path to external YAML watch configuration file (auto-resolved by ConfigLoader). Takes precedence over inline 'watch'.",
            },
        },
        'winidea_read_variables': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'expressions': {
                'type': 'list',
                'required': True,
                'description': 'List of C-syntax expressions or variable names to evaluate on the target',
            },
            'core': {
                'type': 'int',
                'required': False,
                'description': 'Core index to focus before reading (0=CPU0, 1=CPU1, etc.). If omitted, uses current focused core.',
            },
        },
        'winidea_check_counters': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'counters': {
                'type': 'list',
                'required': True,
                'description': 'List of counter variable names to monitor (must be numeric)',
            },
            'interval': {
                'type': 'float',
                'required': False,
                'description': 'Seconds between reads (default: 1.0)',
            },
            'nr_of_repetitions': {
                'type': 'int',
                'required': False,
                'description': 'Number of read cycles (default: 3). Each cycle verifies counters increased.',
            },
            'core': {
                'type': 'int',
                'required': False,
                'description': 'Core index to focus before reading (0=CPU0, 1=CPU1, etc.). If omitted, uses current focused core.',
            },
        },
        'winidea_verify_variables': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
            'variables': {
                'type': 'dict',
                'required': True,
                'description': 'Dict mapping variable/expression names to their expected values (e.g. {var_name: expected_value})',
            },
            'core': {
                'type': 'int',
                'required': False,
                'description': 'Core index to focus before reading (0=CPU0, 1=CPU1, etc.). If omitted, uses current focused core.',
            },
        },
        'winidea_get_cpu_status': {
            'WINIDEA_ID': {
                'type': 'str',
                'required': True,
                'description': 'WinIDEA instance identifier',
            },
        },
    }

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

        step_type = self.config.get('step_type') or self.config.get('type', '')
        if step_type == 'winidea_setup':
            self.game_stopper = True

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured WinIDEA step."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type') or self.config.get('type', '')
            params = self.config.get('params', {})

            if step_type == 'winidea_setup':
                self._winidea_setup(params)
            elif step_type == 'winidea_configure_session':
                self._winidea_configure_session(params)
            elif step_type == 'winidea_flash_pflash':
                self._winidea_flash_pflash(params)
            elif step_type == 'winidea_flash_dflash':
                self._winidea_flash_dflash(params)
            elif step_type == 'winidea_flash_ucb':
                self._winidea_flash_ucb(params)
            elif step_type == 'winidea_flash_all':
                self._winidea_flash_all(params)
            elif step_type == 'winidea_flash_pflash_dflash':
                self._winidea_flash_pflash_dflash(params)
            elif step_type == 'winidea_load_symbols':
                self._winidea_load_symbols(params)
            elif step_type == 'winidea_read_variables':
                self._winidea_read_variables(params)
            elif step_type == 'winidea_check_counters':
                self._winidea_check_counters(params)
            elif step_type == 'winidea_verify_variables':
                self._winidea_verify_variables(params)
            elif step_type == 'winidea_get_cpu_status':
                self._winidea_get_cpu_status(params)
            elif step_type == 'winidea_reset':
                self._winidea_reset(params)
            elif step_type == 'winidea_close':
                self._winidea_close(params)
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

    def _winidea_setup(self, params: Dict[str, Any]) -> None:
        """Set up the WinIDEA environment.

        Creates a ``WinIdeaTC3xxApi`` instance, connects to winIDEA,
        discovers TC3xx devices, and stores the handle in
        ``self.resources["winideas"]`` keyed by ``WINIDEA_ID``.

        When ``cores`` dict is specified, spawns a separate winIDEA
        instance per core with ID ``{WINIDEA_ID}_{core_name}``.  Each
        core entry can override ``workspace_file`` and ``watch_conf``.
        """
        from xc_ce_utils.winidea.winidea_tc3xx_api import WinIdeaTC3xxApi  # noqa: PLC0415

        cores = params.get('cores')
        if cores and isinstance(cores, dict):
            self._winidea_setup_multicore(params, cores)
            return

        try:
            winidea_id = params['WINIDEA_ID']

            if winidea_id in self.resources['winideas']:
                logger.warning(
                    f'[{self.name}] WinIDEA with id {winidea_id} already '
                    f'set-up. Using existing instance.'
                )
                self.add_to_report = False
                return

            workspace_file = params.get('workspace_file', '')

            # Patch .xgrf to inject named Watch windows before loading
            watch_conf = params.get('watch_conf')
            if watch_conf and isinstance(watch_conf, dict) and workspace_file:
                watch_windows = list(watch_conf.keys())
                self._patch_xgrf_watch_windows(workspace_file, watch_windows, watch_conf)

            winidea = WinIdeaTC3xxApi(
                device=params['device'],
                emulator_type=params['emulator_type'],
                com_mode=params['com_mode'],
                winidea_dir=params['winidea_dir'],
                workspace_dir=params.get('workspace_dir', ''),
                workspace_file=workspace_file,
                log_file=str(self.log_folder / f'{self.name}.log'),
                sym_path=params.get('sym_path'),
            )

            headless = params.get('headless', False)
            if is_running_in_ci():
                headless = True
                logger.info(f'[{self.name}] CI pipeline detected â€” forcing headless mode')

            winidea.connect(
                headless=headless,
                connect_timeout=params.get('connect_timeout', 0),
            )
            winidea.discover_devices()

            winidea.keep_open = params.get('keep_open', False)
            self.resources['winideas'][winidea_id] = winidea

            self.result_string.append(f'WinIDEA {winidea_id} set up successfully')
        except Exception as e:
            message = f"WinIDEA '{params.get('WINIDEA_ID', '?')}' setup failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] WinIDEA {winidea_id} set up')

    def _winidea_setup_multicore(self, params: Dict[str, Any], cores: Dict[str, Any]) -> None:
        """Set up winIDEA for multi-core debugging via instance_attach.

        Opens ONE winIDEA instance using the ``default_core`` workspace,
        then calls ``CSessionCtrl.instance_attach()`` for each additional
        core.  This opens per-core winIDEA windows (the SDK equivalent of
        Debug â†' Core â†' CPUx).

        Each core's watch config is patched into its own ``.xgrf`` layout
        file before the windows are opened.

        Parameters
        ----------
        params : dict
            Step parameters including ``WINIDEA_ID``, ``default_core``,
            ``cores_to_debug``, device/emulator settings, etc.
        cores : dict
            Core definitions: ``{core_index: {watch_conf, workspace_file}}``.
        """
        from xc_ce_utils.winidea.winidea_tc3xx_api import WinIdeaTC3xxApi  # noqa: PLC0415

        base_id = params['WINIDEA_ID']
        headless = params.get('headless', False)
        if is_running_in_ci():
            headless = True
            logger.info(f'[{self.name}] CI pipeline detected â€” forcing headless mode')

        # Convert cores keys to strings for consistent comparison
        cores_str = {str(k): v for k, v in cores.items()}
        default_core = str(params.get('default_core', next(iter(cores_str))))

        if default_core not in cores_str:
            raise ExecutionStepError(
                f"[{self.name}] default_core '{default_core}' not found in "
                f'cores dict (available: {list(cores_str.keys())})',
                phase=self.name,
            )

        # Parse cores_to_debug (comma-separated string â†' set of core names)
        cores_to_debug_raw = params.get('cores_to_debug', '')
        if cores_to_debug_raw:
            cores_to_debug = [s.strip() for s in str(cores_to_debug_raw).split(',') if s.strip()]
        else:
            # If not specified, debug all cores
            cores_to_debug = list(cores_str.keys())

        # Ensure default_core is always included
        if default_core not in cores_to_debug:
            cores_to_debug.insert(0, default_core)

        # Use the top-level workspace file (opens the main instance)
        workspace_file = params.get('workspace_file', '')
        if not workspace_file:
            workspace_file = cores_str[default_core].get('workspace_file', '')

        # Patch each core's own .xgrf with its watch config
        for core_name in cores_to_debug:
            if core_name not in cores_str:
                logger.warning(
                    f"[{self.name}] Core '{core_name}' in cores_to_debug "
                    f'but not in cores dict â€” skipping watch config'
                )
                continue
            core_ws = cores_str[core_name].get('workspace_file', workspace_file)
            if not core_ws:
                continue
            watch_conf = cores_str[core_name].get('watch_conf', params.get('watch_conf'))
            if watch_conf and isinstance(watch_conf, dict):
                watch_windows = list(watch_conf.keys())
                self._patch_xgrf_watch_windows(core_ws, watch_windows, watch_conf)

        try:
            winidea = WinIdeaTC3xxApi(
                device=params['device'],
                emulator_type=params['emulator_type'],
                com_mode=params['com_mode'],
                winidea_dir=params['winidea_dir'],
                workspace_dir=params.get('workspace_dir', ''),
                workspace_file=workspace_file,
                log_file=str(self.log_folder / f'{self.name}.log'),
                sym_path=params.get('sym_path'),
            )

            winidea.connect(
                headless=headless,
                connect_timeout=params.get('connect_timeout', 0),
            )
            winidea.discover_devices()
            winidea.keep_open = params.get('keep_open', False)

            # Clear stale symbol/program files from the workspace before
            # begin_attach() â€” the .xjrf may contain paths from a different
            # machine.  The correct files are set later by configure_session.
            winidea.configure_session()
            ic = winidea._ic
            cfg_ctrl = ic.CConfigurationController(winidea._conn_mgr)

            # Clear program files on SoC level
            winidea._soc_opt.program_files().clear()
            logger.debug(f'[{self.name}] Cleared SoC program files')

            # Clear symbol files for every application
            apps_opt = cfg_ctrl.ide_apps()
            for i in range(apps_opt.size()):
                app_name = apps_opt.at(i).get('Name')
                app_cfg = cfg_ctrl.ide_app(app_name)
                app_cfg.symbol_files().clear()
                logger.debug(f"[{self.name}] Cleared symbol files for app '{app_name}'")

            # Register under base WINIDEA_ID
            self.resources['winideas'][base_id] = winidea

            # Store cores_to_debug metadata â€” actual instance_attach
            # happens later in configure_session (after session run),
            # because flashing disconnects additional cores.
            if 'winidea_cores' not in self.resources:
                self.resources['winidea_cores'] = {}
            self.resources['winidea_cores'][base_id] = {
                'default_core': default_core,
                'cores_to_debug': cores_to_debug,
                'cores_config': cores_str,
                'core_connections': {},
                'core_name_map': {},
                'session_ctrl': None,
                'attached': False,
            }

            self.result_string.append(
                f"WinIDEA '{base_id}' ready (default_core={default_core}, "
                f'cores_to_debug={cores_to_debug}, '
                f'attach_pending=True)'
            )
        except Exception as e:
            message = f"WinIDEA multi-core setup failed for '{base_id}': {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(
            f"[{self.name}] WinIDEA '{base_id}' set up â€” "
            f'cores: {cores_to_debug}, '
            f'attach_pending=True (will attach after session run)'
        )

    def _attach_additional_cores(
        self, winidea, winidea_id: str, cores_meta: Dict[str, Any]
    ) -> None:
        """Attach additional core windows via instance_attach.

        Called from configure_session after session_actions includes 'run',
        ensuring the target is alive and all cores are running before
        attaching debug windows to non-default cores.
        """
        ic = winidea._ic
        default_core = cores_meta['default_core']
        cores_to_debug = cores_meta['cores_to_debug']

        session_ctrl = ic.CSessionCtrl(winidea._conn_mgr)
        session_ctrl.begin_attach()

        # Build core index -> topology name mapping
        topo = session_ctrl.get_topology()
        topo_cores = topo.SoCs()[0].cores()
        core_name_map: Dict[str, str] = {}
        for i in range(topo_cores.size()):
            core_name_map[str(i)] = topo_cores[i].name()

        logger.info(f'[{self.name}] Topology cores: {core_name_map}')

        # Attach non-default cores
        core_connections: Dict[str, Any] = {}
        for core_idx in cores_to_debug:
            if core_idx == default_core:
                continue
            topo_name = core_name_map.get(core_idx)
            if not topo_name:
                logger.warning(
                    f"[{self.name}] Core '{core_idx}' not found in "
                    f'topology â€” skipping instance_attach'
                )
                continue
            logger.info(
                f'[{self.name}] Attaching to core window: ' f'{topo_name} (index {core_idx})...'
            )
            core_conn = session_ctrl.instance_attach(topo_name)
            if core_conn.isAttached():
                core_connections[core_idx] = core_conn
                logger.info(f"[{self.name}] Core '{topo_name}' window opened")
            else:
                logger.warning(
                    f"[{self.name}] instance_attach('{topo_name}') "
                    f'returned but isAttached()=False'
                )

        # Update the resource metadata
        cores_meta['core_connections'] = core_connections
        cores_meta['core_name_map'] = core_name_map
        cores_meta['session_ctrl'] = session_ctrl
        cores_meta['attached'] = True

        logger.info(
            f"[{self.name}] Multi-core attach complete for '{winidea_id}': "
            f'attached_cores={list(core_connections.keys())}'
        )

    def _set_focused_core(self, winidea, core_idx: int) -> None:
        """Switch the focused core for variable reads.

        If multi-core connections were established via ``instance_attach``,
        this switches the winIDEA API's internal ``_conn_mgr`` to the
        per-core connection.  For the default core, the original
        connection is restored.

        Falls back to ``SMP_set_focused_core()`` when no per-core
        connections are available (single-core setup).

        Parameters
        ----------
        winidea : WinIdeaApi
            The connected winIDEA instance.
        core_idx : int
            Zero-based core index (0=CPU0, 1=CPU1, etc.).
        """
        # Find the per-core connection from the resource pool
        base_id = None
        for wid, wi in self.resources.get('winideas', {}).items():
            if wi is winidea:
                base_id = wid
                break

        cores_data = self.resources.get('winidea_cores', {}).get(base_id)
        if cores_data and 'core_connections' in cores_data:
            core_key = str(core_idx)
            default_core = cores_data['default_core']

            if core_key == default_core:
                # Restore original connection for default core
                if hasattr(winidea, '_original_conn_mgr'):
                    winidea._conn_mgr = winidea._original_conn_mgr
                logger.info(f'[{self.name}] Using main connection (core {core_idx})')
            elif core_key in cores_data['core_connections']:
                # Switch to per-core connection
                if not hasattr(winidea, '_original_conn_mgr'):
                    winidea._original_conn_mgr = winidea._conn_mgr
                winidea._conn_mgr = cores_data['core_connections'][core_key]
                logger.info(f'[{self.name}] Switched to core {core_idx} connection')
            else:
                logger.warning(
                    f'[{self.name}] Core {core_idx} has no attached connection '
                    f'â€” falling back to SMP_set_focused_core()'
                )
                winidea.set_focused_core(core_idx)
        else:
            # Fallback: no multi-core setup, use SMP_set_focused_core
            winidea.set_focused_core(core_idx)

    @staticmethod
    def _count_watch_expressions(group: Dict[str, Any]) -> int:
        """Count total expressions in a watch group (supports both formats)."""
        if 'expressions' in group:
            return len(group['expressions'])
        # New format: keys are partition names, values are expression lists
        return sum(len(v) for v in group.values() if isinstance(v, list))

    def _build_variables_xml(
        self,
        watch_conf: Dict[str, Any],
        name: str,
        indent: str = '          ',
    ) -> str:
        """Build the <Variables> XML block for a Watch window entry.

        Supports two YAML formats:

        Old format (expressions key)::

            group_name:
              expressions:
                - var_name: Partition
                - var_name2

        New format (partition-grouped)::

            group_name:
              Partition/Name:
                - var_name
                - var_name2

        Parameters
        ----------
        watch_conf : dict
            Watch configuration dict with group names as keys.
        name : str
            The watch window name (key in watch_conf).
        indent : str
            Base indentation for the XML elements.

        Returns
        -------
        str
            XML fragment for the <Variables> element, or empty string.
        """
        if name not in watch_conf:
            return ''
        group = watch_conf[name]

        # Flatten to list of (expression, partition) tuples
        flat: List[tuple] = []
        if 'expressions' in group:
            # Old format: expressions is a list of dicts or strings
            for item in group['expressions']:
                if isinstance(item, dict):
                    expr = next(iter(item.keys()))
                    partition = next(iter(item.values()))
                else:
                    expr = item
                    partition = ''
                flat.append((expr, partition))
        else:
            # New format: keys are partition names, values are expression lists
            for partition_name, expr_list in group.items():
                if isinstance(expr_list, list):
                    for expr in expr_list:
                        flat.append((str(expr), str(partition_name)))

        if not flat:
            return ''

        lines = [f'{indent}<Variables>']
        for idx, (expr, partition) in enumerate(flat):
            full_name = f'{expr},,,{partition}' if partition else expr
            lines.append(f'{indent} <__.{idx}>')
            lines.append(f'{indent}  <Name>{full_name}</Name>')
            lines.append(f'{indent}  <ExpressionDisplay>')
            lines.append(f'{indent}   <Color>false</Color>')
            lines.append(f'{indent}   <ColorBack>16777215</ColorBack>')
            lines.append(f'{indent}   <ColorText>0</ColorText>')
            lines.append(f'{indent}   <Enabled>false</Enabled>')
            lines.append(f'{indent}   <Hi>0</Hi>')
            lines.append(f'{indent}   <Lo>0</Lo>')
            lines.append(f'{indent}   <Scale>Linear</Scale>')
            lines.append(f'{indent}  </ExpressionDisplay>')
            lines.append(f'{indent} </__.{idx}>')
        lines.append(f'{indent}</Variables>')
        return '\n'.join(lines)

    def _patch_xgrf_watch_windows(
        self,
        workspace_file: str,
        watch_windows: List[str],
        watch_conf: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Patch the .xgrf layout file to add named Watch window tabs.

        The .xgrf file (same base name as .xjrf, same directory) stores
        the winIDEA GUI layout including Watch window definitions under
        ``<WatchViews>``.  This method injects new named Watch entries
        with inline ``<Variables>`` so winIDEA loads the expressions
        when the workspace is opened.

        Parameters
        ----------
        workspace_file : str
            Path to the .xjrf workspace file (used to derive .xgrf path).
        watch_windows : list of str
            Names for the Watch window tabs to create.
        watch_conf : dict, optional
            Watch configuration dict (from YAML). Keys are group names
            matching ``watch_windows`` entries; values have
            ``{"expressions": [{expr: partition}, ...]}``.
        """
        import re

        xgrf_path = Path(workspace_file).with_suffix('.xgrf')
        if not xgrf_path.is_file():
            logger.warning(
                f'[{self.name}] .xgrf file not found: {xgrf_path} â€” '
                f'cannot inject Watch windows'
            )
            return

        content = xgrf_path.read_text(encoding='utf-8')

        # Find existing WatchViews section
        match = re.search(r'(<WatchViews>)(.*?)(</WatchViews>)', content, re.DOTALL)
        if not match:
            # Create an empty <WatchViews> section after </AllViewBaseData>
            avbd_close = content.find('</AllViewBaseData>')
            if avbd_close == -1:
                logger.warning(
                    f'[{self.name}] No <WatchViews> or <AllViewBaseData> in '
                    f'{xgrf_path.name} â€” cannot inject Watch windows'
                )
                return
            insert_pos = avbd_close + len('</AllViewBaseData>')
            content = (
                content[:insert_pos]
                + '\n      <WatchViews>\n      </WatchViews>'
                + content[insert_pos:]
            )
            match = re.search(r'(<WatchViews>)(.*?)(</WatchViews>)', content, re.DOTALL)
            logger.info(f'[{self.name}] Created empty <WatchViews> section in ' f'{xgrf_path.name}')

        watch_section = match.group(2)

        # Determine next index: count existing <__.N> entries
        existing_indices = re.findall(r'<__\.(\d+)>', watch_section)
        next_idx = max((int(i) for i in existing_indices), default=-1) + 1

        # Determine next ViewId (must be unique globally in the file)
        all_file_view_ids = re.findall(r'<ViewId>(\d+)</ViewId>', content)
        next_view_id = max((int(v) for v in all_file_view_ids), default=0) + 1

        # Collect existing Watch window names to avoid duplicates
        existing_names = re.findall(r'<Name>(.*?)</Name>', watch_section)

        # Track ViewIds that need visibility registration
        # (AllViewBaseData + docking panel)
        all_view_ids: List[int] = []

        # For existing windows: fix ViewId=-1 and replace <VariableData>
        modified = False
        for name in watch_windows:
            if name in existing_names:
                # Fix ViewId=-1 if present for this window (always, even
                # without variable expressions â€” needed for docking)
                viewid_pattern = (
                    r'(<Name>' + re.escape(name) + r'</Name>\s*)' r'(<ViewId>)-1(</ViewId>)'
                )
                viewid_repl = rf'\g<1>\g<2>{next_view_id}\g<3>'
                new_content = re.sub(
                    viewid_pattern,
                    viewid_repl,
                    content,
                    count=1,
                    flags=re.DOTALL,
                )
                if new_content != content:
                    content = new_content
                    all_view_ids.append(next_view_id)
                    next_view_id += 1
                    logger.info(
                        f"[{self.name}] Fixed ViewId for '{name}' "
                        f'(was -1, now {next_view_id - 1})'
                    )
                else:
                    # Already has a valid ViewId â€” extract it
                    vid_match = re.search(
                        r'<Name>' + re.escape(name) + r'</Name>\s*' r'<ViewId>(\d+)</ViewId>',
                        content,
                    )
                    if vid_match:
                        all_view_ids.append(int(vid_match.group(1)))

                # Replace the <VariableData> block if we have expressions
                if watch_conf and name in watch_conf:
                    variables_xml = self._build_variables_xml(watch_conf, name)
                    if variables_xml:
                        pattern = (
                            r'(<Name>' + re.escape(name) + r'</Name>.*?)'
                            r'(<VariableData>.*?</VariableData>)'
                        )
                        replacement_block = (
                            '<VariableData>\n'
                            '          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
                            f'{variables_xml}\n'
                            '         </VariableData>'
                        )

                        def _replace_vardata(m):
                            return m.group(1) + replacement_block

                        new_content = re.sub(
                            pattern,
                            _replace_vardata,
                            content,
                            count=1,
                            flags=re.DOTALL,
                        )
                        if new_content != content:
                            content = new_content
                            modified = True
                            n_expr = self._count_watch_expressions(watch_conf[name])
                            logger.info(
                                f'[{self.name}] Updated Variables for existing '
                                f"Watch window '{name}' ({n_expr} expressions)"
                            )

        # Build XML entries for new Watch windows only
        new_entries = []
        for name in watch_windows:
            if name in existing_names:
                continue

            # Build the VariableData block with inline expressions
            var_data_block = (
                '         <VariableData>\n'
                '          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
            )
            if watch_conf and name in watch_conf:
                v_xml = self._build_variables_xml(watch_conf, name)
                if v_xml:
                    var_data_block += f'{v_xml}\n'
            var_data_block += '         </VariableData>\n'

            entry = (
                f'       <__.{next_idx}>\n'
                f'        <Name>{name}</Name>\n'
                f'        <ViewId>{next_view_id}</ViewId>\n'
                f'        <ViewType>CustomWatch</ViewType>\n'
                f'        <ColumnData>\n'
                f'         <__.0>\n'
                f'          <Pos>0</Pos>\n'
                f'          <Visible>true</Visible>\n'
                f'          <Width>300</Width>\n'
                f'         </__.0>\n'
                f'         <__.1>\n'
                f'          <Pos>25</Pos>\n'
                f'          <Visible>true</Visible>\n'
                f'          <Width>300</Width>\n'
                f'         </__.1>\n'
                f'         <__.2>\n'
                f'          <Pos>50</Pos>\n'
                f'          <Visible>true</Visible>\n'
                f'          <Width>100</Width>\n'
                f'         </__.2>\n'
                f'         <__.3>\n'
                f'          <Pos>75</Pos>\n'
                f'          <Visible>true</Visible>\n'
                f'          <Width>100</Width>\n'
                f'         </__.3>\n'
                f'         <__.4>\n'
                f'          <Pos>100</Pos>\n'
                f'          <Visible>true</Visible>\n'
                f'          <Width>50</Width>\n'
                f'         </__.4>\n'
                f'        </ColumnData>\n'
                f'        <WatchData>\n'
                f'         <MiscData>\n'
                f'          <InitScript></InitScript>\n'
                f'         </MiscData>\n'
                f'         <PaneMiscData.0>\n'
                f'          <InitScript></InitScript>\n'
                f'         </PaneMiscData.0>\n'
                f'         <PaneMiscData.1>\n'
                f'          <InitScript></InitScript>\n'
                f'         </PaneMiscData.1>\n'
                f'         <PaneMiscData.2>\n'
                f'          <InitScript></InitScript>\n'
                f'         </PaneMiscData.2>\n'
                f'         <PaneMiscData.3>\n'
                f'          <InitScript></InitScript>\n'
                f'         </PaneMiscData.3>\n'
                f'{var_data_block}'
                f'         <WatchPaneData.0>\n'
                f'          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
                f'         </WatchPaneData.0>\n'
                f'         <WatchPaneData.1>\n'
                f'          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
                f'         </WatchPaneData.1>\n'
                f'         <WatchPaneData.2>\n'
                f'          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
                f'         </WatchPaneData.2>\n'
                f'         <WatchPaneData.3>\n'
                f'          <IsRealTimeEnabled>true</IsRealTimeEnabled>\n'
                f'         </WatchPaneData.3>\n'
                f'        </WatchData>\n'
                f'       </__.{next_idx}>\n'
            )
            new_entries.append(entry)
            all_view_ids.append(next_view_id)
            next_idx += 1
            next_view_id += 1

        if new_entries:
            # Re-find match position in potentially modified content
            match = re.search(r'(<WatchViews>)(.*?)(</WatchViews>)', content, re.DOTALL)
            insert_text = ''.join(new_entries)
            content = content[: match.end(2)] + insert_text + content[match.end(2) :]
            modified = True

        # Register all ViewIds in AllViewBaseData and docking panel
        if all_view_ids:
            content = self._register_view_visibility(content, all_view_ids)

            # Set focus to the first yaml-added watch view
            content = re.sub(
                r'<FocusedViewId>\d+</FocusedViewId>',
                f'<FocusedViewId>{all_view_ids[0]}</FocusedViewId>',
                content,
                count=1,
            )

        if modified or all_view_ids:
            xgrf_path.write_text(content, encoding='utf-8')
            added = [n for n in watch_windows if n not in existing_names]
            updated = [n for n in watch_windows if n in existing_names]
            parts = []
            if added:
                parts.append(f'added={added}')
            if updated:
                parts.append(f'updated={updated}')
            logger.info(f"[{self.name}] Patched {xgrf_path.name}: {', '.join(parts)}")

    def _register_view_visibility(
        self,
        content: str,
        view_ids: List[int],
    ) -> str:
        """Register ViewIds in AllViewBaseData and the docking panel.

        This makes the Watch windows actually visible as tabs in winIDEA.

        Parameters
        ----------
        content : str
            The full .xgrf file content.
        view_ids : list of int
            ViewIds to register.

        Returns
        -------
        str
            Modified content with views registered.
        """
        import re

        # 1. Register in <AllViewBaseData>
        avbd_match = re.search(r'(<AllViewBaseData>)(.*?)(</AllViewBaseData>)', content, re.DOTALL)
        if avbd_match:
            avbd_section = avbd_match.group(2)
            existing_avbd_ids = re.findall(r'<__\.(\d+)>', avbd_section)
            avbd_next_idx = max((int(i) for i in existing_avbd_ids), default=-1) + 1

            avbd_entries = ''
            for vid in view_ids:
                # Skip if already registered
                if f'<ViewId>{vid}</ViewId>' in avbd_section:
                    continue
                avbd_entries += (
                    f'       <__.{avbd_next_idx}>\n'
                    f'        <ViewId>{vid}</ViewId>\n'
                    f'        <ViewType>CustomWatch</ViewType>\n'
                    f'       </__.{avbd_next_idx}>\n'
                )
                avbd_next_idx += 1

            if avbd_entries:
                content = content[: avbd_match.end(2)] + avbd_entries + content[avbd_match.end(2) :]
                logger.debug(f'[{self.name}] Registered ViewIds {view_ids} ' f'in AllViewBaseData')

        # 2. Add to docking panel so the views are visible as tabs
        # Strategy: find a tabbed panel that already contains one of our
        # ViewIds or any CustomWatch view. If none exists, create a new
        # tabbed panel in the top-right area of the layout.
        dock_pattern = (
            r'(<IsTabbed>true</IsTabbed>\s*'
            r'<Orientation>None</Orientation>\s*'
            r'<TopTabViewId>)(\d+)(</TopTabViewId>\s*'
            r'<ViewId>-1</ViewId>\s*'
            r'<Children>)'
            r'(.*?)'
            r'(</Children>)'
        )
        dock_matches = list(re.finditer(dock_pattern, content, re.DOTALL))

        # Look for a panel that already contains one of our view IDs
        target_match = None
        for dm in dock_matches:
            children_section = dm.group(4)
            for vid in view_ids:
                if f'<ViewId>{vid}</ViewId>' in children_section:
                    target_match = dm
                    break
            if target_match:
                break

        # Fallback: look for any panel containing a known Watch ViewId
        if not target_match:
            watch_vid_pattern = re.findall(
                r'<ViewId>(\d+)</ViewId>\s*<ViewType>CustomWatch</ViewType>',
                content,
            )
            watch_vids = {int(v) for v in watch_vid_pattern}
            for dm in dock_matches:
                children_section = dm.group(4)
                for wv in watch_vids:
                    if f'<ViewId>{wv}</ViewId>' in children_section:
                        target_match = dm
                        break
                if target_match:
                    break

        if target_match:
            # Add to existing Watch panel â€” insert NEW views BEFORE existing
            # children so yaml-configured watches appear first as tabs.
            children_section = target_match.group(4)

            # Collect new ViewIds that aren't already in the panel
            new_vids = [
                vid for vid in view_ids if f'<ViewId>{vid}</ViewId>' not in children_section
            ]

            if new_vids:
                # Extract existing child entries to re-index after prepending
                child_entry_pattern = re.compile(r'<__\.\d+>(.*?)</(__\.\d+)>', re.DOTALL)
                existing_entries = child_entry_pattern.findall(children_section)

                # Build combined children: new views first, then existing
                idx = 0
                combined_children = ''
                for vid in new_vids:
                    combined_children += (
                        f'              <__.{idx}>\n'
                        f'               <DockType>View</DockType>\n'
                        f'               <Extent>1</Extent>\n'
                        f'               <IsDocumentPane>false</IsDocumentPane>\n'
                        f'               <IsPinned>false</IsPinned>\n'
                        f'               <IsPrimaryDocumentPane>false</IsPrimaryDocumentPane>\n'
                        f'               <IsTabbed>false</IsTabbed>\n'
                        f'               <Orientation>None</Orientation>\n'
                        f'               <TopTabViewId>-1</TopTabViewId>\n'
                        f'               <ViewId>{vid}</ViewId>\n'
                        f'              </__.{idx}>\n'
                    )
                    idx += 1
                for entry_body, _ in existing_entries:
                    combined_children += f'              <__.{idx}>{entry_body}</__.{idx}>\n'
                    idx += 1

                # Replace children section
                content = (
                    content[: target_match.start(4)]
                    + combined_children
                    + content[target_match.end(4) :]
                )
                logger.debug(
                    f'[{self.name}] Added ViewIds {new_vids} to '
                    f'existing Watch panel (prepended before existing)'
                )

            # Always update TopTabViewId to the first yaml-configured view
            old_top_id = target_match.group(2)
            if str(view_ids[0]) != old_top_id:
                content = re.sub(
                    r'(<TopTabViewId>)'
                    + re.escape(old_top_id)
                    + r'(</TopTabViewId>\s*<ViewId>-1</ViewId>\s*<Children>)',
                    rf'\g<1>{view_ids[0]}\g<2>',
                    content,
                    count=1,
                )
        else:
            # No existing Watch panel found â€” create a new tabbed panel
            # Insert as a sibling in the top-level Dock Children (top-right)
            content = self._create_watch_dock_panel(content, view_ids)

        return content

    def _create_watch_dock_panel(
        self,
        content: str,
        view_ids: List[int],
    ) -> str:
        """Create a new docking panel for Watch windows in the layout.

        Finds the top-level Dock Children under ViewLayout and adds
        a new tabbed panel as the last child, adjusting existing sibling
        Extents to make room.
        """
        import re

        # Find the top-level <Dock> under <ViewLayout> â€” it has the
        # root Children with Orientation=Horizontal or Vertical
        root_dock_pattern = (
            r'(<ViewLayout>\s*<Frames>\s*<__.0>.*?<Dock>\s*'
            r'<DockType>None</DockType>\s*'
            r'<Extent>\S+</Extent>\s*'
            r'<IsDocumentPane>false</IsDocumentPane>\s*'
            r'<IsPinned>false</IsPinned>\s*'
            r'<IsPrimaryDocumentPane>false</IsPrimaryDocumentPane>\s*'
            r'<IsTabbed>false</IsTabbed>\s*'
            r'<Orientation>(?:Horizontal|Vertical)</Orientation>\s*'
            r'<TopTabViewId>-1</TopTabViewId>\s*'
            r'<ViewId>-1</ViewId>\s*'
            r'<Children>)'
            r'(.*?)'
            r'(</Children>\s*</Dock>)'
        )
        root_match = re.search(root_dock_pattern, content, re.DOTALL)

        if not root_match:
            logger.warning(
                f'[{self.name}] Could not find root dock panel â€” '
                f'Watch windows may not be visible'
            )
            return content

        children_section = root_match.group(2)
        existing_indices = re.findall(r'<__\.(\d+)>', children_section)
        next_child_idx = max((int(i) for i in existing_indices), default=-1) + 1

        # Shrink existing siblings to make room (reduce each by proportional amount)
        # New panel gets 25% â€” scale existing extents to fit in remaining 75%
        new_panel_extent = 0.25
        scale_factor = 1.0 - new_panel_extent

        # Only scale the Extent of direct children (the <__.N> entries at
        # the first level). Each direct child starts with DockType/Extent
        # before any nested <Children> block.
        def _scale_direct_child(m):
            prefix = m.group(1)
            old_val = float(m.group(2))
            suffix = m.group(3)
            new_val = old_val * scale_factor
            return f'{prefix}{new_val:.6g}{suffix}'

        # Match <__.N> followed by its DockType line then Extent line
        scaled_section = re.sub(
            r'(<__\.\d+>\s*<DockType>\w+</DockType>\s*<Extent>)([0-9.]+)(</Extent>)',
            _scale_direct_child,
            children_section,
        )

        # Build child entries for each Watch view
        view_children = ''
        for idx, vid in enumerate(view_ids):
            view_children += (
                f'            <__.{idx}>\n'
                f'             <DockType>View</DockType>\n'
                f'             <Extent>1</Extent>\n'
                f'             <IsDocumentPane>false</IsDocumentPane>\n'
                f'             <IsPinned>false</IsPinned>\n'
                f'             <IsPrimaryDocumentPane>false</IsPrimaryDocumentPane>\n'
                f'             <IsTabbed>false</IsTabbed>\n'
                f'             <Orientation>None</Orientation>\n'
                f'             <TopTabViewId>-1</TopTabViewId>\n'
                f'             <ViewId>{vid}</ViewId>\n'
                f'            </__.{idx}>\n'
            )

        # Create a new tabbed panel
        new_panel = (
            f'          <__.{next_child_idx}>\n'
            f'           <DockType>None</DockType>\n'
            f'           <Extent>{new_panel_extent}</Extent>\n'
            f'           <IsDocumentPane>false</IsDocumentPane>\n'
            f'           <IsPinned>false</IsPinned>\n'
            f'           <IsPrimaryDocumentPane>false</IsPrimaryDocumentPane>\n'
            f'           <IsTabbed>true</IsTabbed>\n'
            f'           <Orientation>None</Orientation>\n'
            f'           <TopTabViewId>{view_ids[0]}</TopTabViewId>\n'
            f'           <ViewId>-1</ViewId>\n'
            f'           <Children>\n'
            f'{view_children}'
            f'           </Children>\n'
            f'          </__.{next_child_idx}>\n'
        )

        # Reconstruct: prefix + scaled_children + new_panel + suffix
        content = (
            content[: root_match.start(2)]
            + scaled_section
            + new_panel
            + content[root_match.end(2) :]
        )
        logger.info(f'[{self.name}] Created new Watch dock panel ' f'with ViewIds {view_ids}')
        return content

    def _winidea_flash_pflash(self, params: Dict[str, Any]) -> None:
        """Flash the PFLASH region via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].flash_pflash(
                params['hex_file'], verify=params.get('verify', True)
            )
            self.result_string.append(f"PFLASH flashed: {params['hex_file']}")
        except Exception as e:
            message = f"WinIDEA flash PFLASH failed ({params.get('hex_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] PFLASH flashed: {params['hex_file']}")

    def _winidea_flash_dflash(self, params: Dict[str, Any]) -> None:
        """Flash the DFLASH (FEE) region via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].flash_dflash(
                params['hex_file'], verify=params.get('verify', True)
            )
            self.result_string.append(f"DFLASH flashed: {params['hex_file']}")
        except Exception as e:
            message = f"WinIDEA flash DFLASH failed ({params.get('hex_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] DFLASH flashed: {params['hex_file']}")

    def _winidea_flash_ucb(self, params: Dict[str, Any]) -> None:
        """Flash the UCB (User Configuration Block) via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].flash_ucb(
                params['hex_file'], verify=params.get('verify', True)
            )
            self.result_string.append(f"UCB flashed: {params['hex_file']}")
        except Exception as e:
            message = f"WinIDEA flash UCB failed ({params.get('hex_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] UCB flashed: {params['hex_file']}")

    def _winidea_flash_all(self, params: Dict[str, Any]) -> None:
        """Flash all regions (PFLASH, DFLASH, UCB) from a merged HEX via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].flash_all(
                params['hex_file'], verify=params.get('verify', True)
            )
            self.result_string.append(f"All regions flashed: {params['hex_file']}")
        except Exception as e:
            message = f"WinIDEA flash all failed ({params.get('hex_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] All regions flashed: {params['hex_file']}")

    def _winidea_flash_pflash_dflash(self, params: Dict[str, Any]) -> None:
        """Flash PFLASH + DFLASH regions from a HEX via WinIDEA (no UCB)."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].flash_pflash_dflash(
                params['hex_file'], verify=params.get('verify', True)
            )
            self.result_string.append(f"PFLASH+DFLASH flashed: {params['hex_file']}")
        except Exception as e:
            message = f"WinIDEA flash PFLASH+DFLASH failed ({params.get('hex_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] PFLASH+DFLASH flashed: {params['hex_file']}")

    def _winidea_load_symbols(self, params: Dict[str, Any]) -> None:
        """Load ELF symbols on all cores via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].load_symbols(
                params['elf_file'], source_remap=params.get('source_remap', '')
            )
            self.result_string.append(f"Symbols loaded: {params['elf_file']}")
        except Exception as e:
            message = f"WinIDEA load symbols failed ({params.get('elf_file', '?')}): {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Symbols loaded: {params['elf_file']}")

    def _winidea_reset(self, params: Dict[str, Any]) -> None:
        """Reset the target via WinIDEA."""
        try:
            self.resources['winideas'][params['WINIDEA_ID']].reset_target()
            self.result_string.append('Target reset')
        except Exception as e:
            message = f'WinIDEA reset failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Target reset: {params['WINIDEA_ID']}")

    def _winidea_close(self, params: Dict[str, Any]) -> None:
        """Close the WinIDEA connection and remove it from the resource pool."""
        winidea_id = params['WINIDEA_ID']

        try:
            wi = self.resources['winideas'][winidea_id]

            # Disconnect per-core connections first
            cores_data = self.resources.get('winidea_cores', {}).get(winidea_id)
            if cores_data and 'core_connections' in cores_data:
                for core_key, core_conn in cores_data['core_connections'].items():
                    try:
                        if getattr(wi, 'keep_open', False):
                            core_conn.disconnect_keep()
                        else:
                            core_conn.disconnect_close(False)
                        logger.info(f'[{self.name}] Core {core_key} connection closed')
                    except Exception as e:
                        logger.warning(f'[{self.name}] Error closing core {core_key}: {e}')

            # Restore original connection if it was swapped
            if hasattr(wi, '_original_conn_mgr'):
                wi._conn_mgr = wi._original_conn_mgr

            if getattr(wi, 'keep_open', False):
                logger.info(
                    f"[{self.name}] WinIDEA '{winidea_id}' keep_open is set â€” bringing to front and detaching"
                )
                wi.bring_to_front()
                wi.disconnect_keep()
            else:
                wi.disconnect()
            self.resources['winideas'].pop(winidea_id, None)
            self.resources.get('winidea_cores', {}).pop(winidea_id, None)
            self.result_string.append(f'WinIDEA {winidea_id} closed')
        except Exception as e:
            message = f"Closing WinIDEA '{winidea_id}' failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] WinIDEA closed: {winidea_id}')

    def _winidea_configure_session(self, params: Dict[str, Any]) -> None:
        """Configure the winIDEA session with files, options, and actions."""
        try:
            winidea = self.resources['winideas'][params['WINIDEA_ID']]

            # Expand "all_socs" shorthand: assign the same ELF to every app in the session
            symbol_files = params.get('symbol_files')
            if symbol_files and 'all_socs' in symbol_files:
                elf_path = symbol_files['all_socs']
                ic = winidea._ic
                cfg_ctrl = ic.CConfigurationController(winidea._conn_mgr)
                apps_opt = cfg_ctrl.ide_apps()
                num_apps = apps_opt.size()
                if num_apps == 0:
                    logger.warning(
                        f'[{self.name}] all_socs: No applications found in WinIDEA session'
                    )
                    symbol_files = {}
                else:
                    expanded = {}
                    for i in range(num_apps):
                        app_name = apps_opt.at(i).get('Name')
                        expanded[app_name] = elf_path
                    logger.info(
                        f'[{self.name}] all_socs expanded to {num_apps} apps: '
                        f'{list(expanded.keys())}'
                    )
                    symbol_files = expanded

            # Resolve watch configuration: watch_conf (external file, auto-resolved
            # by ConfigLoader) takes precedence over inline watch dict
            watch = params.get('watch')
            watch_conf = params.get('watch_conf')
            if watch_conf and isinstance(watch_conf, dict):
                watch = watch_conf

            winidea.configure_session_ext(
                program_files=params.get('program_files'),
                symbol_files=symbol_files,
                verify=params.get('verify', True),
                source_remap=params.get('source_remap', ''),
                source_remap_auto=bool(params.get('source_remap_auto', False)),
                preset_pc=params.get('preset_pc'),
                use_sym_for_pgm=params.get('use_sym_for_pgm'),
                session_actions=params.get('session_actions'),
                watch=watch,
            )

            # --- Attach additional cores after session run ---
            session_actions = params.get('session_actions') or []
            winidea_id = params['WINIDEA_ID']
            cores_meta = self.resources.get('winidea_cores', {}).get(winidea_id)
            if 'run' in session_actions and cores_meta and not cores_meta.get('attached'):
                self._attach_additional_cores(winidea, winidea_id, cores_meta)

            parts: List[str] = []
            if params.get('program_files'):
                parts.append(f"program_files={len(params['program_files'])}")
            if symbol_files:
                parts.append(f'symbol_files={list(symbol_files.keys())}')
            if params.get('session_actions'):
                parts.append(f"actions={params['session_actions']}")
            if watch:
                total = sum(self._count_watch_expressions(g) for g in watch.values())
                parts.append(f'watch={len(watch)} group(s), {total} expr(s)')
            summary = ', '.join(parts) if parts else 'no-op'
            self.result_string.append(f'Session configured: {summary}')
        except Exception as e:
            message = f'WinIDEA configure session failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Session configured')

    def _winidea_read_variables(self, params: Dict[str, Any]) -> None:
        """Read variable values from the target via WinIDEA."""
        try:
            winidea = self.resources['winideas'][params['WINIDEA_ID']]
            expressions = params['expressions']

            # Focus specific core if requested
            core = params.get('core')
            if core is not None:
                self._set_focused_core(winidea, int(core))

            logger.info(f'[{self.name}] Reading {len(expressions)} variable(s)...')
            results = winidea.read_variables(expressions)

            for expr, value in results.items():
                self.result_string.append(f'{expr} = {value}')

            errors = [e for e, v in results.items() if v.startswith('<error:')]
            if errors:
                logger.warning(
                    f'[{self.name}] {len(errors)}/{len(expressions)} '
                    f'expression(s) failed: {errors}'
                )
        except Exception as e:
            message = f'WinIDEA read variables failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Read {len(results)} variable(s)')

    def _winidea_check_counters(self, params: Dict[str, Any]) -> None:
        """Verify counter variables are incrementing, proving SW is running.

        Reads the specified counters at each interval and asserts that every
        counter value is strictly greater than the previous read. If any
        counter stalls (does not increase), the test FAILs.

        Produces one TestResult per counter and generates a JUnit XML report.
        """
        import time

        from xc_ce_utils.core_engine.reporting.adapters.exporters import TestResult  # noqa: PLC0415

        winidea = self.resources['winideas'][params['WINIDEA_ID']]
        counters = params['counters']
        interval = float(params.get('interval', 1.0))
        repetitions = int(params.get('nr_of_repetitions', 3))

        # Focus specific core if requested
        core = params.get('core')
        if core is not None:
            self._set_focused_core(winidea, int(core))

        logger.info(
            f'[{self.name}] Checking {len(counters)} counter(s), '
            f'{repetitions} repetitions, {interval}s interval'
        )

        # Initial read
        prev_values = self._read_counter_values(winidea, counters)
        if prev_values is None:
            raise ExecutionStepError(f'[{self.name}] Initial counter read failed', phase=self.name)

        self.result_string.append(f'Initial read: {prev_values}')
        logger.info(f'[{self.name}] Initial: {prev_values}')

        # Track per-counter failures across all repetitions
        counter_failures: Dict[str, List[str]] = {name: [] for name in counters}
        start_time = time.time()

        for rep in range(1, repetitions + 1):
            time.sleep(interval)
            curr_values = self._read_counter_values(winidea, counters)
            if curr_values is None:
                raise ExecutionStepError(
                    f'[{self.name}] Counter read failed at repetition {rep}',
                    phase=self.name,
                )

            logger.info(f'[{self.name}] Read #{rep}: {curr_values}')

            for name in counters:
                prev = prev_values.get(name)
                curr = curr_values.get(name)
                if prev is None or curr is None:
                    counter_failures[name].append(f'read error at rep {rep}')
                elif curr <= prev:
                    counter_failures[name].append(f'stalled at rep {rep}: {prev} -> {curr}')
                    logger.error(
                        f'[{self.name}] FAIL: {name} did not increase: '
                        f'{prev} -> {curr} (rep {rep})'
                    )

            prev_values = curr_values

        total_duration = time.time() - start_time

        # Build TestResult per counter
        for name in counters:
            failures = counter_failures[name]
            if failures:
                self.test_results.append(
                    TestResult(
                        name=name,
                        classname=f'winidea.check_counters.{self.name}',
                        status='failed',
                        duration=total_duration / len(counters),
                        message=f"Counter did not increment: {'; '.join(failures)}",
                        output=f'interval={interval}s, repetitions={repetitions}',
                    )
                )
            else:
                self.test_results.append(
                    TestResult(
                        name=name,
                        classname=f'winidea.check_counters.{self.name}',
                        status='passed',
                        duration=total_duration / len(counters),
                        message='',
                        output=f'Incremented across all {repetitions} repetitions',
                    )
                )

        # Generate JUnit report and set test_status
        self.report_results(
            suite_name=f'check_counters_{self.name}',
            report_filename=f'{self.name}.xml',
            properties={
                'interval': str(interval),
                'nr_of_repetitions': str(repetitions),
                'winidea_id': params['WINIDEA_ID'],
            },
        )

    def _read_counter_values(self, winidea, counters: List[str]) -> 'Dict[str, int] | None':
        """Read counter expressions and parse them as integers."""
        try:
            results = winidea.read_variables(counters)
        except Exception as e:
            logger.error(f'[{self.name}] read_variables failed: {e}')
            return None

        parsed: Dict[str, int] = {}
        for name, val_str in results.items():
            if val_str.startswith('<error:'):
                logger.error(f'[{self.name}] {name}: {val_str}')
                return None
            try:
                # int(x, 0) auto-detects base from prefix (0x, 0o, 0b)
                parsed[name] = int(val_str.strip(), 0)
            except ValueError:
                logger.error(f"[{self.name}] {name} returned non-integer: '{val_str}'")
                return None
        return parsed

    def _winidea_verify_variables(self, params: Dict[str, Any]) -> None:
        """Read variables from target and verify against expected values.

        Produces one TestResult per variable and generates a JUnit XML report.

        Config supports two formats per variable:
          Simple equality:
            variables:
              my_var: 42

          With operator:
            variables:
              my_var:
                operator: ">="
                value: 1
        """
        from xc_ce_utils.core_engine.domain.comparison import (
            evaluate_comparison,
        )
        from xc_ce_utils.core_engine.reporting.adapters.exporters import TestResult  # noqa: PLC0415

        winidea = self.resources['winideas'][params['WINIDEA_ID']]
        variables: Dict[str, Any] = params['variables']

        # Focus specific core if requested
        core = params.get('core')
        if core is not None:
            self._set_focused_core(winidea, int(core))

        expressions = list(variables.keys())
        logger.info(f'[{self.name}] Verifying {len(expressions)} variable(s)...')

        try:
            results = winidea.read_variables(expressions)
        except Exception as e:
            message = f'WinIDEA read variables failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        for expr in expressions:
            actual_str = results.get(expr, '<missing>').strip()
            spec = variables[expr]

            # Parse operator and expected value from config
            if isinstance(spec, dict):
                op = spec.get('operator', '==')
                expected_str = str(spec['value']).strip()
            else:
                op = '=='
                expected_str = str(spec).strip()

            passed = evaluate_comparison(actual_str, expected_str, op)

            if passed:
                self.test_results.append(
                    TestResult(
                        name=expr,
                        classname=f'winidea.verify_variables.{self.name}',
                        status='passed',
                        duration=0.0,
                        message='',
                        output=f'actual={actual_str} {op} expected={expected_str}',
                    )
                )
                self.result_string.append(f'PASS: {expr} = {actual_str} ({op} {expected_str})')
                logger.info(f'  PASS: {expr} = {actual_str} ({op} {expected_str})')
            else:
                self.test_results.append(
                    TestResult(
                        name=expr,
                        classname=f'winidea.verify_variables.{self.name}',
                        status='failed',
                        duration=0.0,
                        message=f'Expected {op} {expected_str}, got {actual_str}',
                        output=f'actual={actual_str} {op} expected={expected_str}',
                    )
                )
                self.result_string.append(
                    f'FAIL: {expr} = {actual_str} (expected {op} {expected_str})'
                )
                logger.error(f'  FAIL: {expr} = {actual_str} (expected {op} {expected_str})')

        # Generate JUnit report and set test_status
        self.report_results(
            suite_name=f'verify_variables_{self.name}',
            report_filename=f'{self.name}.xml',
            properties={'winidea_id': params['WINIDEA_ID']},
        )

    def _winidea_get_cpu_status(self, params: Dict[str, Any]) -> None:
        """Query CPU execution status for all cores via WinIDEA."""
        try:
            winidea = self.resources['winideas'][params['WINIDEA_ID']]

            logger.info(f'[{self.name}] Querying CPU status...')
            results = winidea.get_cpu_status()

            for core, status in results.items():
                self.result_string.append(f'{core}: {status}')
                logger.info(f'  {core}: {status}')

            errors = [c for c, s in results.items() if s.startswith('<error:')]
            if errors:
                logger.warning(
                    f'[{self.name}] {len(errors)}/{len(results)} '
                    f'core(s) returned errors: {errors}'
                )
        except Exception as e:
            message = f'WinIDEA get CPU status failed: {e!s}'
            self.result_string.append(message)
            msg = f'[{self.name}] {message}'
            raise ExecutionStepError(msg, phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] CPU status queried for {len(results)} core(s)')
