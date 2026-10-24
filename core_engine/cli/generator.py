"""Dynamic CLI generator: builds the rich-click CLI from configuration.

Extracted from the former ``core_engine/dynamic_cli.py`` monolith. This
module creates a rich-click CLI dynamically based on configuration files:
- Actions from config/actions/actions_conf.yml
- Variants and options from config/project/project_conf.yml

The CLI supports:
- Dynamic command generation based on available actions
- Dynamic variant arguments based on the variant matrix
- Rich help formatting with examples and grouping
- Automatic validation of variant combinations
- Command-specific options (build-type, create-baseline, etc.)
"""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

from xc_ce_utils import logger
from xc_ce_utils.core_engine.application import load_runtime_config
from xc_ce_utils.core_engine.cli import platform_setup
from xc_ce_utils.core_engine.cli.startup_tracing import trace_startup


def _is_metadata_request() -> bool:
    return any(arg in sys.argv for arg in ('--help', '-h', '--version'))


def _import_config_loader_dependencies():
    """Import config-loader dependencies lazily to reduce module import cost."""
    module = import_module('xc_ce_utils.conf_file_loader.conf_file_loader')

    return (
        module.ConfigLoader,
        module.ConfigLoaderError,
        module.load_entry_config,
        module.resolve_entry_conf_path,
    )


def _import_execution_dependencies():
    """Import lightweight execution dependencies lazily.

    Avoid importing the execution orchestrator here; it eagerly loads the
    full step registry and significantly slows startup for ``--help`` and
    ``--version`` flows.
    """
    exceptions_module = import_module('xc_ce_utils.core_engine.domain.exceptions')
    variant_matrix_module = import_module('xc_ce_utils.core_engine.domain.variant_matrix')
    return (
        exceptions_module.ConfigurationError,
        variant_matrix_module.VariantMatrix,
    )


def _import_cli_dependencies():
    """Import CLI factory and introspection helpers lazily."""
    introspection = import_module('xc_ce_utils.core_engine.cli.action_introspection')
    command_factory = import_module('xc_ce_utils.core_engine.cli.command_factory')
    root_group = import_module('xc_ce_utils.core_engine.cli.root_group')
    aux_helper = import_module('xc_ce_utils.global_modules.aux_helper')
    return (
        introspection,
        command_factory,
        root_group,
        aux_helper.is_running_in_ci,
    )


def _get_isolate_environment() -> Any:
    module = import_module('xc_ce_utils.core_engine.setup.env_isolation')
    return module.isolate_environment


def _get_execution_tracker_cls() -> type:
    module = import_module('xc_ce_utils.core_engine.cli.execution_tracker')
    return module.ExecutionTracker


def _get_role_gating_module() -> Any:
    return import_module('xc_ce_utils.core_engine.cli.role_gating')


class DynamicCLIGenerator:
    """Generates a dynamic CLI based on configuration files."""

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize the CLI generator.

        Args:
            repo_root: Repository root path. Defaults to ``$REPO_PATH`` or
                the current working directory.
        """
        init_t0 = perf_counter()
        trace_startup('DynamicCLIGenerator.__init__ entered', t0=init_t0)
        is_metadata_request = _is_metadata_request()
        (
            configuration_error_cls,
            variant_matrix_cls,
        ) = _import_execution_dependencies()

        self._load_runtime_configuration(
            repo_root,
            is_metadata_request=is_metadata_request,
            configuration_error_cls=configuration_error_cls,
        )
        self._initialize_project_configuration(
            configuration_error_cls,
            variant_matrix_cls,
            is_metadata_request=is_metadata_request,
        )
        self.variant = None
        trace_startup('DynamicCLIGenerator.__init__ finished', t0=init_t0)

    def _load_runtime_configuration(
        self,
        repo_root: Optional[Path],
        *,
        is_metadata_request: bool,
        configuration_error_cls: type,
    ) -> None:
        (
            config_loader_cls,
            _,
            load_entry_config,
            resolve_entry_conf_path,
        ) = _import_config_loader_dependencies()

        stage_t0 = perf_counter()
        platform_setup.set_platform_env_variables()
        trace_startup('set platform env variables', t0=stage_t0)

        self.repo_root = repo_root or Path(os.getenv('REPO_PATH') or str(Path.cwd()))
        trace_startup(f'repo root resolved: {self.repo_root}')

        stage_t0 = perf_counter()
        platform_setup.configure_dev_tooling_provider_from_env()
        trace_startup('dev-tooling provider configured', t0=stage_t0)

        stage_t0 = perf_counter()
        self.config_loader = config_loader_cls()
        trace_startup('ConfigLoader initialized', t0=stage_t0)

        stage_t0 = perf_counter()
        runtime_config = load_runtime_config(
            repo_root=self.repo_root,
            cwd=Path.cwd(),
            load_entry_config=load_entry_config,
            resolve_entry_conf_path=resolve_entry_conf_path,
            configuration_error_cls=configuration_error_cls,
            validate_schema=not is_metadata_request,
        )
        self.conf_file = runtime_config.conf_file
        self.full_config = runtime_config.raw_main_config
        self.main_config = runtime_config.canonical_main_config
        trace_startup('entry config loaded via application facade', t0=stage_t0)

    def _initialize_project_configuration(
        self,
        configuration_error_cls: type,
        variant_matrix_cls: type,
        *,
        is_metadata_request: bool,
    ) -> None:
        self._validate_required_sections(configuration_error_cls)
        self._set_project_identity(configuration_error_cls)

        self.build_config = self.full_config['ACTIONS']
        logger.debug(f'ACTIONS type: {type(self.build_config).__name__}')
        if 'ACTIONS' in self.build_config:
            logger.debug(f"ACTIONS found in ACTIONS: {list(self.build_config['ACTIONS'].keys())}")
        else:
            logger.warning('No ACTIONS in ACTIONS!')

        self.oss_config = self.full_config.get('OSS_CONFIG', {})
        self.splunk_config = self.full_config.get('SPLUNK', {})
        self.project_config = self.full_config['PROJECT_CONFIG']
        self.artifactories = self.full_config['ARTIFACTORIES']

        from xc_ce_utils.utils.git_version_resolver import (
            RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL,
            export_git_managed_environment,
            parse_git_managed_versioning,
            resolve_git_managed_version,
            version_string,
        )

        raw_rb_versioning = self.full_config['RB_VERSIONING']
        git_managed = parse_git_managed_versioning(raw_rb_versioning)
        version_resolver = None
        default_version_pattern = None
        if git_managed and git_managed[0] == RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL:
            # Each variant resolves its own version from its tag pattern; RB_VERSION is set
            # per variant when the action configuration is created (variant_executor).
            os.environ['XC_CE_UTILS_RB_VERSIONING_MODE'] = git_managed[0]
            default_version_pattern = git_managed[1]
            repo_root = self.repo_root

            def version_resolver(pattern: str) -> Dict[str, Any]:
                return resolve_git_managed_version(repo_root, pattern)

            self.version_dict = {}
            self.artifact_version = None
        elif git_managed:
            # Not auto-inlined by ConfigLoader: 'git-managed' doesn't end in
            # .yml/.yaml/.json, so it stays a plain string here. Mark the mode
            # via env var so ActionConfiguration can independently recompute
            # and write its own per-action version.json later.
            os.environ['XC_CE_UTILS_RB_VERSIONING_MODE'] = git_managed[0]
            self.version_dict = resolve_git_managed_version(self.repo_root, git_managed[1])
            # Exposed for Deployer._build_artifact_properties (commits_ahead,
            # full_version_tag artifact properties).
            export_git_managed_environment(self.version_dict, git_managed[1])
            self.artifact_version = version_string(self.version_dict)
        else:
            os.environ['XC_CE_UTILS_RB_VERSIONING_MODE'] = 'file'
            self.version_dict = raw_rb_versioning
            self.artifact_version = version_string(self.version_dict)

        stage_t0 = perf_counter()
        self.variant_matrix = variant_matrix_cls(
            self.project_config,
            default_version=self.version_dict,
            version_resolver=version_resolver,
            default_version_pattern=default_version_pattern,
        )
        trace_startup('variant matrix initialized', t0=stage_t0)

        self._apply_environment_isolation(is_metadata_request=is_metadata_request)

        self.actions: dict[str, Any] = {}
        self.default_action = None
        self.tracker = None
        self._set_default_action()
        self._load_actions(configuration_error_cls)

    def _validate_required_sections(self, configuration_error_cls: type) -> None:
        if 'ACTIONS' in self.full_config and 'PROJECT_CONFIG' in self.full_config:
            return

        message = "Wrong configuration, 'ACTIONS' and 'PROJECT_CONFIG' are mandatory fields"
        raise configuration_error_cls(message)

    def _set_project_identity(self, configuration_error_cls: type) -> None:
        if self.main_config is not None:
            project_name = self.main_config.PROJECT_CONFIG.PROJECT
            xc_ce_utils_version = self.main_config.XC_CE_UTILS_VERSION
        else:
            project_name = self.full_config['PROJECT_CONFIG'].get('PROJECT', None)
            xc_ce_utils_version = self.full_config.get('XC_CE_UTILS_VERSION', None)

        if not project_name:
            message = 'PROJECT name is missing in PROJECT_CONFIG'
            raise configuration_error_cls(message)

        if not xc_ce_utils_version:
            message = 'XC_CE_UTILS_VERSION is missing in main configuration'
            raise configuration_error_cls(message)

        os.environ['PROJECT_NAME'] = project_name
        os.environ['XC_CE_UTILS_VERSION'] = xc_ce_utils_version

    def _apply_environment_isolation(
        self,
        *,
        is_metadata_request: bool,
    ) -> None:
        env_isolation_config = self.full_config.get('ENV_ISOLATION', None)
        if env_isolation_config is None:
            env_isolation_config = {
                'enabled': True,
                'bypass_env_vars': [],
                'bypass_path_elements': [],
            }

        if is_metadata_request:
            trace_startup('environment isolation skipped for metadata request')
            return

        isolate_environment = _get_isolate_environment()
        stage_t0 = perf_counter()
        isolate_environment(env_isolation_config)
        trace_startup('environment isolation applied', t0=stage_t0)

    def _set_default_action(self) -> None:
        if (
            'DEFAULT_PARAMETERS' not in self.build_config
            or 'action' not in self.build_config['DEFAULT_PARAMETERS']
        ):
            return

        self.default_action = self.build_config['DEFAULT_PARAMETERS']['action'].lower()

    def _load_actions(self, configuration_error_cls: type) -> None:
        if 'ACTIONS' not in self.build_config:
            message = "Bad configuration. No 'ACTIONS' element"
            raise configuration_error_cls(message)

        stage_t0 = perf_counter()
        for action_name, action_config in self.build_config['ACTIONS'].items():
            self.actions[action_name] = action_config
            logger.debug(f"Action '{action_name}': type={type(action_config).__name__}")
            if isinstance(action_config, dict):
                logger.debug(
                    f"  Has PHASES: {'PHASES' in action_config}, Has phases: {'phases' in action_config}"
                )
                if 'PHASES' in action_config:
                    logger.debug(f"  PHASES count: {len(action_config['PHASES'])}")
                    logger.debug(f"  First 3 phases: {list(action_config['PHASES'].keys())[:3]}")
            else:
                logger.warning(f'  Action config is not a dict! Got: {action_config}')

        trace_startup(f'actions indexed: {len(self.actions)}', t0=stage_t0)

    def _ensure_tracker(self) -> None:
        if self.tracker is None:
            self.tracker = _get_execution_tracker_cls().from_config(self.full_config)

    # ------------------------------------------------------------------
    # ExecutionTracker delegators (kept for external callers)
    # ------------------------------------------------------------------
    def start_execution(self):
        self._ensure_tracker()
        self.tracker.start_execution()

    def add_warning(self, message: str, operation: str = 'General'):
        self._ensure_tracker()
        self.tracker.add_warning(message, operation)

    def add_error(self, message: str, operation: str = 'General'):
        self._ensure_tracker()
        self.tracker.add_error(message, operation)

    def track_operation(self, operation: str, status: str, duration: Optional[float] = None):
        self._ensure_tracker()
        self.tracker.track_operation(operation, status, duration)

    def print_final_summary(self):
        self._ensure_tracker()
        self.tracker.print_final_summary()

    def _create_action_groups(self, command_factory: Any) -> dict[str, Any]:
        return {
            'config': command_factory.create_config_group(self),
            'config-devops': command_factory.create_config_devops_group(self),
        }

    def _wire_action_commands(
        self,
        *,
        cli: Any,
        introspection: Any,
        command_factory: Any,
        action_groups: dict[str, Any],
        is_ci: bool,
    ) -> int:
        conan_enabled = bool(self.full_config.get('CONAN_ENABLED', True))
        role_gating = _get_role_gating_module()
        added_commands = 0

        for action in self.actions:
            if not conan_enabled and action.replace('_', '-').lower() == 'conan-cache-cleanup':
                logger.debug('Skipping action "conan-cache-cleanup" because CONAN_ENABLED=false')
                continue

            action_config = introspection.get_action_config(self, action)
            is_hidden = not is_ci and introspection.is_ci_only_action(self, action)
            cmd = command_factory.create_action_command_with_arguments(
                self, action, hidden=is_hidden
            )

            role_gating.apply_action_gating(
                cmd, action_config.get('requires_role'), self.full_config
            )

            group_name = action_config.get('action_group')
            if group_name is None:
                cli.add_command(cmd)
                added_commands += 1
                continue

            target_group_name = group_name
            if (
                group_name == 'config'
                and str(action_config.get('requires_role', '')).lower() == 'maintainer'
            ):
                target_group_name = 'config-devops'

            if target_group_name not in action_groups:
                action_groups[target_group_name] = command_factory.create_dynamic_group(
                    target_group_name
                )
            action_groups[target_group_name].add_command(cmd)
            added_commands += 1

        return added_commands

    def create_cli(self) -> Any:
        """Create the dynamic CLI with variant arguments for action commands."""
        create_t0 = perf_counter()
        trace_startup('create_cli entered', t0=create_t0)

        stage_t0 = perf_counter()
        platform_setup.configure_rich_click_defaults()
        trace_startup('create_cli rich-click configured', t0=stage_t0)

        stage_t0 = perf_counter()
        (
            introspection,
            command_factory,
            root_group,
            is_running_in_ci,
        ) = _import_cli_dependencies()
        trace_startup('create_cli CLI dependencies imported', t0=stage_t0)

        stage_t0 = perf_counter()
        cli = root_group.create_root_group(self)
        trace_startup('root click group created', t0=stage_t0)

        # Store CLI group reference for dynamic help generation
        self.cli_group = cli

        # Check if running in CI
        is_ci = is_running_in_ci()

        # Create config group (and any other groups declared by actions)
        action_groups = self._create_action_groups(command_factory)
        trace_startup('base command groups created')

        # Add action commands with variant arguments
        stage_t0 = perf_counter()
        added_commands = self._wire_action_commands(
            cli=cli,
            introspection=introspection,
            command_factory=command_factory,
            action_groups=action_groups,
            is_ci=is_ci,
        )

        for group in action_groups.values():
            cli.add_command(group)

        trace_startup(
            f'create_cli command wiring done (action_cmds={added_commands})',
            t0=stage_t0,
        )
        trace_startup('create_cli finished', t0=create_t0)

        return cli
