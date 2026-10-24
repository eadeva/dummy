"""Application use cases for execution setup and action orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SetupUseCaseDependencies:
    """Dependency boundary for setup orchestration use case."""

    prepare_setup_directories: Callable[[], None]
    handle_clean_only_mode: Callable[[], bool]
    run_optional_setup_cleanups: Callable[[], None]
    run_setup_configuration: Callable[[], None]
    log_phase_header: Callable[[str], None]
    log_success: Callable[[str], None]


def run_setup_use_case(deps: SetupUseCaseDependencies) -> bool:
    """Execute setup orchestration through application-layer boundary."""
    deps.log_phase_header('SETUP')

    deps.prepare_setup_directories()

    if deps.handle_clean_only_mode():
        return False

    deps.run_optional_setup_cleanups()
    deps.run_setup_configuration()
    deps.log_success('Setup completed')
    return True


@dataclass(frozen=True)
class ExecuteActionUseCaseDependencies:
    """Dependency boundary for action execution orchestration use case."""

    get_action_name: Callable[[], str]
    prepare_action_environment: Callable[[], None]
    collect_action_sections: Callable[[], tuple[dict[str, Any], dict[str, Any]]]
    execute_action_sections: Callable[[dict[str, Any], dict[str, Any]], None]
    finalize_action_execution: Callable[[], None]
    log_phase_header: Callable[[str], None]


def run_execute_action_use_case(
    deps: ExecuteActionUseCaseDependencies,
) -> None:
    """Execute action orchestration through application-layer boundary."""
    action_name = deps.get_action_name()
    deps.log_phase_header(f'EXECUTING ACTION {action_name}')

    deps.prepare_action_environment()
    phases, sets_config = deps.collect_action_sections()
    deps.execute_action_sections(phases, sets_config)
    deps.finalize_action_execution()

    deps.log_phase_header(f'ACTION {action_name} - END')


@dataclass(frozen=True)
class UploadDebugArtifactsUseCaseDependencies:
    """Dependency boundary for debug-artifact upload orchestration."""

    is_running_in_ci: Callable[[], bool]
    upload_debug_artifacts_impl: Callable[[Exception], None]
    log_warning: Callable[[str], None]
    log_debug: Callable[[str], None]
    format_traceback: Callable[[], str]


def run_upload_debug_artifacts_use_case(
    *,
    deps: UploadDebugArtifactsUseCaseDependencies,
    error: Exception,
) -> None:
    """Execute debug-artifact upload orchestration through use-case boundary."""
    if not deps.is_running_in_ci():
        return

    try:
        deps.upload_debug_artifacts_impl(error)
    except Exception as upload_error:
        deps.log_warning(f'Failed to upload debug artifacts: {upload_error}')
        deps.log_debug(f'Debug upload traceback:\n{deps.format_traceback()}')
