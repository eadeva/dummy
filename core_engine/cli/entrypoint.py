"""Entry point for building and running the dynamic CLI.

Extracted from the former ``core_engine/dynamic_cli.py`` monolith. Exposes
``create_dynamic_cli()`` (consumed by ``xc_ce_utils.xc_ce_utils:main``) and a
standalone ``main()`` for direct invocation
(``python -m xc_ce_utils.core_engine.cli.entrypoint``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

# Add the xc_ce_utils repo root for imports when run as a standalone script.
_xc_ce_utils_path = str(Path(__file__).resolve().parent.parent.parent.parent)
if _xc_ce_utils_path not in sys.path:
    sys.path.insert(0, _xc_ce_utils_path)

from xc_ce_utils import logger  # noqa: E402
from xc_ce_utils.core_engine.cli import platform_setup  # noqa: E402
from xc_ce_utils.core_engine.cli.environment_setup_orchestrator import (  # noqa: E402
    run_environment_setup,
)
from xc_ce_utils.core_engine.cli.generator import (  # noqa: E402
    DynamicCLIGenerator,
)
from xc_ce_utils.core_engine.cli.startup_tracing import (  # noqa: E402
    trace_startup,
)


def _create_dynamic_cli_impl(
    repo_root: Optional[Path],
    *,
    create_t0: float,
) -> Any:
    stage_t0 = perf_counter()
    generator = DynamicCLIGenerator(repo_root)
    trace_startup('DynamicCLIGenerator created', t0=stage_t0)

    stage_t0 = perf_counter()
    cli = generator.create_cli()
    trace_startup('click CLI object created', t0=stage_t0)
    trace_startup('create_dynamic_cli finished', t0=create_t0)
    return cli


def create_dynamic_cli(repo_root: Optional[Path] = None) -> Any:
    """
    Create a dynamic CLI based on configuration files.

    Args:
        repo_root: Repository root path

    Returns:
        Click group representing the CLI
    """
    create_t0 = perf_counter()
    trace_startup('create_dynamic_cli entered', t0=create_t0)

    try:
        return _create_dynamic_cli_impl(repo_root, create_t0=create_t0)
    except Exception as e:
        if e.__class__.__name__ == 'ConfigLoaderError':
            logger.critical(f'Configuration file error: {e}')
            sys.exit(1)
        if e.__class__.__name__ == 'ConfigurationError':
            logger.critical(f'Configuration error: {e}')
            sys.exit(1)
        raise


def main():
    """Entry point for the xc-ce-builder console script (legacy standalone)."""
    main_t0 = perf_counter()
    trace_startup('legacy main() entered', t0=main_t0)

    stage_t0 = perf_counter()
    platform_setup.ensure_utf8_stdout()
    trace_startup('legacy main() _ensure_utf8_stdout done', t0=stage_t0)

    stage_t0 = perf_counter()
    run_environment_setup()
    trace_startup('legacy main() environment setup done', t0=stage_t0)

    stage_t0 = perf_counter()
    cli = create_dynamic_cli()
    trace_startup('legacy main() dynamic CLI created', t0=stage_t0)

    trace_startup('legacy main() entering click CLI')
    cli()
    trace_startup('legacy main() click CLI finished', t0=main_t0)


if __name__ == '__main__':
    main()
