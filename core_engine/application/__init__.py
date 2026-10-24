"""Public application-layer API for core-engine driving adapters.

This module is the single, stable entrypoint for *driving* adapters —
``xc_ce_utils.core_engine.cli`` today, and any future
``xc_ce_utils.core_engine.gui`` or other automation surface. Driving adapters
must import exclusively from this package root (plus
``xc_ce_utils.core_engine.domain`` for shared vocabulary such as exceptions
and value objects); they must never import
``xc_ce_utils.core_engine.application.orchestration``,
``xc_ce_utils.core_engine.application.facades``,
``xc_ce_utils.core_engine.application.use_cases`` or
``xc_ce_utils.core_engine.adapters`` submodules directly. This keeps the
execution engine reusable behind multiple front-ends without any changes
below this boundary.
"""

from xc_ce_utils.core_engine.adapters import (
    configure_git_hooks,
    create_copilot_instructions_manager,
    create_copilot_vs_configurator,
    create_mcp_server_configurator,
    create_vscode_commands_generator,
    create_vscode_extensions_installer,
    reset_dev_tooling_provider,
    set_dev_tooling_provider,
)
from xc_ce_utils.core_engine.application.facades.execution import (
    ActionExecutionOptions,
    ExecutionRuntime,
    execute_action,
)
from xc_ce_utils.core_engine.application.facades.runtime import (
    RuntimeConfigDependencies,
    RuntimeConfigEnvelope,
    load_runtime_config,
)
from xc_ce_utils.core_engine.application.orchestration.action_orchestrator import (
    BuildType,
    ExecutionAction,
)
from xc_ce_utils.core_engine.application.use_cases.execution import (
    ExecuteActionUseCaseDependencies,
    SetupUseCaseDependencies,
    UploadDebugArtifactsUseCaseDependencies,
    run_execute_action_use_case,
    run_setup_use_case,
    run_upload_debug_artifacts_use_case,
)

__all__ = [
    'ActionExecutionOptions',
    'BuildType',
    'ExecuteActionUseCaseDependencies',
    'ExecutionAction',
    'ExecutionRuntime',
    'RuntimeConfigDependencies',
    'RuntimeConfigEnvelope',
    'SetupUseCaseDependencies',
    'UploadDebugArtifactsUseCaseDependencies',
    'configure_git_hooks',
    'create_copilot_instructions_manager',
    'create_copilot_vs_configurator',
    'create_mcp_server_configurator',
    'create_vscode_commands_generator',
    'create_vscode_extensions_installer',
    'execute_action',
    'load_runtime_config',
    'reset_dev_tooling_provider',
    'run_execute_action_use_case',
    'run_setup_use_case',
    'run_upload_debug_artifacts_use_case',
    'set_dev_tooling_provider',
]
