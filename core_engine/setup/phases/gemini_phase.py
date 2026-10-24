"""Gemini CLI environment-variable setup phase."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from datetime import datetime

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci
from xc_ce_utils.rb_logger import logger


class GeminiCliPhase(SetupPhase):
    """Validate / configure the ``GOOGLE_CLOUD_PROJECT`` environment variable for Gemini CLI."""

    name = 'gemini_cli'

    def should_run(self, ctx: SetupContext) -> bool:
        """Skip in CI, otherwise run if GOOGLE_CLOUD_PROJECT is not correctly configured."""
        if is_running_in_ci():
            return False

        current_val = os.environ.get('GOOGLE_CLOUD_PROJECT')
        return current_val != 'rbprj-100397'

    def run(self, ctx: SetupContext) -> None:
        """Configure GOOGLE_CLOUD_PROJECT and instruct the user on setup."""
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - GEMINI CLI')
        logger.progress('Configuring GOOGLE_CLOUD_PROJECT for Gemini CLI...')

        target_value = 'rbprj-100397'
        success = False

        try:
            if platform.system() == 'Windows':
                # Windows: Set in User registry
                cmd = [
                    'powershell',
                    '-NoProfile',
                    '-Command',
                    f"[System.Environment]::SetEnvironmentVariable('GOOGLE_CLOUD_PROJECT', '{target_value}', 'User')",
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10, check=False
                )

                if result.returncode == 0:
                    os.environ['GOOGLE_CLOUD_PROJECT'] = target_value
                    success = True
                else:
                    logger.error(f'Failed to set Windows environment variable: {result.stderr}')
            else:
                # Linux/Mac: Add to shell config
                shell_rc = Path.home() / '.bashrc'
                if not shell_rc.exists():
                    shell_rc = Path.home() / '.profile'
                    if not shell_rc.exists():
                        shell_rc = Path.home() / '.bashrc'

                export_line = f'\nexport GOOGLE_CLOUD_PROJECT="{target_value}"\n'

                with open(shell_rc, 'a') as f:
                    f.write(export_line)

                os.environ['GOOGLE_CLOUD_PROJECT'] = target_value
                success = True

        except Exception as e:
            logger.error(f'Failed to setup persistent GOOGLE_CLOUD_PROJECT: {e}')

        if success:
            logger.success(' GOOGLE_CLOUD_PROJECT environment variable configured permanently')
            self._print_gemini_instructions()
            ctx.state['setup_steps']['gemini_cli'] = datetime.now().isoformat()
        else:
            logger.warning(
                'Failed to persist GOOGLE_CLOUD_PROJECT - falling back to in-process only'
            )
            os.environ['GOOGLE_CLOUD_PROJECT'] = target_value

        logger.log_phase_header('SETUP - GEMINI CLI - END')
        logger.debug(f'  ⏱  Gemini CLI Setup: {time.monotonic() - t0:.1f}s')

    @staticmethod
    def _print_gemini_instructions() -> None:
        """Print clear instructions for installing and running Gemini CLI."""
        logger.info('')
        logger.info('=' * 80)
        logger.info(' GEMINI CLI SYSTEM REQUISITES & MANUAL SETUP')
        logger.info('=' * 80)
        logger.info('  To start using the Gemini CLI on your machine, please ensure:')
        logger.info('    1. Additional Tools:')
        logger.note('       node.js (IT Service Portal)')
        logger.note('       PX by BD running and active')
        logger.info('    2. Env Variables and VS Code proxy settings:')
        logger.note('       HTTP_PROXY=http://127.0.0.1:3128')
        logger.note('       HTTPS_PROXY=http://127.0.0.1:3128')
        logger.info('')
        logger.info('  Complete instructions, download links, and setup details are on Docupedia:')
        logger.note(
            '    https://inside-docupedia.bosch.com/confluence2/spaces/AgenticAI/pages/976816515/Tooling'
        )
        logger.info('')
        logger.info('  Tip: Once Node.js and PX are ready, restart your PowerShell and type:')
        logger.note('    gemini')
        logger.info('=' * 80)
        logger.info('')
