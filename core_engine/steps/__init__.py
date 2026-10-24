"""
Unified execution steps package.

Importing this module triggers registration of all step classes via
the @StepRegistry.register() decorator.

Step modules are discovered automatically: every ``*_steps.py`` file
in this package is imported on first access, so adding a new step
module requires no edit to this file.
"""

import importlib
import pkgutil
from typing import List

from xc_ce_utils import logger


def _discover_step_modules() -> List[str]:
    """Import every ``*_steps`` module in this package.

    Uses :func:`pkgutil.iter_modules` so discovery works both for a
    regular filesystem layout and inside a PyInstaller frozen bundle
    (where modules live in the embedded archive rather than as files
    on disk). The decorator ``@StepRegistry.register(...)`` at module
    top level handles the actual registration as a side effect of
    import.

    Returns:
        List of fully-qualified module names that were imported.
    """
    package_name = __name__  # "xc_ce_utils.core_engine.steps"

    imported: List[str] = []
    for module_info in pkgutil.iter_modules(
        __path__, prefix=f'{package_name}.'
    ):
        if not module_info.name.endswith('_steps'):
            continue
        try:
            importlib.import_module(module_info.name)
            imported.append(module_info.name)
        except ImportError as exc:  # pragma: no cover - surfaced as build error
            logger.error(
                f'Failed to import step module {module_info.name}: {exc}'
            )
            raise

    return sorted(imported)


_DISCOVERED_STEP_MODULES = _discover_step_modules()
