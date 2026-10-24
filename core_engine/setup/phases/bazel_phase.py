"""Bazel disk-cache and remote-cache setup phases."""

from __future__ import annotations

import sys
import time
from datetime import datetime

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


def _bazel_enabled(ctx: SetupContext) -> bool:
    value = ctx.config.get('BAZEL', '')
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('true', '1', 'yes')


class BazelDiskCachePhase(SetupPhase):
    """Always-on disk-cache path validation (independent of remote cache).

    Runs every setup so developers get correct user-specific paths without
    permission issues.
    """

    name = 'bazel_disk_cache'

    def should_run(self, ctx: SetupContext) -> bool:
        return _bazel_enabled(ctx)

    def run(self, ctx: SetupContext) -> None:
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - BAZEL DISK CACHE')
        ctx.setup._ensure_bazel_disk_cache_path(ctx.state)
        logger.log_phase_header('SETUP - BAZEL DISK CACHE - END')
        logger.debug(f'  ⏱  Bazel disk cache: {time.monotonic() - t0:.1f}s')


class BazelRemoteCachePhase(SetupPhase):
    """Remote Bazel cache configuration — regenerates ``.bazelrc.cache`` / ``.bazelrc.auth``."""

    name = 'bazel_remote_cache'

    def should_run(self, ctx: SetupContext) -> bool:
        if not _bazel_enabled(ctx):
            return False
        project_bazelrc = ctx.setup.repo_path / '.bazelrc.cache'
        project_bazelrc_auth = ctx.setup.repo_path / '.bazelrc.auth'
        return (
            ctx.first_time_setup
            or ctx.force
            or not project_bazelrc.exists()
            or not project_bazelrc_auth.exists()
            or ctx.needs_credential_check  # credentials may have changed
        )

    def run(self, ctx: SetupContext) -> None:
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - BAZEL REMOTE CACHE')
        logger.progress('Setting up Bazel remote cache configuration...')
        sys.stdout.flush()
        if not ctx.setup.setup_bazel_cache(ctx.config):
            logger.info('Bazel remote cache not configured (this is optional)')
            sys.stdout.flush()
        else:
            logger.success(' Bazel remote cache configured')
            ctx.state['setup_steps']['bazel_cache'] = datetime.now().isoformat()
            sys.stdout.flush()
        logger.log_phase_header('SETUP - BAZEL REMOTE CACHE - END')
        logger.debug(f'  ⏱  Bazel remote cache: {time.monotonic() - t0:.1f}s')
