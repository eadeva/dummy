"""Conan environment-variable export phase (runs every setup)."""

from __future__ import annotations

import sys

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


class ApplyConanEnvPhase(SetupPhase):
    """Apply Conan environment variables — lightweight, runs every setup."""

    name = 'apply_conan_env'

    def should_run(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> None:
        logger.debug('Applying Conan environment variables...')
        sys.stdout.flush()
        if not ctx.setup._apply_conan_environment():
            raise RuntimeError('Failed to apply Conan environment.')
        logger.debug(' Conan environment applied')
        sys.stdout.flush()
