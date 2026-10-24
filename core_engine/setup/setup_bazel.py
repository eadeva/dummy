"""
Bazel cache setup mixin for the XC-CE environment setup.

Extracted from ``environment_setup.py`` to keep that file focused on
orchestration.  This mixin provides all Bazel-related methods that
can be mixed into
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.

Methods provided
----------------
- :meth:`_ensure_bazel_disk_cache_path` - validate/migrate global ~/.bazelrc disk_cache path
- :meth:`_notify_old_bazel_cache`       - one-shot user notification about old cache location
- :meth:`_format_size`                  - static helper: bytes to human-readable string
- :meth:`setup_bazel_cache`             - write project-level .bazelrc.cache + .bazelrc.auth

Note
----
This mixin accesses ``self.repo_path`` which is defined in
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.
"""

from __future__ import annotations

import base64
import os
import platform
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from xc_ce_utils.auth import get_auth_manager
from xc_ce_utils.rb_logger import logger

CORRECT_DISK_CACHE_PATH = '~/.bazel_cache'
BYTES_PER_KIB = 1024.0
OLD_WINDOWS_CACHE_PATHS = {'C:\\bazel_cache', 'C:/bazel_cache'}


class BazelSetupMixin:
    """
    Mixin class providing Bazel cache lifecycle methods.

    This class is designed to be mixed in with :class:`EnvironmentSetup`.
    It expects the following attributes on the consuming class:

    - ``self.repo_path`` - :class:`~pathlib.Path` to the repository root
    """

    # ------------------------------------------------------------------
    # Disk cache helpers
    # ------------------------------------------------------------------

    def _ensure_bazel_disk_cache_path(self, state: Dict[str, Any]) -> None:
        """
        Ensure Bazel disk cache uses correct user-specific path.

        Validates global ~/.bazelrc has correct disk_cache path (~/.bazel_cache).
        If old problematic path (C:\\bazel_cache) or custom path is detected,
        updates configuration and notifies user once.

        This runs ALWAYS when Bazel is enabled (independent of project setup needs)
        to ensure all developers get correct cache path without permission issues.

        Args:
            state: Setup state dict to track validation and notification
        """
        global_bazelrc = Path.home() / '.bazelrc'
        correct_path = CORRECT_DISK_CACHE_PATH

        # Fast path: if already validated to correct path, skip
        if state.get('bazel_disk_cache_path') == correct_path:
            logger.debug('Disk cache path already validated to correct path')
            return

        # Read current configuration
        current_disk_cache = None
        if global_bazelrc.exists():
            logger.debug(f'Found existing {global_bazelrc}')
            with open(global_bazelrc, 'r', encoding='utf-8') as f:
                content = f.read()
                # Match: build --disk_cache=<path>
                match = re.search(r'build\s+--disk_cache=([^\s]+)', content)
                if match:
                    current_disk_cache = match.group(1)
                    logger.debug(
                        f'Detected current disk_cache path: {current_disk_cache}'
                    )
                else:
                    logger.debug('No disk_cache path found in .bazelrc')
        else:
            logger.debug(f'{global_bazelrc} does not exist yet')

        # Determine if migration needed
        needs_migration = (
            current_disk_cache and current_disk_cache != correct_path
        )
        logger.debug(f'Migration needed: {needs_migration}')

        if needs_migration:
            # Update to correct path
            old_path = current_disk_cache
            with open(global_bazelrc, 'r', encoding='utf-8') as f:
                content = f.read()

            # Replace old disk_cache path with correct one
            updated_content = re.sub(
                r'(build\s+--disk_cache=)([^\s]+)',
                rf'\1{correct_path}',
                content,
            )

            with open(global_bazelrc, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            logger.info(
                f'Updated Bazel disk cache path: {old_path} → {correct_path}'
            )

            # Notify user once about old cache (unless already notified)
            if not state.get('bazel_disk_cache_notified'):
                self._notify_old_bazel_cache(old_path)
                state['bazel_disk_cache_notified'] = True

        elif not current_disk_cache:
            # No disk cache configured, add it
            logger.info(f'No disk cache configured yet, adding: {correct_path}')
            # Create .bazelrc if it doesn't exist
            if not global_bazelrc.exists():
                global_bazelrc.parent.mkdir(parents=True, exist_ok=True)
                logger.debug(f'Created directory for {global_bazelrc}')

            with open(global_bazelrc, 'a', encoding='utf-8') as f:
                f.write('\n# XC-CE Utils Bazel Disk Cache\n')
                f.write(f'build --disk_cache={correct_path}\n')
            logger.info(f'Configured Bazel disk cache: {correct_path}')

        # Update state to track validated path
        state['bazel_disk_cache_path'] = correct_path
        logger.debug(f'Updated state: bazel_disk_cache_path = {correct_path}')

    def _notify_old_bazel_cache(self, old_path: str) -> None:
        """
        Notify user about old Bazel disk cache and suggest cleanup.

        Provides detailed guidance based on old path:
        - C:\\bazel_cache: Explain multi-user permission issues
        - Other paths: Generic space-saving notification

        Args:
            old_path: The old disk cache path being migrated from
        """
        # Expand path for size calculation
        expanded_path = Path(old_path.replace('~', str(Path.home())))

        # Calculate cache size if accessible
        cache_size_str = 'unknown size'
        try:
            if expanded_path.exists():
                total_size = sum(
                    f.stat().st_size
                    for f in expanded_path.rglob('*')
                    if f.is_file()
                )
                cache_size_str = self._format_size(total_size)
        except Exception:
            pass  # Size calculation is best-effort

        # Build notification message
        logger.warning('\n' + '=' * 70)
        logger.warning('  BAZEL DISK CACHE PATH CHANGED')
        logger.warning('=' * 70)

        if old_path in OLD_WINDOWS_CACHE_PATHS:
            logger.warning(
                f'\nYour old Bazel disk cache was at: {old_path}\n'
                f'This location causes permission issues on multi-user machines.\n'
                f'\nNew cache location: ~/.bazel_cache (user-specific)\n'
                f'\nOld cache size: {cache_size_str}\n'
            )
        else:
            logger.warning(
                f'\nYour old Bazel disk cache was at: {old_path}\n'
                f'New cache location: ~/.bazel_cache\n'
                f'\nOld cache size: {cache_size_str}\n'
            )

        logger.warning('To free up disk space, you can delete the old cache:')
        if os.name == 'nt':  # Windows
            logger.warning(f"  Remove-Item -Recurse -Force '{expanded_path}'")
        else:  # Unix/Linux
            logger.warning(f"  rm -rf '{expanded_path}'")

        logger.warning(
            '\nThe new cache will rebuild automatically during builds.'
        )
        logger.warning('=' * 70 + '\n')

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < BYTES_PER_KIB:
                return f'{size_bytes:.1f} {unit}'
            size_bytes /= BYTES_PER_KIB
        return f'{size_bytes:.1f} PB'

    # ------------------------------------------------------------------
    # Remote cache setup
    # ------------------------------------------------------------------

    def setup_bazel_cache(self, config: Dict[str, Any]) -> bool:
        """
        Setup Bazel remote cache configuration (project-level files only).

        Creates project-level .bazelrc.cache and .bazelrc.auth (gitignored, regenerated).

        This method configures Bazel remote cache (Artifactory) for the current project.
        The project-level files contain authentication and are gitignored,
        so they must be regenerated on each machine or when credentials change.

        Note: Global disk cache configuration is handled separately by
        :meth:`_ensure_bazel_disk_cache_path`.

        Cache Configuration Strategy:
        - Remote Cache (Artifactory):
          - Developers: Read-only access (--remote_upload_local_results=false)
          - CI Systems: Read/Write access (auto-detected via CI env vars)
        - Disk Cache (Local):
          - Shared across all projects on the same machine
          - Faster than remote cache (~10ms vs ~500ms)

        Args:
            config: Build configuration dictionary

        Returns:
            True if setup was successful
        """
        bazel_cache_url = self._get_bazel_cache_url(config)
        if not bazel_cache_url:
            return True

        try:
            self._ensure_project_bazelrc_base()
            self._write_project_cache_config(bazel_cache_url)
            self._configure_project_cache_auth(bazel_cache_url)

        except Exception as e:
            logger.error(f'Failed to setup Bazel cache: {e}')
            return False

        logger.success(f'Bazel cache configured: {bazel_cache_url}')
        logger.info(
            'Remote cache mode: Read-only for developers (CI will upload automatically)'
        )
        return True

    @staticmethod
    def _get_bazel_cache_url(config: Dict[str, Any]) -> Optional[str]:
        """Read remote cache URL and emit user guidance when absent."""
        bazel_cache_url = config.get('BAZEL_REMOTE_CACHE_URL')
        if bazel_cache_url:
            return str(bazel_cache_url)

        logger.info(
            'BAZEL_REMOTE_CACHE_URL not configured - skipping remote cache setup'
        )
        logger.info(
            'Bazel will work normally, only local disk cache will be available'
        )
        return None

    def _project_path(self, filename: str) -> Path:
        """Return project-local Bazel config path under repository root."""
        return self.repo_path / filename  # type: ignore[attr-defined]

    def _ensure_project_bazelrc_base(self) -> None:
        """Create or validate base `.bazelrc` import wiring."""
        project_bazelrc_base = self._project_path('.bazelrc')
        if not project_bazelrc_base.exists():
            project_bazelrc_base.write_text(
                self._render_base_config(), encoding='utf-8'
            )
            logger.info(
                f' Base Bazel config created: {project_bazelrc_base.name}'
            )
            logger.info('   (This file should be committed to git)')
            return

        content = project_bazelrc_base.read_text(encoding='utf-8')
        if 'try-import %workspace%/.bazelrc.cache' in content:
            return

        logger.warning(
            f"  {project_bazelrc_base.name} exists but doesn't import .bazelrc.cache"
        )
        logger.info('   Add this line to enable remote cache:')
        logger.info('   try-import %workspace%/.bazelrc.cache')

    @staticmethod
    def _render_base_config() -> str:
        """Render base `.bazelrc` content that imports cache settings."""
        return """# Bazel Configuration
# This file should be checked into git
# Cache-specific settings are in .bazelrc.cache (gitignored)

# Import cache configuration (gitignored, auto-generated)
try-import %workspace%/.bazelrc.cache

# Common build settings
build --incompatible_enable_cc_toolchain_resolution
build --enable_platform_specific_config

# Improved error messages
build --verbose_failures
build --show_timestamps

# Performance settings
build --experimental_reuse_sandbox_directories
build --experimental_inmemory_jdeps_files
build --experimental_inmemory_dotd_files
"""

    def _write_project_cache_config(self, bazel_cache_url: str) -> None:
        """Write project-local `.bazelrc.cache` remote cache config."""
        project_bazelrc = self._project_path('.bazelrc.cache')
        project_bazelrc.write_text(
            self._render_project_cache_config(bazel_cache_url), encoding='utf-8'
        )
        logger.info(f' Project cache config created: {project_bazelrc.name}')

    @staticmethod
    def _render_project_cache_config(bazel_cache_url: str) -> str:
        """Render project-level cache config content."""
        return f"""# Bazel Cache Configuration
# This file configures remote HTTP cache using Artifactory
# AUTO-GENERATED by environment_setup.py - DO NOT EDIT MANUALLY

# Remote HTTP cache using Artifactory
build --remote_cache={bazel_cache_url}

# Default: Read-only mode for developers (download only, no uploads)
# CI systems override this flag programmatically to enable uploads
build --remote_upload_local_results=false
build --remote_timeout=60

# Authentication via .bazelrc.auth file
try-import %workspace%/.bazelrc.auth

# Cache settings
build --experimental_repository_cache_hardlinks
build --experimental_guard_against_concurrent_changes
"""

    def _configure_project_cache_auth(self, bazel_cache_url: str) -> None:
        """Configure auth header file when credentials are available."""
        username, password = self._resolve_cache_credentials(bazel_cache_url)
        if not username or not password:
            self._log_missing_credentials()
            return

        project_bazelrc_auth = self._project_path('.bazelrc.auth')
        credentials_base64 = self._encode_basic_auth(username, password)
        auth_config = f"""# Bazel Remote Cache Authentication
# AUTO-GENERATED - DO NOT COMMIT THIS FILE
build --remote_header=\"Authorization=Basic {credentials_base64}\"
"""
        project_bazelrc_auth.write_text(auth_config, encoding='utf-8')

        if platform.system() != 'Windows':
            os.chmod(project_bazelrc_auth, 0o600)

        logger.info(f' Authentication configured: {project_bazelrc_auth.name}')
        logger.info(f'   User: {username}')

    @staticmethod
    def _resolve_cache_credentials(
        bazel_cache_url: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve cache credentials from CI environment or keyring."""
        username = os.environ.get('TECHNICAL_USER_ID')
        password = os.environ.get('TECHNICAL_USER_PASSWORD')
        if username and password:
            return username, password

        logger.info('Checking keyring for Bazel cache credentials...')
        return get_auth_manager().get_credentials(bazel_cache_url)

    @staticmethod
    def _encode_basic_auth(username: str, password: str) -> str:
        """Encode Basic auth header value for Bazel remote cache access."""
        credentials_string = f'{username}:{password}'
        credentials_bytes = credentials_string.encode('ascii')
        return base64.b64encode(credentials_bytes).decode('ascii')

    @staticmethod
    def _log_missing_credentials() -> None:
        """Log guidance when credentials are missing."""
        logger.warning('  Bazel cache credentials not found')
        logger.info('Credentials can be provided via:')
        logger.info(
            '  - Environment (CI): TECHNICAL_USER_ID / TECHNICAL_USER_PASSWORD'
        )
        logger.info(
            '  - Keyring: Run Artifactory credential validation to store credentials'
        )
