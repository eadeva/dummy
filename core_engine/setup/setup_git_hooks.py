"""
Git hooks setup mixin for the XC-CE environment setup.

Extracted from ``environment_setup.py`` to keep that file focused on
orchestration.  This mixin provides all git-hooks-related methods that
can be mixed into
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.

Methods provided
----------------
- :meth:`_get_git_hooks_state`    - read timestamp + hash from git config
- :meth:`_save_git_hooks_state`   - persist timestamp + hash to git config
- :meth:`_setup_git_hooks`         - copy + configure hooks when changed
- :meth:`_calculate_directory_hash` - recursive SHA-256 of a directory tree
- :meth:`_has_directory_changed`  - compare tree hash against stored value
- :meth:`_save_directory_hash`    - persist current tree hash to a file

Note
----
``_has_directory_changed`` and ``_save_directory_hash`` depend on
``_get_hash_file_path`` which is defined in
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup` and
resolved at runtime via ``self``.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from xc_ce_utils.core_engine.adapters.dev_tooling.adapter import (
    configure_git_hooks,
)
from xc_ce_utils.rb_logger import logger


class GitHooksSetupMixin:
    """
    Mixin class providing git hooks management methods.

    Intended to be used only as part of
    :class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.
    """

    # ------------------------------------------------------------------
    # Git config state persistence
    # ------------------------------------------------------------------

    def _get_git_hooks_state(self) -> tuple[str | None, str | None]:
        """
        Get git hooks state from repository's git config.

        Returns:
            Tuple of (timestamp, source_hash) or (None, None) if not found
        """
        try:
            # Get timestamp
            result = subprocess.run(
                ['git', 'config', '--local', 'xc-ce.hooksSetup'],
                cwd=self.repo_path,  # type: ignore[attr-defined]
                capture_output=True,
                text=True,
                check=False,
            )
            timestamp = (
                result.stdout.strip() if result.returncode == 0 else None
            )

            # Get hash
            result = subprocess.run(
                ['git', 'config', '--local', 'xc-ce.hooksHash'],
                cwd=self.repo_path,  # type: ignore[attr-defined]
                capture_output=True,
                text=True,
                check=False,
            )
            hash_value = (
                result.stdout.strip() if result.returncode == 0 else None
            )

            return timestamp, hash_value
        except Exception as e:
            logger.debug(f'Failed to read git hooks state from git config: {e}')
            return None, None

    def _save_git_hooks_state(self, source_hash: str) -> None:
        """
        Save git hooks state to repository's git config.

        Args:
            source_hash: Hash of source hooks directory

        Raises:
            SystemExit: If git config fails (non-git repository)
        """
        try:
            timestamp = datetime.now().isoformat()

            # Save timestamp
            subprocess.run(
                ['git', 'config', '--local', 'xc-ce.hooksSetup', timestamp],
                cwd=self.repo_path,  # type: ignore[attr-defined]
                check=True,
            )

            # Save hash
            subprocess.run(
                ['git', 'config', '--local', 'xc-ce.hooksHash', source_hash],
                cwd=self.repo_path,  # type: ignore[attr-defined]
                check=True,
            )

            logger.debug(
                f'Saved git hooks state to git config (hash: {source_hash[:8]}...)'
            )
        except subprocess.CalledProcessError as e:
            logger.error('Git hooks require git repository')
            logger.error(f'Failed to save git hooks state: {e}')
            sys.exit(1)
        except Exception as e:
            logger.error(f'Unexpected error saving git hooks state: {e}')
            sys.exit(1)

    # ------------------------------------------------------------------
    # Directory hash helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_directory_hash(dir_path: Path) -> str:
        """
        Calculate SHA-256 hash of all files in a directory tree (recursive).

        Args:
            dir_path: Root directory to hash

        Returns:
            Hex digest of the combined hash, or ``""`` if the directory
            does not exist.
        """
        if not dir_path.exists():
            return ''

        sha256_hash = hashlib.sha256()

        # Sorted for deterministic ordering
        for file_path in sorted(dir_path.rglob('*')):
            if file_path.is_file():
                sha256_hash.update(
                    str(file_path.relative_to(dir_path)).encode()
                )
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b''):
                        sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def _has_directory_changed(
        self, dir_path: Path, hash_file_name: str
    ) -> bool:
        """
        Check if directory contents have changed since last check.

        Args:
            dir_path: Directory path
            hash_file_name: Name for hash tracking file

        Returns:
            True if directory has changed or no previous hash is stored
        """
        hash_file = self._get_hash_file_path(hash_file_name)  # type: ignore[attr-defined]
        current_hash = self._calculate_directory_hash(dir_path)

        if not hash_file.exists():
            return True

        try:
            previous_hash = hash_file.read_text(encoding='utf-8').strip()
            return current_hash != previous_hash
        except Exception as e:
            logger.debug(f'Error reading hash file {hash_file}: {e}')
            return True

    def _save_directory_hash(self, dir_path: Path, hash_file_name: str) -> None:
        """
        Persist the current directory hash for future comparison.

        Args:
            dir_path: Directory path
            hash_file_name: Name for hash tracking file
        """
        hash_file = self._get_hash_file_path(hash_file_name)  # type: ignore[attr-defined]
        current_hash = self._calculate_directory_hash(dir_path)

        try:
            hash_file.write_text(current_hash, encoding='utf-8')
            logger.debug(
                f'Saved hash for {dir_path.name}: {current_hash[:16]}...'
            )
        except Exception as e:
            logger.warning(f'Failed to save hash for {dir_path.name}: {e}')

    # ------------------------------------------------------------------
    # Git hooks installation
    # ------------------------------------------------------------------

    def _setup_git_hooks(
        self,
        config: Dict[str, Any],
        *,
        include_maintainer_steps: bool = True,
        force: bool = False,
    ) -> bool:
        """
        Setup Git hooks with hash-based change detection.

        Only copies hooks when the source directory has changed since the
        last successful setup.

        Args:
            config: Configuration dictionary
            include_maintainer_steps: Whether to regenerate committed hook configs
            force: Whether to bypass hash-based change detection

        Returns:
            True if successful, False on error
        """
        try:
            return self._setup_git_hooks_impl(
                config,
                include_maintainer_steps=include_maintainer_steps,
                force=force,
            )

        except Exception as e:
            logger.error(f'Failed to setup Git hooks: {e}')
            logger.error(traceback.format_exc())
            return False

    def _setup_git_hooks_impl(
        self,
        config: Dict[str, Any],
        *,
        include_maintainer_steps: bool,
        force: bool,
    ) -> bool:
        """Execute git-hooks setup workflow without outer exception wrapping."""
        # Skip in CI environment
        if (
            os.environ.get('GITHUB_ACTIONS') == 'true'
            or os.environ.get('CI') == 'true'
        ):
            logger.debug('Skipping Git hooks setup in CI environment')
            return True

        xc_ce_utils_path = Path(__file__).resolve().parent.parent.parent
        git_hooks_root = xc_ce_utils_path / 'git_hooks'
        template_file = (
            git_hooks_root / 'templates' / 'pre-commit' / 'base.yaml'
        )
        checks_dir = git_hooks_root / 'checks'

        if not template_file.exists() or not checks_dir.exists():
            logger.warning(
                f'pre-commit assets not found (template={template_file.exists()}, '
                f'checks={checks_dir.exists()})'
            )
            return False

        # Hash both template and checks so any change re-triggers install.
        source_hook_dir = git_hooks_root
        hash_file_name = 'git_hooks'
        pre_commit_cfg = self.repo_path / '.pre-commit-config.yaml'  # type: ignore[attr-defined]
        missing_pre_commit_cfg = (
            include_maintainer_steps and not pre_commit_cfg.exists()
        )
        if (
            not force
            and not self._has_directory_changed(source_hook_dir, hash_file_name)
            and not missing_pre_commit_cfg
        ):
            logger.debug('Git hooks unchanged, skipping setup')
            return True

        if missing_pre_commit_cfg:
            logger.info(
                '.pre-commit-config.yaml is missing; regenerating code-quality configs.'
            )

        logger.info('Git hooks have changed, updating...')

        jira_project_key = config.get('JIRA_PROJECT', '')
        configure_git_hooks(
            jira_project_key,
            regenerate_code_quality_configs=include_maintainer_steps,
        )

        self._save_directory_hash(source_hook_dir, hash_file_name)

        return True
