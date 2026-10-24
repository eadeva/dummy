"""
Unified exception hierarchy for the xc-ce-utils execution engine.

Unified exception hierarchy for the execution engine.
"""

from enum import Enum


class ErrorRecoveryStrategy(Enum):
    """Recovery strategy for a step's failure mode.

    Declared at registration time on each step type. Currently *metadata-only*:
    the execution engine still routes errors via the legacy ``game_stopper``
    boolean and the ``AbortError`` / ``ContinueWithErrorsError`` exceptions.
    The enum is consumed in later phases when the engine is migrated.

    Values:
        ABORT — failure halts the entire execution (default; legacy behaviour
            for ``game_stopper=True``).
        CONTINUE_WITH_ERRORS — failure is recorded but execution continues
            (legacy behaviour for ``game_stopper=False``).
        RETRY_ONCE — engine should attempt the step a second time on failure
            before falling back to ABORT.
        SKIP — failure is silently ignored; the step is treated as if it
            never ran.
    """

    ABORT = 'abort'
    CONTINUE_WITH_ERRORS = 'continue_with_errors'
    RETRY_ONCE = 'retry_once'
    SKIP = 'skip'


class ExecutionError(Exception):
    """Base exception for all execution errors."""

    def __init__(self, message='Execution error', phase=None, exit_code=1):
        self.message = message
        self.phase = phase
        self.exit_code = exit_code
        super().__init__(self.message)


_REPORTED_ATTRIBUTE = '_xc_ce_utils_reported'


def mark_reported(error: BaseException) -> BaseException:
    """Flag ``error`` as already printed, so outer handlers don't print it again."""
    setattr(error, _REPORTED_ATTRIBUTE, True)
    return error


def is_reported(error: BaseException) -> bool:
    """Return True if ``error`` or an exception it wraps (``raise ... from``) was already printed."""
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        if getattr(current, _REPORTED_ATTRIBUTE, False):
            return True
        seen.add(id(current))
        current = current.__cause__
    return False


class ConfigurationError(ExecutionError):
    """Raised when configuration is invalid."""

    def __init__(self, message='Configuration error', phase=None):
        super().__init__(message, phase=phase)


class RuntimeConfigError(ConfigurationError):
    """Raised when runtime variable resolution or config processing fails."""

    def __init__(self, message='Runtime configuration error', phase=None):
        super().__init__(message, phase=phase)


class DependencyError(ExecutionError):
    """Raised when dependency installation fails."""

    def __init__(self, message='Dependency error', phase=None):
        super().__init__(message, phase=phase)


class ExecutionStepError(ExecutionError):
    """Raised when a build phase fails."""

    def __init__(self, message='Phase error', phase=None):
        super().__init__(message, phase=phase)


class SetupError(ExecutionError):
    """Raised when setup or initialization fails."""

    def __init__(self, message='Setup error', phase=None):
        super().__init__(message, phase=phase)


class AbortError(ExecutionError):
    """Raised when a game_stopper step fails — halts the entire execution."""

    def __init__(self, message='Execution aborted', phase=None):
        super().__init__(message, phase=phase)


class ContinueWithErrorsError(ExecutionError):
    """Raised when a non-game_stopper step fails — execution continues."""

    def __init__(self, message='Execution continues with errors', phase=None):
        super().__init__(message, phase=phase)


class BlockingTestError(ExecutionError):
    """Raised when a blocking test evaluation fails — halts execution."""

    def __init__(self, message='Blocking test failure', phase=None):
        super().__init__(message, phase=phase)


class NonBlockingTestError(ExecutionError):
    """Raised when a non-blocking test evaluation fails — execution continues."""

    def __init__(self, message='Non-blocking test failure', phase=None):
        super().__init__(message, phase=phase)


# Aliases
BuildError = ExecutionError
