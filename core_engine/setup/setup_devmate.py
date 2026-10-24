"""
DEVMATE PAT setup mixin for the XC-CE environment setup.

Extracted from environment_setup.py to keep that file focused on
orchestration.  This mixin provides all DEVMATE-related methods that
can be mixed into :class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.

Methods provided
----------------
- :meth:`_is_devmate_check_needed` - staleness check for the validation timer
- :meth:`_setup_devmate_pat`       - full PAT validation / prompt workflow
- :meth:`_warn_vscode_restart_if_needed` - VS Code restart advisory
- :meth:`_close_vscode`            - forcibly terminate VS Code processes
"""

from __future__ import annotations

import os
import platform
import subprocess
import traceback
from datetime import datetime
from typing import Any, Dict

from xc_ce_utils.core_engine.adapters.dev_tooling.adapter import (
    create_mcp_server_configurator,
)
from xc_ce_utils.rb_logger import logger


class DevmateSetupMixin:
    """
    Mixin class providing DEVMATE PAT lifecycle methods.

    This class is designed to be mixed in with :class:`EnvironmentSetup`.
    It expects ``self.repo_path`` to be available on the consuming class.
    """

    # ------------------------------------------------------------------
    # Staleness helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_devmate_check_needed(state: Dict[str, Any], weeks: int = 5) -> bool:
        """
        Return ``True`` when DEVMATE PAT validation is due (older than *weeks*).

        Args:
            state: Current setup state dictionary
            weeks: Staleness threshold in weeks (default: 5)
        """
        last_check = state.get('last_devmate_check')
        if last_check is None:
            return True

        try:
            last_check_date = datetime.fromisoformat(last_check)
            age = datetime.now() - last_check_date
            return age.days > (weeks * 7)
        except Exception as exc:
            logger.debug(f'Error parsing DEVMATE_PAT check date: {exc}')
            return True

    # ------------------------------------------------------------------
    # PAT setup workflow
    # ------------------------------------------------------------------

    def _setup_devmate_pat(self) -> bool:
        """
        Setup and validate the ``DEVMATE_PAT`` environment variable.

        Workflow
        --------
        1. Check ``DEVMATE_PAT`` in the current environment.
        2. If missing, retrieve from keyring.
        3. Validate whichever token was found against the Devmate API.
        4. If invalid / missing, prompt the user for a new token.
        5. Store the valid token in keyring and persist it as a
           system-level environment variable.

        Returns:
            ``True`` if the token is configured and valid, ``False`` otherwise.
        """
        try:
            mcp_config = create_mcp_server_configurator(  # type: ignore[attr-defined]
                repo_root=self.repo_path
            )
            return self._setup_devmate_pat_with_config(mcp_config)
        except Exception as exc:
            logger.error(f'Failed to setup DEVMATE_PAT: {exc}')
            logger.debug(traceback.format_exc())
            return False

    def _setup_devmate_pat_with_config(self, mcp_config: Any) -> bool:
        """Execute PAT lookup, validation, and persistence using a configurator."""
        current_pat = os.environ.get('DEVMATE_PAT')

        if current_pat:
            logger.debug('DEVMATE_PAT found in environment, validating...')
            if mcp_config.validate_devmate_pat(current_pat):
                logger.debug('Existing DEVMATE_PAT is valid')
                return True

            logger.warning('DEVMATE_PAT in environment is invalid - requesting new token')

        logger.info('DEVMATE_PAT not found or invalid - prompting for new token...')
        new_pat = mcp_config.prompt_and_store_devmate_pat()
        if not new_pat:
            logger.info('DEVMATE_PAT setup cancelled or failed')
            return False

        logger.debug('New DEVMATE_PAT provided successfully')
        return self._persist_pat_and_warn(
            mcp_config,
            pat=new_pat,
            pat_was_changed=True,
        )

    def _persist_pat_and_warn(
        self,
        mcp_config: Any,
        *,
        pat: str,
        pat_was_changed: bool,
    ) -> bool:
        """Persist PAT when possible and emit restart guidance if needed."""
        if mcp_config.setup_persistent_devmate_pat(pat):
            logger.debug('DEVMATE_PAT set as persistent environment variable')
        else:
            logger.warning('Failed to persist DEVMATE_PAT - falling back to in-process only')
            os.environ['DEVMATE_PAT'] = pat

        self._warn_vscode_restart_if_needed(pat_was_changed=pat_was_changed)
        return True

    # ------------------------------------------------------------------
    # VS Code restart advisory
    # ------------------------------------------------------------------

    @staticmethod
    def _warn_vscode_restart_if_needed(*, pat_was_changed: bool) -> None:
        """
        Warn the user to restart VS Code when ``DEVMATE_PAT`` was changed.

        Args:
            pat_was_changed: ``True`` when the token was newly set or modified.
        """
        if not pat_was_changed:
            return

        is_vscode_terminal = (
            os.environ.get('TERM_PROGRAM') == 'vscode'
            or os.environ.get('VSCODE_PID') is not None
            or os.environ.get('VSCODE_GIT_ASKPASS_NODE') is not None
        )

        if is_vscode_terminal:
            logger.warning('  DEVMATE_PAT was set/changed')
            logger.warning(
                '  VS Code is running - RESTART VS Code for MCP servers to pick up the new token'
            )
            logger.warning('  Close all VS Code windows and reopen them to apply the changes')
        else:
            logger.info(
                'DEVMATE_PAT was set/changed - restart any running VS Code instances to apply'
            )

    @staticmethod
    def _close_vscode() -> None:
        """Forcibly terminate all running VS Code processes."""
        try:
            if platform.system() == 'Windows':
                for exe in ('Code.exe', 'Code - Insiders.exe'):
                    subprocess.run(
                        ['taskkill', '/F', '/IM', exe],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
            else:
                subprocess.run(
                    ['pkill', '-f', 'code'],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
        except Exception as exc:
            logger.debug(f'Failed to close VS Code: {exc}')
