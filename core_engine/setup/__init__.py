"""
XC-CE Utils Setup Module

Handles initial setup and configuration for standalone builds:
- Conan installation and configuration
- Bazel remote cache setup
- Environment validation
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .environment_setup import EnvironmentSetup

__all__ = ['EnvironmentSetup']


def __getattr__(name: str) -> Any:
    """Load heavy setup exports lazily.

    Importing ``xc_ce_utils.core_engine.setup`` should stay lightweight so
    submodule imports (for example ``setup.env_isolation``) do not pull the
    full ``environment_setup`` dependency tree unless explicitly needed.
    """
    if name == 'EnvironmentSetup':
        from .environment_setup import EnvironmentSetup

        return EnvironmentSetup
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
