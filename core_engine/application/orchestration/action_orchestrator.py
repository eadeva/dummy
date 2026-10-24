"""Thin ExecutionAction orchestrator composing execution collaborators.

This module replaces the former monolithic ``execution_engine.py``. It keeps
only lifecycle orchestration (setup/execute/run, phase-window selection,
clean operations, version environment) and delegates to focused
collaborators:

- :class:`~xc_ce_utils.core_engine.application.orchestration.step_executor.StepExecutor`
  for step/execution-set creation and execution.
- :class:`~xc_ce_utils.core_engine.application.orchestration.tool_requires_installer.ToolRequiresInstaller`
  for platform tool-requires installation.
- :class:`~xc_ce_utils.core_engine.application.orchestration.debug_artifact_uploader.DebugArtifactUploader`
  for CI debug-artifact upload on failure.
- :class:`~xc_ce_utils.core_engine.reporting.adapters.reporting_orchestrator.ReportingOrchestrator`
  for unified end-of-action reporting.

.. uml:: _diagrams/build_flow_diagram.puml
    :align: center
"""

import os
import platform
import shutil
import stat
import subprocess
import traceback
from datetime import datetime
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.execution.resource_manager import (
    ResourceReleaseAdapterFactoryInput,
    create_resource_release_adapter,
    create_standard_resource_release_callbacks,
    initialize_resource_pool,
    release_all_resources,
)
from xc_ce_utils.core_engine.application.orchestration.debug_artifact_uploader import (
    DebugArtifactUploader,
)
from xc_ce_utils.core_engine.application.orchestration.step_executor import (
    StepExecutor,
)
from xc_ce_utils.core_engine.application.orchestration.tool_requires_installer import (
    ToolRequiresInstaller,
)
from xc_ce_utils.core_engine.application.use_cases.execution import (
    ExecuteActionUseCaseDependencies,
    SetupUseCaseDependencies,
    UploadDebugArtifactsUseCaseDependencies,
    run_execute_action_use_case,
    run_setup_use_case,
    run_upload_debug_artifacts_use_case,
)
from xc_ce_utils.core_engine.config.action_configuration import (
    ActionConfiguration,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    BuildError,
    ConfigurationError,
    DependencyError,
    is_reported,
    mark_reported,
)
from xc_ce_utils.core_engine.domain.runtime_context import get_runtime_context
from xc_ce_utils.core_engine.reporting.adapters.reporting_orchestrator import (
    ReportingOrchestrator,
)
from xc_ce_utils.core_engine.steps.base import ExecutionNode
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

BUGFIX_VERSION_INDEX = 2


def _get_rb_bazel_wrapper_cls() -> type:
    module = import_module('xc_ce_utils.core_engine.wrappers.rb_bazel_wrapper')
    return module.RBBazelWrapper


def _get_ccache_manager_cls() -> type:
    module = import_module('xc_ce_utils.core_engine.wrappers.ccache_utils')
    return module.CcacheManager


class BuildType(Enum):
    """Enumeration of supported build types."""

    DEBUG = 'Debug'
    RELEASE = 'Release'
    REL_WITH_DEBUG_INFO = 'RelWithDebInfo'
    DEVELOPER = 'Developer'


class ExecutionAction:
    """Main orchestrator for the execution process.

    Supports both flat PHASES and grouped SETS.
    PHASES execute first, then SETS. Steps within SETS support non-blocking execution,
    game_stopper control, and execute_if conditional execution.
    """

    def __init__(self, config: ActionConfiguration):
        """
        Initialize build handler.

        Args:
            config: Build configuration
        """
        self.config = config
        self.steps: List[ExecutionNode] = []
        self.errors = False
        self.omitted = False
        self.resources: Dict[str, Any] = {}
        self.global_variables: Dict[str, Any] = {}

        action_conf = self.config.get_action_config()
        self.omit_variants: List[str] = action_conf.get('omit_variants', [])
        self.only_variants: List[str] = action_conf.get('only_variants', [])
        self.only_cx_pipelines: bool = action_conf.get('only_cx_pipelines', False)

        self.omitted = self._resolve_action_omission()
        if self.omitted:
            return

        self.runtime_context = get_runtime_context()
        self._step_executor = StepExecutor(
            config=self.config,
            resources=self.resources,
            global_variables=self.global_variables,
        )
        self._tool_installer = ToolRequiresInstaller(
            config=self.config,
            runtime_context=self.runtime_context,
        )
        self._debug_uploader = DebugArtifactUploader(config=self.config)
        self._init_resources()

    def _resolve_action_omission(self) -> bool:
        """Evaluate action-level omission policy for current runtime context."""
        if self.only_cx_pipelines and not is_running_in_ci():
            logger.debug(
                f'[{self.config.get_action_name()}] Skipping execution (only_cx_pipelines=True and not in CX pipeline)'
            )
            return True

        current_variant = self._current_variant_alias()

        if self.only_variants and current_variant not in self.only_variants:
            logger.debug(
                f'[{self.config.get_action_name()}] Skipping execution (current variant: {current_variant} not in only_variants)'
            )
            return True

        if self.omit_variants and current_variant in self.omit_variants:
            logger.debug(
                f'[{self.config.get_action_name()}] Skipping execution (current variant: {current_variant} in omit_variants)'
            )
            return True

        return False

    def _current_variant_alias(self) -> Optional[str]:
        """Return active variant alias when available."""
        if not hasattr(self.config, 'variant'):
            return None
        return self.config.variant.get_variant_alias()

    def setup(self) -> None:
        """Set up the build environment."""
        if self.omitted:
            logger.info(
                f"Action '{self.config.get_action_name()}' is omitted based on configuration. Skipping setup and execution."
            )
            return False

        try:
            return self._setup_impl()
        except Exception as e:
            self._release_resources()
            msg = f'Setup completed: {e}'
            raise DependencyError(msg) from e

    def _setup_impl(self) -> bool:
        return run_setup_use_case(
            SetupUseCaseDependencies(
                prepare_setup_directories=self._prepare_setup_directories,
                handle_clean_only_mode=self._handle_clean_only_mode,
                run_optional_setup_cleanups=self._run_optional_setup_cleanups,
                run_setup_configuration=self._run_setup_configuration,
                log_phase_header=logger.log_phase_header,
                log_success=logger.success,
            )
        )

    def _prepare_setup_directories(self) -> None:
        """Reset setup output directories and relocate startup JSON log."""
        # Removing logs, reports and bin folders if they exist
        self.__remove_folder(self.config.get_logs_folder(), restore_empty=True)
        self.__remove_folder(
            self.config.get_reports_folder(),
            restore_empty=True,
        )
        # Now the logs folder is clean and recreated — relocate the JSON log
        # from its startup temp path (_log/xc-ce-utils.jsonl) into the
        # action-specific folder alongside the per-step text logs.
        logger.relocate_default_json_log(
            self.config.get_logs_folder() / 'xc-ce-utils_full_log.jsonl'
        )

        self.config.get_build_folder().mkdir(parents=True, exist_ok=True)

    def _handle_clean_only_mode(self) -> bool:
        """Handle clean-only setup path and signal whether execution should stop."""
        if not self.config.clean:
            return False

        self._clean_build_only()
        logger.success('Clean completed - stopping execution')
        logger.log_phase_header('CLEAN - END')
        return True

    def _run_optional_setup_cleanups(self) -> None:
        """Apply optional rebuild/docascode cleanup behavior before setup."""
        if self.config.rebuild:
            self._clean_build()

        if self.config.no_cache and self._has_docascode_phases():
            self._clean_docascode_build()

    def _run_setup_configuration(self) -> None:
        """Execute setup configuration and dependency preparation flow."""
        # Written here (after any rebuild/no-cache clean above) rather than at
        # ActionConfiguration construction time, so a clean build folder isn't
        # wiped out before phases (e.g. version_header) run. No-op unless
        # RB_VERSIONING is 'git-managed'.
        self.config.write_git_managed_version_file()
        self._log_build_handler_configuration()
        self._tool_installer.install()
        self._dump_full_environment()

    def create_build_steps(self) -> None:
        """Create build steps based on configuration.

        Handles both flat PHASES and grouped SETS. PHASES are subject to
        from/to phase filtering. SETS are always created in full.
        """
        try:
            self._create_build_steps_impl()

        except Exception as e:
            msg = f'Failed to create build steps: {e}'
            raise ConfigurationError(msg) from e

    def _create_build_steps_impl(self) -> None:
        action_config = self.config.get_action_config()
        phases = action_config.get('PHASES', {})
        sets_config = action_config.get('SETS', {})

        if phases:
            self._append_filtered_phases(phases)
            logger.success(f'Created {len(self.steps)} build steps')

        if sets_config:
            self._append_sets(sets_config)
            logger.success(f'Created {len(sets_config)} sets')

        if not phases and not sets_config:
            logger.warning('No phases or sets found in configuration')

    def _append_filtered_phases(self, phases: Dict[str, Any]) -> None:
        for phase_name, phase_config in self._select_phase_window(
            phases,
            validate_to_phase=True,
        ):
            step = self._step_executor.create_step(phase_name, phase_config)
            if step:
                self.steps.append(step)
                logger.debug(f'Created step: {step}')

    def _append_sets(self, sets_config: Dict[str, Any]) -> None:
        for set_name, set_conf in sets_config.items():
            exec_set = self._step_executor.create_execution_set(set_name, set_conf)
            self.steps.append(exec_set)
            logger.debug(f"Created set '{set_name}'")

    def execute_action(self) -> None:
        """Create and execute build steps one at a time.

        Each step is created immediately before execution so that runtime
        config changes (env variables, global_variables) from previous
        steps are visible to subsequent ones.
        """
        action_error: Optional[Exception] = None
        try:
            self._execute_action_impl()

        except Exception as e:
            action_error = e
            self._release_resources()
            msg = f'Build execution failed: {e}'
            raise BuildError(msg) from e
        finally:
            self._run_unified_reporting(action_error=action_error)

    def _execute_action_impl(self) -> None:
        run_execute_action_use_case(
            ExecuteActionUseCaseDependencies(
                get_action_name=self.config.get_action_name,
                prepare_action_environment=self._prepare_action_environment,
                collect_action_sections=self._collect_action_sections,
                execute_action_sections=self._execute_action_sections,
                finalize_action_execution=self._finalize_action_execution,
                log_phase_header=logger.log_phase_header,
            )
        )

    def _prepare_action_environment(self) -> None:
        """Prepare process environment variables before phase execution."""
        self._set_rb_version_environment()
        self._set_variant_version_environment()

    def _collect_action_sections(
        self,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Collect phase/set sections from current action configuration."""
        action_config = self.config.get_action_config()
        phases = action_config.get('PHASES', {})
        sets_config = action_config.get('SETS', {})
        return phases, sets_config

    def _execute_action_sections(
        self,
        phases: Dict[str, Any],
        sets_config: Dict[str, Any],
    ) -> None:
        """Execute configured phases/sets and handle empty action fallback."""
        if phases:
            self._execute_action_phases(phases)

        if sets_config:
            self._execute_action_sets(sets_config)

        if not phases and not sets_config:
            logger.warning('No phases or sets found in configuration')

    def _finalize_action_execution(self) -> None:
        """Emit end-of-action statistics and terminal status logs."""
        self._log_total_execution_time()
        self._log_ccache_stats()

        if self.errors:
            logger.warning('Execution completed with errors')
            return
        logger.success('Build completed successfully')

    def _set_rb_version_environment(self) -> None:
        rb_version = self.config.artifact_version
        logger.info(f'RB version: {rb_version}')
        (
            rb_major_version,
            rb_minor_version,
            rb_bugfix_version,
        ) = self._resolve_rb_version_components(rb_version)

        os.environ['RB_MAJOR_VERSION'] = str(rb_major_version)
        os.environ['RB_MINOR_VERSION'] = str(rb_minor_version)
        os.environ['RB_BUGFIX_VERSION'] = str(rb_bugfix_version)

    def _resolve_rb_version_components(
        self,
        rb_version: Optional[str],
    ) -> Tuple[str, str, str]:
        """Resolve RB major/minor/bugfix version components."""
        version_parts = rb_version.split('.') if rb_version else []
        rb_major_version = version_parts[0] if len(version_parts) > 0 else 'unknown'
        rb_minor_version = version_parts[1] if len(version_parts) > 1 else 'unknown'
        rb_bugfix_version = self._extract_rb_bugfix_version(version_parts)
        return rb_major_version, rb_minor_version, rb_bugfix_version

    @staticmethod
    def _extract_rb_bugfix_version(version_parts: List[str]) -> str:
        """Extract numeric RB bugfix component from split version parts."""
        if len(version_parts) <= BUGFIX_VERSION_INDEX:
            return 'unknown'

        bugfix_component = version_parts[BUGFIX_VERSION_INDEX]
        bugfix_digits = ''.join(ch for ch in bugfix_component if ch.isdigit())
        return bugfix_digits or '0'

    def _set_variant_version_environment(self) -> None:
        logger.info('Variant version:')
        for variant_version_element, variant_version_value in (
            self.config.get_variant().get_version().items()
        ):
            logger.info(f'    {variant_version_element.upper()}={variant_version_value}')
            os.environ[variant_version_element.upper()] = str(variant_version_value)

    def _execute_action_phases(self, phases: Dict[str, Any]) -> None:
        logger.trace(f'Phases in action config: {list(phases.keys())}')
        logger.trace(f'from_phase={self.config.from_phase}, to_phase={self.config.to_phase}')

        for phase_name, phase_config in self._select_phase_window(
            phases,
            validate_to_phase=False,
        ):
            logger.trace(
                f"Creating step for phase: '{phase_name}', config type: {type(phase_config).__name__}, "
                f"config keys: {list(phase_config.keys()) if isinstance(phase_config, dict) else 'N/A'}"
            )
            step = self._step_executor.create_step(phase_name, phase_config)
            logger.trace(f'Step created: {step} (type={type(step).__name__})')
            if step and self._step_executor.execute(step):
                self.errors = True

    def _execute_action_sets(self, sets_config: Dict[str, Any]) -> None:
        for set_name, set_conf in sets_config.items():
            exec_set = self._step_executor.create_execution_set(set_name, set_conf)
            exec_set.run()
            if exec_set.errors:
                self.errors = True

    def _select_phase_window(
        self,
        phases: Dict[str, Any],
        *,
        validate_to_phase: bool,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Return phases in the configured from/to window.

        Args:
            phases: Ordered phase mapping from action configuration.
            validate_to_phase: When True, require the to_phase to exist.
        """
        selected: List[Tuple[str, Dict[str, Any]]] = []
        from_phase_found = False
        to_phase_found = False

        for phase_name, phase_config in phases.items():
            if not from_phase_found and phase_name != self.config.from_phase:
                continue

            from_phase_found = True
            selected.append((phase_name, phase_config))

            if phase_name == self.config.to_phase:
                to_phase_found = True
                break

        if not from_phase_found:
            msg = f"Invalid from_phase '{self.config.from_phase}' specified"
            raise ConfigurationError(msg)

        if validate_to_phase and not to_phase_found:
            msg = f"Invalid to_phase '{self.config.to_phase}' specified"
            raise ConfigurationError(msg)

        return selected

    def _log_total_execution_time(self) -> None:
        elapsed_time = (datetime.now() - self.config.start_time).total_seconds()
        minutes, seconds = divmod(elapsed_time, 60)

        if minutes > 0:
            logger.progress(
                f'Full execution time: {int(minutes)} minutes and {seconds:.2f} seconds'
            )
            return

        logger.progress(f'Full execution time: {seconds:.2f} seconds')

    def run(self) -> None:
        """Run the complete build process."""
        try:
            self._run_lifecycle()

        except BuildError as e:
            self._handle_run_build_error(e)
            try:
                self._prompt_ai_troubleshooting()
            except Exception as exc:
                logger.debug(f'Failed to prompt AI troubleshooting: {exc}')
            raise
        except Exception as e:
            normalized_error = self._handle_unexpected_run_error(e)
            try:
                self._prompt_ai_troubleshooting()
            except Exception as exc:
                logger.debug(f'Failed to prompt AI troubleshooting: {exc}')
            raise normalized_error from e
        finally:
            self._release_resources()

    def _run_lifecycle(self) -> None:
        """Execute setup and action body for a full run lifecycle."""
        if not self.setup():
            return

        # If clean-only mode, setup() already handled everything and returned early
        if self._should_skip_action_execution():
            return

        self.execute_action()

    def _should_skip_action_execution(self) -> bool:
        """Return True when action execution should be skipped after setup."""
        return self.config.clean

    def _handle_run_build_error(self, error: BuildError) -> None:
        """Handle known build failure path in run()."""
        self._upload_debug_artifacts(error)

    def _handle_unexpected_run_error(self, error: Exception) -> BuildError:
        """Log and normalize unexpected run() failures as BuildError."""
        if not is_reported(error):
            logger.critical(
                f'Unexpected error in build process: {error}\n{traceback.format_exc()}'
            )
            mark_reported(error)
        self._upload_debug_artifacts(error)
        msg = f'Build process failed: {error}'
        return BuildError(msg)

    def _prompt_ai_troubleshooting(self) -> None:
        """Prompt the user if they want to analyze the failure using AI."""
        import sys

        from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

        if (
            not self.config.interactive_failure_assistance
            or is_running_in_ci()
            or not sys.stdin.isatty()
        ):
            return

        logger.warning('')
        logger.warning('=' * 80)
        logger.warning('❌ ACTION EXECUTION FAILED')
        logger.warning('=' * 80)
        logger.warning('  Would you like to analyze this failure using an AI assistant?')
        logger.warning('    1. GitHub Copilot CLI')
        logger.warning('    2. Gemini CLI')
        logger.warning('    3. No, I will do it myself')
        logger.warning('=' * 80)

        response = ''
        while response not in ('1', '2', '3'):
            try:
                response = input('  Select an option (1-3): ').strip()
            except KeyboardInterrupt:
                logger.info('\n  Troubleshooting skipped.')
                return
            except Exception:
                return

        if response == '3':
            logger.info('  Troubleshooting skipped.')
            return

        action_name = self.config.get_action_name()

        if response == '2':
            # Run Gemini CLI
            try:
                from xc_ce_utils.core_engine.adapters.ai.gemini_wrapper import run_gemini_analysis

                logger.info('🤖 Starting Gemini CLI analysis, please wait...')
                run_gemini_analysis(action_name, self.config.repo_root)
            except Exception as exc:
                logger.error(f'  Failed to run Gemini CLI: {exc}')

        elif response == '1':
            # Run GitHub Copilot CLI
            try:
                from xc_ce_utils.core_engine.adapters.ai.copilot_wrapper import run_copilot_analysis

                logger.info('🤖 Starting GitHub Copilot CLI analysis, please wait...')
                run_copilot_analysis(action_name, self.config.repo_root)
            except Exception as exc:
                logger.error(f'  Failed to run GitHub Copilot CLI: {exc}')

    def _run_unified_reporting(self, action_error: Optional[Exception] = None) -> None:
        """Always generate unified reports after action completion."""
        logger.log_phase_header('UNIFIED REPORTING')

        try:
            ReportingOrchestrator(self.config).run_unified_reporting(
                errors=self.errors,
                action_error=action_error,
            )

        except Exception as exc:
            logger.warning(f'[UNIFIED REPORTING] Failed to generate unified report: {exc}')
        finally:
            logger.log_phase_header('UNIFIED REPORTING - END')

    @staticmethod
    def __remove_folder(
        folder_path: Path,
        *,
        restore_empty: bool = False,
    ) -> None:
        def handle_readonly(func, path, excinfo):
            error = excinfo[1]
            if func in {os.unlink, os.remove} and isinstance(error, PermissionError):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            else:
                msg = f'Failed to remove {path}: {error}'
                raise Exception(msg)

        if folder_path and folder_path.exists():
            logger.progress(f'Removing folder: {folder_path}')
            try:
                shutil.rmtree(folder_path, onerror=handle_readonly)
            except Exception as e:
                logger.warning(f'Regular removal failed, trying alternative methods: {e}')

                if platform.system() == 'Windows':
                    try:
                        logger.info('Attempting removal with Windows commands...')
                        subprocess.run(
                            f'rmdir /s /q "{folder_path}"',
                            shell=True,
                            check=False,
                        )
                    except Exception as e2:
                        msg = f'Failed to remove build directory: {e2}'
                        raise Exception(msg) from e2

        if restore_empty:
            folder_path.mkdir(parents=True, exist_ok=True)

    def _get_action_phases(self) -> Dict[str, Any]:
        """Return PHASES mapping for current action configuration."""
        self.config.get_action_name()
        action_config = self.config.get_action_config()
        phases = action_config.get('PHASES', {})
        return phases if isinstance(phases, dict) else {}

    @staticmethod
    def _has_bazel_phases(phases: Dict[str, Any]) -> bool:
        """Return True when action phases contain any Bazel step type."""
        bazel_phase_types = {
            'bazel_build',
            'bazel_test',
            'bazel_run',
            'bazel_query',
        }
        return any(
            phase_config.get('step_type') in bazel_phase_types
            for phase_config in phases.values()
            if isinstance(phase_config, dict)
        )

    def _run_bazel_clean_expunge_if_needed(
        self,
        phases: Dict[str, Any],
    ) -> None:
        """Run bazel clean --expunge when Bazel phases are configured."""
        if not self._has_bazel_phases(phases):
            return

        logger.progress('Bazel phases detected - running bazel clean --expunge...')
        try:
            rb_bazel_wrapper_cls = _get_rb_bazel_wrapper_cls()

            bazel = rb_bazel_wrapper_cls(
                log_folder=self.config.get_logs_folder(),
                workspace_dir=self.config.repo_root,
                bin_folder=self.config.get_bin_folder(),
            )
            bazel.clean(expunge=True)
            logger.success('Bazel clean --expunge completed')
        except Exception as e:
            logger.warning(f'Bazel clean failed: {e}')

    def _clean_build(self) -> None:
        """Clean build and reports folders for a rebuild."""

        logger.log_phase_header('CLEAN FOR REBUILD')
        logger.progress('Cleaning build folders for rebuild...')

        phases = self._get_action_phases()
        self._run_bazel_clean_expunge_if_needed(phases)

        self.__remove_folder(self.config.get_build_folder(), restore_empty=True)

        logger.success('Build folders cleaned for rebuild')
        logger.log_phase_header('CLEAN FOR REBUILD - END')

    def _clean_build_only(self) -> None:
        """Clean build folders and stop (clean-only mode)."""

        logger.log_phase_header('CLEAN')
        logger.progress('Cleaning build folders...')

        phases = self._get_action_phases()
        self._run_bazel_clean_expunge_if_needed(phases)

        self.__remove_folder(self.config.get_build_folder(), restore_empty=True)
        logger.success('Build folders deleted')

    def _has_docascode_phases(self) -> bool:
        """Check if action contains docascode phases."""
        action_config = self.config.get_action_config()
        phases = action_config.get('PHASES', {})

        for _phase_name, phase_config in phases.items():
            if phase_config.get('step_type') == 'docascode':
                return True
        return False

    def _clean_docascode_build(self) -> None:
        """Clean docascode _build folder when --no-cache is used (rebuild from scratch)."""
        logger.progress('--no-cache: Cleaning docascode _build folder for clean rebuild...')
        self.__remove_folder(self.config.get_build_folder(), restore_empty=True)
        logger.success('Docascode _build folder cleaned')

    def _dump_full_environment(self) -> None:
        """Dump full environment snapshot after all tools are installed."""
        self.config.dump_full_environment()

    def _log_build_handler_configuration(self) -> None:
        """Save build configuration to a JSON file."""
        self.config.dump_configuration(yaml_format=False)
        self.config.dump_env_variables()
        if self._has_conan_phases():
            self.config.dump_conandata_yaml()

    def _has_conan_phases(self) -> bool:
        """Check if the current action contains any conan_* phase types."""

        def _scan(phases: dict) -> bool:
            for _name, cfg in phases.items():
                if isinstance(cfg, dict):
                    ptype = cfg.get('type') or cfg.get('step_type', '')
                    if ptype and ptype.startswith('conan_'):
                        return True
                    if 'steps' in cfg and isinstance(cfg['steps'], dict) and _scan(cfg['steps']):
                        return True
            return False

        return _scan(self.config.action_config.get('PHASES', {}))

    def _log_ccache_stats(self) -> None:
        """Log ccache statistics if ccache is available."""
        try:
            ccache_manager_cls = _get_ccache_manager_cls()
            ccache_manager = ccache_manager_cls()
            if (
                ccache_manager.is_available()
                and self.config.get_action_name() == 'build'
                and os.environ['USE_CCACHE']
            ):
                ccache_manager.log_stats()
        except ImportError:
            logger.debug('ccache_utils not available, skipping ccache stats')
        except Exception as e:
            logger.debug(f'Failed to log ccache stats: {e}')

    def _upload_debug_artifacts(self, error: Exception) -> None:
        """Upload ``_log`` and ``_reports`` folders to Artifactory on CX failure.

        Only executes inside a CI environment.

        Args:
            error: The exception that caused the failure (used for log context only).
        """
        run_upload_debug_artifacts_use_case(
            deps=UploadDebugArtifactsUseCaseDependencies(
                is_running_in_ci=is_running_in_ci,
                upload_debug_artifacts_impl=self._debug_uploader.upload_impl,
                log_warning=logger.warning,
                log_debug=logger.debug,
                format_traceback=traceback.format_exc,
            ),
            error=error,
        )

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    def _init_resources(self) -> None:
        """Initialize the shared resource pool."""
        initialize_resource_pool(self.resources)

    def _release_resources(self) -> None:
        """Release all shared resources (threads, connections, hardware).

        Safe to call multiple times.
        """
        release_all_resources(
            create_resource_release_adapter(
                payload=ResourceReleaseAdapterFactoryInput(
                    resources=self.resources,
                    callbacks=create_standard_resource_release_callbacks(
                        log_debug=logger.debug,
                        log_warning=logger.warning,
                    ),
                    log_debug=logger.debug,
                    log_warning=logger.warning,
                )
            )
        )
