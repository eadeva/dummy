"""Environment bootstrap orchestration for the dynamic CLI.

Extracted from the former ``core_engine/dynamic_cli.py`` monolith. Runs the
one-time Conan/toolchain environment setup (``core_engine.setup``) before the
dynamic CLI is constructed, unless the invocation is a fast help/version path.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from time import perf_counter

from xc_ce_utils import logger
from xc_ce_utils.core_engine.cli.startup_tracing import trace_startup


def _get_environment_setup_cls() -> type:
    module = import_module('xc_ce_utils.core_engine.setup')
    return module.EnvironmentSetup


def _should_skip_environment_setup() -> bool:
    skip_setup_commands = {
        '--help',
        '-h',
        '--version',
        'clean-older-versions',
        'force-setup',
        'full-setup',
        'clang-setup',
        'hooks-setup',
        'refresh-bazel-cache',
        'devmate-setup',
    }
    return any(arg in sys.argv for arg in skip_setup_commands)


def _initialize_conan_environment(
    repo_path: Path,
    *,
    environment_setup_cls: type,
) -> None:
    try:
        stage_t0 = perf_counter()
        environment_setup_cls.ensure_conan_env(repo_path)
        trace_startup(
            '_run_environment_setup ensure_conan_env done', t0=stage_t0
        )
    except Exception as error:
        logger.critical(f'Failed to initialise Conan environment: {error}')
        logger.critical('Cannot proceed without proper Conan configuration.')
        sys.exit(1)


def _run_full_environment_setup(
    repo_path: Path,
    *,
    environment_setup_cls: type,
) -> None:
    logger.log_phase_header('XC-CE Utils')

    stage_t0 = perf_counter()
    setup = environment_setup_cls(repo_path=repo_path)
    trace_startup(
        '_run_environment_setup EnvironmentSetup created', t0=stage_t0
    )

    stage_t0 = perf_counter()
    setup_succeeded = setup.run_setup()
    if not setup_succeeded:
        message = 'Environment setup had issues.'
        raise Exception(message)
    trace_startup('_run_environment_setup run_setup completed', t0=stage_t0)

    os.environ['XC_CE_SETUP_DONE'] = '1'
    trace_startup('_run_environment_setup marked setup done')


def run_environment_setup() -> None:
    """Run environment setup if not already done (Conan, toolbase, etc.)."""
    setup_t0 = perf_counter()
    trace_startup('_run_environment_setup entered', t0=setup_t0)

    if 'REPO_PATH' not in os.environ:
        os.environ['REPO_PATH'] = str(Path.cwd())
        trace_startup('_run_environment_setup initialized REPO_PATH')

    repo_path = Path(os.environ['REPO_PATH'])

    should_skip_setup = _should_skip_environment_setup()
    trace_startup(f'_run_environment_setup skip decision: {should_skip_setup}')

    # Fast help/version path: avoid importing EnvironmentSetup entirely.
    if should_skip_setup:
        trace_startup('_run_environment_setup skipped full setup')
        trace_startup('_run_environment_setup finished', t0=setup_t0)
        return

    environment_setup_cls = _get_environment_setup_cls()
    _initialize_conan_environment(
        repo_path,
        environment_setup_cls=environment_setup_cls,
    )

    # Run full environment setup if needed
    if 'XC_CE_SETUP_DONE' not in os.environ:
        _run_full_environment_setup(
            repo_path,
            environment_setup_cls=environment_setup_cls,
        )

    trace_startup('_run_environment_setup finished', t0=setup_t0)
