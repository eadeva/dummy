"""Credential validation and renewal-reminder phases."""

from __future__ import annotations

import sys
import time
from datetime import datetime

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


class CredentialValidationPhase(SetupPhase):
    """Upfront Artifactory credential validation.

    Runs only in CI (required) or on explicit ``--force-setup`` (user
    asked for clean re-validation).  Local builds skip this and resolve
    credentials lazily on first use.
    """

    name = 'credentials'

    def should_run(self, ctx: SetupContext) -> bool:
        return ctx.is_ci or ctx.force

    def run(self, ctx: SetupContext) -> None:
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - CREDENTIAL VALIDATION')
        logger.progress('Validating Artifactory credentials...')
        sys.stdout.flush()
        ctx.setup._validate_artifactory_credentials(ctx.config)
        ctx.state['last_credential_check'] = datetime.now().isoformat()
        logger.success(' Credentials validated')
        sys.stdout.flush()
        logger.log_phase_header('SETUP - CREDENTIAL VALIDATION - END')
        logger.debug(
            f'  ⏱  Credential validation: {time.monotonic() - t0:.1f}s'
        )


class CredentialRenewalReminderPhase(SetupPhase):
    """Warn when credentials have not been renewed for >180 days."""

    name = 'credential_renewal_reminder'

    def should_run(self, ctx: SetupContext) -> bool:
        return ctx.setup._is_credential_renewal_needed(ctx.state)

    def run(self, ctx: SetupContext) -> None:
        if ctx.is_ci:
            logger.warning(
                '⚠  Credential renewal is overdue (>180 days). '
                "Run 'build.ps1 creds renew' on a local machine."
            )
        else:
            logger.warning(
                '⚠  Credentials have not been renewed for >180 days. '
                "Run 'build.ps1 creds renew' to refresh them."
            )
