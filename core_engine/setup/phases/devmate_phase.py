"""DEVMATE_PAT environment-variable setup phase."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


class DevmatePATPhase(SetupPhase):
    """Validate / configure the ``DEVMATE_PAT`` environment variable.

    Skipped in CI.  Re-checks at most every 5 weeks; honours a 3-week
    cooldown after a failed / declined prompt.
    """

    name = 'devmate_pat'

    def should_run(self, ctx: SetupContext) -> bool:
        if ctx.is_ci:
            return False
        devmate_in_env = os.environ.get('DEVMATE_PAT') is not None
        devmate_needs_check = (
            ctx.first_time_setup
            or ctx.force
            or ctx.setup._is_devmate_check_needed(ctx.state, weeks=5)
            or not devmate_in_env
        )
        devmate_last_success = ctx.state.get('setup_steps', {}).get(
            'devmate_pat'
        )
        devmate_failed_before = 'devmate_last_failed_prompt' in ctx.state
        devmate_in_cooldown = (
            devmate_failed_before
            and not ctx.setup._is_retry_needed(
                ctx.state, 'devmate_last_failed_prompt', weeks=3
            )
        )
        devmate_should_run = (
            ctx.first_time_setup
            or ctx.force
            or (not devmate_last_success and not devmate_in_cooldown)
        )
        return bool(devmate_needs_check and devmate_should_run)

    def run(self, ctx: SetupContext) -> None:
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - DEVMATE PAT')
        logger.progress('Validating DEVMATE_PAT environment variable...')
        sys.stdout.flush()
        devmate_pat_present = bool(os.environ.get('DEVMATE_PAT'))
        user_wants_devmate = (
            ctx.force
            or devmate_pat_present
            or ctx.setup._ask_proceed(
                '\n DEVMATE (AI assistant) is not configured.\n'
                '   Set it up now? (requires a DEVMATE Personal Access Token)'
            )
        )
        if not user_wants_devmate:
            ctx.state['devmate_last_failed_prompt'] = datetime.now().isoformat()
            logger.info('⏭  DEVMATE setup skipped – will ask again in 3 weeks.')
            logger.info(
                "    (Run './build.ps1 config force-setup' to configure immediately)"
            )
            sys.stdout.flush()
        elif not ctx.setup._setup_devmate_pat():
            ctx.state['devmate_last_failed_prompt'] = datetime.now().isoformat()
            logger.info(
                '  DEVMATE_PAT setup skipped or failed - will retry in 3 weeks'
            )
            logger.info('    (or use --force-setup to retry immediately)')
            sys.stdout.flush()
        else:
            ctx.state.pop('devmate_last_failed_prompt', None)
            logger.success(' DEVMATE_PAT configured')
            ctx.state['setup_steps']['devmate_pat'] = datetime.now().isoformat()
            ctx.state['last_devmate_check'] = datetime.now().isoformat()
            sys.stdout.flush()
        logger.log_phase_header('SETUP - DEVMATE PAT - END')
        logger.debug(f'  ⏱  DEVMATE PAT: {time.monotonic() - t0:.1f}s')
