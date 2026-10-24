"""VS Code extensions setup phase.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.core_engine.setup.vscode import VSCodeExtensionsOutcome
from xc_ce_utils.rb_logger import logger


class VSCodeExtensionsPhase(SetupPhase):
    """Install VS Code extensions — skipped in CI, 3-week cooldown on failure."""

    name = 'vscode_extensions'

    @staticmethod
    def _call_setup_method(setup_obj, method_name: str, /, *args, **kwargs):
        method = getattr(setup_obj, method_name)
        return method(*args, **kwargs)

    def should_run(self, ctx: SetupContext) -> bool:
        _ = self.name
        if ctx.is_ci:
            return False
        extensions_last_success = ctx.state.get('setup_steps', {}).get(
            'vscode_extensions'
        )
        extensions_failed = ctx.state.get('vscode_extensions_failed', False)
        extensions_in_cooldown = (
            extensions_failed
            and not self._call_setup_method(
                ctx.setup,
                '_is_retry_needed',
                ctx.state,
                'vscode_extensions_last_attempt',
                weeks=3,
            )
        )
        ctx.extras['vscode_extensions_in_cooldown'] = extensions_in_cooldown
        ctx.extras['vscode_extensions_last_success'] = extensions_last_success
        return (
            ctx.first_time_setup
            or ctx.force
            or (not extensions_last_success and not extensions_in_cooldown)
        )

    def run(self, ctx: SetupContext) -> None:
        _ = self.name
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - VSCODE EXTENSIONS')
        logger.progress('Installing VS Code extensions...')
        sys.stdout.flush()
        # Prompt the user only when not forced and we're past first-time setup.
        user_wants_vscode = (
            ctx.force
            or not ctx.first_time_setup
            or self._call_setup_method(
                ctx.setup,
                '_ask_proceed',
                '\n VS Code extensions are not installed.\n'
                '   Install them now?',
            )
        )
        if not user_wants_vscode:
            ctx.state['vscode_extensions_failed'] = True
            ctx.state['vscode_extensions_last_attempt'] = (
                datetime.now().isoformat()
            )
            logger.info(
                '⏭  VS Code extension installation skipped - will ask again in 3 weeks.'
            )
            logger.info(
                "    (Run './build.ps1 config vs-code refresh-extensions' to install immediately)"
            )
            sys.stdout.flush()
            logger.log_phase_header('SETUP - VSCODE EXTENSIONS - END')
            logger.debug(
                f'  ⏱  VS Code extensions: {time.monotonic() - t0:.1f}s'
            )
            return

        outcome = self._call_setup_method(
            ctx.setup, '_install_vscode_extensions'
        )

        if outcome is VSCodeExtensionsOutcome.INSTALLED:
            ctx.state['vscode_extensions_failed'] = False
            ctx.state['vscode_extensions_last_attempt'] = (
                datetime.now().isoformat()
            )
            logger.success(' VS Code extensions installed')
            ctx.state['setup_steps']['vscode_extensions'] = (
                datetime.now().isoformat()
            )
            vscode_extensions_file = (
                ctx.setup.repo_path / '.vscode' / 'extensions.json'
            )
            if vscode_extensions_file.exists():
                self._call_setup_method(
                    ctx.setup,
                    '_update_vscode_extensions_hash',
                    vscode_extensions_file,
                    ctx.state,
                )
        elif outcome is VSCodeExtensionsOutcome.CLI_UNAVAILABLE:
            # Recoverable: VS Code is not (yet) installed on this machine.
            # Leave state untouched so the NEXT bootstrap re-checks once the
            # user installs VS Code. Do NOT mark failure (would trigger the
            # 3-week cooldown) and do NOT record success in setup_steps
            # (would skip forever until --force-setup).
            logger.info(
                '  VS Code extensions deferred - will retry on next bootstrap'
            )
        else:  # VSCodeExtensionsOutcome.FAILED
            ctx.state['vscode_extensions_failed'] = True
            ctx.state['vscode_extensions_last_attempt'] = (
                datetime.now().isoformat()
            )
            logger.info(
                '  VS Code extension installation incomplete - will retry in 3 weeks'
            )
            logger.info('    (or use --force-setup to retry immediately)')
        sys.stdout.flush()
        logger.log_phase_header('SETUP - VSCODE EXTENSIONS - END')
        logger.debug(f'  ⏱  VS Code extensions: {time.monotonic() - t0:.1f}s')
