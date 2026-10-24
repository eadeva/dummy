"""Clang environment setup phase.

Sits AFTER :class:`GitHooksPhase` in the default chain so that
``configure_git_hooks`` has already produced ``.pre-commit-config.yaml``
when this phase deploys the (Phase-D) clang hooks into it.

Gates
-----
The phase is a no-op unless:

* host is Windows AND not CI,
* ``main_conf.yml::CLANG_CONFIG`` resolves to an existing file,
* resolved config has ``enabled: true``,
* AND (project-side ``config/clang/clang_conf.yml`` changed since the last
  run, OR ``ctx.force`` / ``ctx.first_time_setup``).

State is persisted through the same hash-based mechanism used by
:class:`GitHooksPhase` (``_has_directory_changed`` /
``_save_directory_hash`` on the project config file).
"""

from __future__ import annotations

import platform
import sys
import time
from pathlib import Path
from typing import Optional

from xc_ce_utils.clang.config_resolver import resolve_clang_config
from xc_ce_utils.core_engine.cli import role_gating
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)
from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


def _resolve_project_clang_cfg_path(ctx: SetupContext) -> Optional[Path]:
    """Locate the on-disk project clang config file.

    ``conf_file_loader`` auto-expands ``*_CONFIG`` string pointers into
    inlined dicts, so by the time we read ``ctx.config["CLANG_CONFIG"]``
    the original relative-path string is usually gone. Probe the
    conventional location (``<repo>/config/clang/clang_conf.yml``) when
    the value is a dict; only fall back to the legacy string form when a
    raw mapping was passed in.
    """
    pointer = ctx.config.get('CLANG_CONFIG')
    if not pointer:
        return None
    config_root = get_project_config_root(ctx.setup.repo_path)
    if isinstance(pointer, dict):
        # Loader already inlined the file contents -- recover its conventional
        # path so the directory-hash change-detector has something to watch.
        path = (config_root / 'clang' / 'clang_conf.yml').resolve()
    else:
        path = (config_root / pointer).resolve()
    return path if path.exists() else None


class ClangSetupPhase(SetupPhase):
    """Install clang toolchain and conditionally refresh repo clang configs.

    Maintainers run the full clang setup (including generated repo files).
    Non-maintainers run local toolchain setup only (no repository writes).
    """

    name = 'clang_setup'

    def should_run(self, ctx: SetupContext) -> bool:
        if ctx.is_ci:
            logger.debug('⏭  ClangSetupPhase: CI environment, skipping')
            return False
        if platform.system() != 'Windows':
            logger.debug('⏭  ClangSetupPhase: non-Windows host, skipping')
            return False
        cfg_path = _resolve_project_clang_cfg_path(ctx)
        if cfg_path is None:
            logger.debug(
                '⏭  ClangSetupPhase: no CLANG_CONFIG pointer, skipping'
            )
            return False
        merged = resolve_clang_config(ctx.config, ctx.setup.repo_path)
        if not merged or not merged.get('enabled', False):
            logger.debug('⏭  ClangSetupPhase: clang feature disabled, skipping')
            return False
        ctx.extras['clang_cfg_path'] = cfg_path
        include_maintainer_steps = bool(
            ctx.extras.get('include_maintainer_steps', True)
        )
        ctx.extras['clang_is_maintainer'] = include_maintainer_steps and (
            role_gating.is_maintainer(ctx.config)
        )
        return True

    def run(self, ctx: SetupContext) -> None:
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - CLANG')
        is_maintainer = bool(ctx.extras.get('clang_is_maintainer'))

        if is_maintainer:
            cfg_path: Path = ctx.extras['clang_cfg_path']
            cfg_dir = cfg_path.parent

            # Maintainers: full clang config generation with hash-based skip.
            needs_setup = (
                ctx.first_time_setup
                or ctx.force
                or ctx.setup._has_directory_changed(cfg_dir, 'clang_config')
            )
            if not needs_setup:
                logger.debug(
                    '⏭  ClangSetupPhase: project clang config unchanged, skipping'
                )
                logger.log_phase_header('SETUP - CLANG - END')
                logger.debug(f'  ⏱  Clang setup: {time.monotonic() - t0:.1f}s')
                return

            logger.progress(
                'Configuring clang toolchain (full maintainer mode)...'
            )
            sys.stdout.flush()
            if not ctx.setup._setup_clang(ctx.config):
                logger.warning('Clang setup had issues, continuing anyway...')
                sys.stdout.flush()
            else:
                ctx.setup._save_directory_hash(cfg_dir, 'clang_config')
        else:
            # Developers: local install/env setup only (no repo file generation).
            logger.progress(
                'Configuring local clang toolchain (developer mode, no repo writes)...'
            )
            sys.stdout.flush()
            if not ctx.setup._setup_clang_local_toolchain(ctx.config):
                logger.warning(
                    'Local clang toolchain setup had issues, continuing anyway...'
                )
                sys.stdout.flush()
        logger.log_phase_header('SETUP - CLANG - END')
        logger.debug(f'  ⏱  Clang setup: {time.monotonic() - t0:.1f}s')
