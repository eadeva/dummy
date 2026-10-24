"""Git hooks legacy-state migration and active setup phases."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


class GitHooksMigrationPhase(SetupPhase):
    """One-time migration of legacy global git-hooks state to per-repo tracking."""

    name = 'git_hooks_migration'

    def should_run(self, ctx: SetupContext) -> bool:
        steps = ctx.state.get('setup_steps', {})
        file_hashes = ctx.state.get('file_hashes', {})
        return 'git_hooks' in steps or '.githooks/pre-commit' in file_hashes

    def run(self, ctx: SetupContext) -> None:
        steps = ctx.state.get('setup_steps', {})
        file_hashes = ctx.state.get('file_hashes', {})
        migrated = False
        if 'git_hooks' in steps:
            del steps['git_hooks']
            migrated = True
        if '.githooks/pre-commit' in file_hashes:
            del file_hashes['.githooks/pre-commit']
            migrated = True
        if migrated:
            ctx.setup._save_setup_state(ctx.state)


class GitHooksPhase(SetupPhase):
    """Install / refresh per-repository git hooks (pre-commit framework).

    Post-migration the bundled bash hooks are gone; the gate is now the
    pre-commit-config template plus the Python checks directory, which
    together drive the framework install.  ``configure_git_hooks`` is
    idempotent (no-ops when nothing needs doing), so the phase can safely
    run on every setup invocation; finer-grained skipping is done via the
    source-hash check below.
    """

    name = 'git_hooks'

    def should_run(self, ctx: SetupContext) -> bool:
        git_hooks_root = (
            Path(__file__).resolve().parent.parent.parent.parent / 'git_hooks'
        )
        template = git_hooks_root / 'templates' / 'pre-commit' / 'base.yaml'
        checks_dir = git_hooks_root / 'checks'
        if not template.exists() or not checks_dir.exists():
            logger.debug(
                '⏭  pre-commit base template or checks directory not found, skipping'
            )
            return False
        # Hash both directories together so any template/check change re-installs.
        ctx.extras['git_hooks_source_dir'] = git_hooks_root
        return True

    def run(self, ctx: SetupContext) -> None:
        source_hook_dir: Path = ctx.extras['git_hooks_source_dir']
        include_maintainer_steps = bool(
            ctx.extras.get('include_maintainer_steps', False)
        )

        current_source_hash = ctx.setup._calculate_directory_hash(
            source_hook_dir
        )
        _, stored_hash = ctx.setup._get_git_hooks_state()

        jira_config_missing = False
        try:
            result = subprocess.run(
                ['git', 'config', '--local', 'xc-ce.jiraProject'],
                cwd=ctx.setup.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            jira_config_missing = result.returncode != 0
        except Exception:
            jira_config_missing = True

        needs_setup = (
            ctx.first_time_setup
            or ctx.force
            or not (
                ctx.setup.repo_path / '.git' / 'hooks' / 'pre-commit'
            ).exists()
            or stored_hash != current_source_hash
            or jira_config_missing
        )

        if needs_setup:
            t0 = time.monotonic()
            logger.log_phase_header('SETUP - GIT HOOKS')
            logger.progress('Checking Git hooks for updates...')
            sys.stdout.flush()
            if not ctx.setup._setup_git_hooks(
                ctx.config,
                include_maintainer_steps=include_maintainer_steps,
                force=ctx.force,
            ):
                logger.warning(
                    'Git hooks setup had issues, continuing anyway...'
                )
                sys.stdout.flush()
            else:
                logger.success(' Git hooks configured')
                ctx.setup._save_git_hooks_state(current_source_hash)
                sys.stdout.flush()
            logger.log_phase_header('SETUP - GIT HOOKS - END')
            logger.debug(f'  ⏱  Git hooks: {time.monotonic() - t0:.1f}s')
        else:
            logger.debug(
                '⏭  Skipping Git hooks (unchanged for this repository)'
            )

        # NOTE: Do not set `core.hooksPath` here.
        #
        # The pre-commit framework installs its shim scripts into git's
        # default location (`.git/hooks/`). Any `core.hooksPath` override
        # would redirect git away from those shims and silently disable
        # the entire hook pipeline. The legacy `.githooks/` directory
        # (and its `core.hooksPath = .githooks` config) is migrated away
        # by `_cleanup_legacy_hooks()` during `configure_git_hooks()`.
