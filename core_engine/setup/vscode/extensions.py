"""VS Code extension management mixin for the XC-CE environment setup.

Extracted from environment_setup.py to keep that file focused on
orchestration. This mixin provides all VS Code extension-related methods
that can be mixed into
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.

Methods provided
----------------
- :meth:`_check_vscode_extensions_changed` - hash-based change detection
- :meth:`_update_vscode_extensions_hash`   - persist the current hash to state
- :meth:`_install_vscode_extensions`       - merge configs and run installs

Note
----
``generate_vscode_config`` is implemented in
``setup/vscode/config_generation.py`` to keep extension installation and
configuration generation concerns separated.
"""

from __future__ import annotations

import traceback
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from xc_ce_utils.core_engine.adapters.dev_tooling.adapter import (
    create_vscode_extensions_installer,
)
from xc_ce_utils.rb_logger import logger


class VSCodeExtensionsOutcome(Enum):
    """Tri-state result from :meth:`VSCodeSetupMixin._install_vscode_extensions`.

    ``INSTALLED``
        Real success - extensions installed or already present. The phase
        records ``setup_steps["vscode_extensions"]`` so subsequent bootstraps
        skip the step until ``extensions.json`` changes or ``--force-setup``
        is used.

    ``CLI_UNAVAILABLE``
        VS Code CLI (``code`` / ``code.cmd``) not found on PATH. This is a
        recoverable, environment-level issue - the user will install VS Code
        later. The phase MUST leave state untouched so the next bootstrap
        re-checks. Do NOT trigger the failure cooldown.

    ``FAILED``
        Hard failure (one or more extensions failed to install, import
        error, unexpected exception). Triggers the 3-week cooldown.
    """

    INSTALLED = 'installed'
    CLI_UNAVAILABLE = 'cli_unavailable'
    FAILED = 'failed'


class VSCodeSetupMixin:
    """Mixin class providing VS Code extension management methods.

    This class is designed to be mixed in with :class:`EnvironmentSetup`.
    It expects the following attributes on the consuming class:

    - ``self.repo_path`` - :class:`~pathlib.Path` to the repository root
    - ``self._calculate_file_hash(path)`` - returns a hex-string SHA-256 hash
    """

    def _check_vscode_extensions_changed(
        self, extensions_file: Path, state: Dict[str, Any]
    ) -> bool:
        """Return ``True`` when ``extensions.json`` differs from the stored hash."""
        if not extensions_file.exists():
            return False

        current_hash = self._calculate_file_hash(extensions_file)  # type: ignore[attr-defined]
        previous_hash = state.get('vscode_extensions_hash')

        if previous_hash is None:
            logger.debug('No previous VS Code extensions hash found')
            return True

        return current_hash != previous_hash

    def _update_vscode_extensions_hash(self, extensions_file: Path, state: Dict[str, Any]) -> None:
        """Write the current ``extensions.json`` hash into *state*."""
        if not extensions_file.exists():
            return

        current_hash = self._calculate_file_hash(extensions_file)  # type: ignore[attr-defined]
        state['vscode_extensions_hash'] = current_hash
        logger.debug(f'Updated VS Code extensions hash: {current_hash[:16]}...')

    def _install_vscode_extensions(self) -> VSCodeExtensionsOutcome:
        """Merge extension configs and install missing VS Code extensions."""
        try:
            installer = create_vscode_extensions_installer(  # type: ignore[attr-defined]
                repo_root=self.repo_path
            )
            return self._install_with_installer(installer)
        except ImportError as exc:
            logger.error(f'Could not import VS Code extension installer: {exc}')
            logger.debug(traceback.format_exc())
            return VSCodeExtensionsOutcome.FAILED
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.error(f'Failed to install VS Code extensions: {exc}')
            logger.debug(traceback.format_exc())
            return VSCodeExtensionsOutcome.FAILED

    @staticmethod
    def _install_with_installer(installer) -> VSCodeExtensionsOutcome:
        """Execute extension verification using a prepared installer."""
        logger.info('Merging base and project VS Code extensions...')
        if not installer.copy_extensions_config():
            logger.warning('Failed to create extensions.json - skipping extension analysis')
            return VSCodeExtensionsOutcome.CLI_UNAVAILABLE

        logger.info('Extensions configuration created successfully')

        logger.info('Checking for VS Code CLI availability...')
        if not installer.check_vscode_cli_available():
            logger.warning('VS Code CLI not available - extensions analysis will be deferred')
            logger.info(' To enable extension analysis:')
            logger.info('   1. Install VS Code from https://code.visualstudio.com')
            logger.info("   2. Run 'Shell Command: Install code command in PATH' from VS Code")
            logger.info('   3. Or add VS Code to your system PATH manually')
            logger.info(" The next './build.ps1' will re-check automatically.")
            return VSCodeExtensionsOutcome.CLI_UNAVAILABLE

        logger.info('VS Code CLI detected - proceeding with extension analysis...')
        installed, already_installed, failed = installer.install_missing_extensions()

        if failed > 0:
            logger.warning(f'Some extensions failed to analyze ({failed} failed)')
            return VSCodeExtensionsOutcome.FAILED

        logger.info(f'Extension analysis complete (total recommended: {already_installed})')

        return VSCodeExtensionsOutcome.INSTALLED

    # VS Code project config generation is provided by
    # VSCodeConfigGenerationMixin (setup/vscode/config_generation.py).
