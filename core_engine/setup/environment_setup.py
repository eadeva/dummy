"""
Environment Setup for Standalone XC-CE Builder

This module handles one-time setup of required tools and configurations
when running the standalone executable.
"""

import atexit
import hashlib
import importlib
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from filelock import FileLock, Timeout
from packaging.version import Version

from xc_ce_utils.auth import get_auth_manager
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_builds_root,
    get_logs_root,
    load_entry_config,
    read_project_name_from_main_config,
)
from xc_ce_utils.core_engine.setup.setup_bazel import BazelSetupMixin
from xc_ce_utils.core_engine.setup.setup_clang import ClangSetupMixin
from xc_ce_utils.core_engine.setup.setup_conan import ConanSetupMixin
from xc_ce_utils.core_engine.setup.setup_devmate import DevmateSetupMixin
from xc_ce_utils.core_engine.setup.setup_git_hooks import GitHooksSetupMixin
from xc_ce_utils.core_engine.setup.vscode import (
    VSCodeConfigGenerationMixin,
    VSCodeExtensionsOutcome,
    VSCodeSetupMixin,
)
from xc_ce_utils.global_modules.aux_helper import export_to_github_env

# Import logger from parent package
from xc_ce_utils.rb_logger import logger
from xc_ce_utils.utils.version import version_manager

HTTP_STATUS_OK = 200


class EnvironmentSetup(
    ConanSetupMixin,
    BazelSetupMixin,
    DevmateSetupMixin,
    VSCodeConfigGenerationMixin,
    VSCodeSetupMixin,
    GitHooksSetupMixin,
    ClangSetupMixin,
):
    """Handles environment setup for standalone XC-CE Builder."""

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize environment setup.

        Args:
            repo_path: Path to the repository (defaults to current working directory)
        """
        self.repo_path = repo_path or Path.cwd()
        self.project_folder = self._get_project_folder()
        self.conan_home = self.project_folder / '.conan'
        os.environ['CONAN_HOME'] = str(self.conan_home)
        self.setup_marker_file = (
            self.project_folder / '.xc_ce_builder_setup_complete'
        )
        self.setup_state_file = self.project_folder / '.xc_ce_setup_state.json'
        self.lock_file_path = self.project_folder / '.xc_ce_setup.lock'
        self.lock = None

        # Register cleanup handler for lock release on exit/cancellation
        atexit.register(self._release_lock)

    @staticmethod
    def _compute_project_folder(repo_path: Path) -> Path:
        """
        Compute the versioned project folder path from a repo path.
        Shared by :meth:`_get_project_folder` and :meth:`ensure_conan_env`
        so the logic is never duplicated.
        """
        # Resolve project name through the central config loader so the
        # only hardcoded path is the main_conf.yml entry point.
        project_name = read_project_name_from_main_config(repo_path)

        version_suffix = version_manager.get_major_version_suffix()
        versioned_project_name = f'{project_name}_xc-ce-utils_{version_suffix}'

        if os.environ.get('GITHUB_ACTIONS') == 'true':
            if platform.system() == 'Windows':
                marker_dir = Path(f'C:\\workflows\\{versioned_project_name}')
            else:
                marker_dir = Path(f'/tmp/workflows/{versioned_project_name}')
        else:
            marker_dir = Path.home() / f'.{versioned_project_name}'

        marker_dir.mkdir(parents=True, exist_ok=True)
        return marker_dir

    def _get_project_name_from_config(self) -> str:
        """Read project name from project configuration (via central loader)."""
        return read_project_name_from_main_config(self.repo_path)

    def _get_project_folder(self) -> Path:
        """Get the directory for setup markers with major version suffix."""
        return EnvironmentSetup._compute_project_folder(self.repo_path)

    @classmethod
    def ensure_conan_env(cls, repo_path: Path) -> None:
        """
        Ensure ``CONAN_HOME`` and related env vars are initialised early —
        before any :class:`EnvironmentSetup` instance is created.

        Safe to call multiple times; exits immediately if ``CONAN_HOME`` is
        already present in the environment (e.g. already exported by CI).
        """
        if 'CONAN_HOME' in os.environ:
            return
        project_folder = cls._compute_project_folder(repo_path)
        conan_home = str(project_folder / '.conan')
        os.environ['CONAN_HOME'] = conan_home
        os.environ['CONAN_USER_HOME'] = conan_home
        os.environ['CONAN_DEFAULT_PROFILE_PATH'] = str(
            Path(conan_home) / 'profiles'
        )
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            export_to_github_env('CONAN_HOME', conan_home)
            export_to_github_env('CONAN_USER_HOME', conan_home)
            export_to_github_env(
                'CONAN_DEFAULT_PROFILE_PATH',
                os.environ['CONAN_DEFAULT_PROFILE_PATH'],
            )
            logger.debug(
                ' Conan environment variables exported to GitHub Actions'
            )
        logger.debug(f' CONAN_HOME initialised: {conan_home}')

    def is_setup_complete(self) -> bool:
        """Check if initial setup has been completed."""
        return self.setup_marker_file.exists()

    def _get_setup_date(self) -> Optional[datetime]:
        """
        Get the date when setup was last completed.

        Returns:
            datetime object or None if setup never completed
        """
        if not self.setup_marker_file.exists():
            return None

        try:
            with open(self.setup_marker_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                date_str = data.get('setup_date')
                if date_str:
                    return datetime.fromisoformat(date_str)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f'Could not read setup date from marker file: {e}')
            # Old format (empty file) - assume very old
            return None

        return None

    def _is_setup_older_than(self, days: int) -> bool:
        """
        Check if setup is older than specified number of days.

        Args:
            days: Number of days to check

        Returns:
            True if setup is older than specified days or never completed
        """
        setup_date = self._get_setup_date()
        if setup_date is None:
            return True

        age = datetime.now() - setup_date
        return age.days > days

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to file to hash

        Returns:
            Hex string of file hash
        """
        if not file_path.exists():
            return ''

        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b''):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # _calculate_directory_hash  → GitHooksSetupMixin (setup_git_hooks.py)
    # _get_git_hooks_state        → GitHooksSetupMixin (setup_git_hooks.py)
    # _save_git_hooks_state       → GitHooksSetupMixin (setup_git_hooks.py)

    def _get_hash_file_path(self, requirements_file: str) -> Path:
        """
        Get path to hash tracking file for a requirements file.

        Args:
            requirements_file: Name of requirements file (e.g., 'python_requirements.txt')

        Returns:
            Path to hash file
        """
        return self.project_folder / f'.{requirements_file}.hash'

    def _has_file_changed(self, file_path: Path, hash_file_name: str) -> bool:
        """
        Check if a file has changed since last installation.

        Args:
            file_path: Path to requirements file
            hash_file_name: Name for hash tracking file

        Returns:
            True if file has changed or is new
        """
        hash_file = self._get_hash_file_path(hash_file_name)
        current_hash = self._calculate_file_hash(file_path)

        if not hash_file.exists():
            # No previous hash - file is new
            return True

        # Read previous hash
        try:
            with open(hash_file, 'r', encoding='utf-8') as f:
                previous_hash = f.read().strip()

            return current_hash != previous_hash
        except (OSError, UnicodeError, ValueError, TypeError) as e:
            logger.debug(f'Error reading hash file {hash_file}: {e}')
            return True

    def _save_file_hash(self, file_path: Path, hash_file_name: str) -> None:
        """
        Save hash of a file for future comparison.

        Args:
            file_path: Path to requirements file
            hash_file_name: Name for hash tracking file
        """
        hash_file = self._get_hash_file_path(hash_file_name)
        current_hash = self._calculate_file_hash(file_path)

        try:
            with open(hash_file, 'w', encoding='utf-8') as f:
                f.write(current_hash)
            logger.debug(
                f'Saved hash for {file_path.name}: {current_hash[:16]}...'
            )
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f'Failed to save hash for {file_path.name}: {e}')

    def mark_setup_complete(self) -> None:
        """Mark setup as complete with current date."""
        try:
            data = {'setup_date': datetime.now().isoformat(), 'version': '1.0'}
            with open(self.setup_marker_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except (OSError, TypeError, ValueError) as e:
            logger.warning(f'Failed to save setup date: {e}')
            # Fallback to old method
            self.setup_marker_file.touch()

    def _acquire_lock(self, timeout: int = 300) -> bool:
        """
        Acquire a file lock to prevent concurrent setup processes.

        Args:
            timeout: Maximum time in seconds to wait for the lock (default: 5 minutes)

        Returns:
            True if lock was acquired, False if timeout or error
        """
        try:
            self.lock = FileLock(str(self.lock_file_path), timeout=timeout)
            logger.debug(
                f'Attempting to acquire setup lock: {self.lock_file_path}'
            )
            self.lock.acquire(timeout=timeout)
            logger.debug('Setup lock acquired successfully')
            return True
        except Timeout:
            logger.warning(
                f'Could not acquire setup lock within {timeout} seconds'
            )
            return False
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            logger.warning(f'Failed to acquire setup lock: {e}')
            return False

    def _release_lock(self) -> None:
        """Release the setup lock if held."""
        if self.lock is not None:
            try:
                self.lock.release()
                logger.debug('Setup lock released')
            except (OSError, RuntimeError, TypeError, ValueError) as e:
                logger.debug(
                    f'Failed to release lock (may already be released): {e}'
                )
            finally:
                self.lock = None

    def _load_setup_state(self) -> Dict[str, Any]:
        """
        Load setup state from central state file.

        Returns:
            Dictionary containing setup state with defaults
        """
        default_state = {
            'version': '2.0',
            'xc_ce_utils_version': version_manager.get_version_string(),
            'last_full_setup': None,
            'last_credential_check': None,
            'last_credential_renewal': None,
            'last_devmate_check': None,
            'conan_settings_hash': None,
            'file_hashes': {},
            'setup_steps': {
                'conan_setup': None,
                'conan_tools': None,
                'git_hooks': None,
                'bazel_cache': None,
                'python_requirements': None,
                'vscode_extensions': None,
            },
            'vscode_extensions_hash': None,
            'bazel_disk_cache_path': None,
            'bazel_disk_cache_notified': False,
        }

        if not self.setup_state_file.exists():
            return default_state

        try:
            with open(self.setup_state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # Merge with defaults to handle version upgrades
                for key, value in default_state.items():
                    if key not in state:
                        state[key] = value
                # Always update xc_ce_utils_version to current
                state['xc_ce_utils_version'] = (
                    version_manager.get_version_string()
                )
                return state
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f'Failed to load setup state: {e}, using defaults')
            return default_state

    def _save_setup_state(self, state: Dict[str, Any]) -> None:
        """
        Save setup state to central state file.

        Args:
            state: Setup state dictionary to save
        """
        try:
            state['version'] = '1.0'
            with open(self.setup_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            logger.debug(f'Setup state saved to {self.setup_state_file}')
        except (OSError, TypeError, ValueError) as e:
            logger.warning(f'Failed to save setup state: {e}')

    def _check_file_hash_changed(
        self, file_path: Path, state: Dict[str, Any]
    ) -> bool:
        """
        Check if a file hash has changed compared to state.

        Args:
            file_path: Path to file to check
            state: Current setup state

        Returns:
            True if file has changed or is new
        """
        if not file_path.exists():
            return False

        file_key = str(file_path.relative_to(self.repo_path))
        current_hash = self._calculate_file_hash(file_path)
        previous_hash = state['file_hashes'].get(file_key)

        return current_hash != previous_hash

    def _update_file_hash(self, file_path: Path, state: Dict[str, Any]) -> None:
        """
        Update file hash in state.

        Args:
            file_path: Path to file
            state: Setup state to update
        """
        if not file_path.exists():
            return

        file_key = str(file_path.relative_to(self.repo_path))
        current_hash = self._calculate_file_hash(file_path)
        state['file_hashes'][file_key] = current_hash
        logger.debug(
            f'Updated hash for {file_path.name}: {current_hash[:16]}...'
        )

    @staticmethod
    def _is_credential_check_needed(
        state: Dict[str, Any], weeks: int = 5
    ) -> bool:
        """
        Check if credential validation is needed (older than specified weeks).

        Args:
            state: Current setup state
            weeks: Number of weeks before re-validation needed

        Returns:
            True if credentials need to be checked
        """
        last_check = state.get('last_credential_check')
        if last_check is None:
            return True

        try:
            last_check_date = datetime.fromisoformat(last_check)
            age = datetime.now() - last_check_date
            return age.days > (weeks * 7)
        except (TypeError, ValueError) as e:
            logger.debug(f'Error parsing credential check date: {e}')
            return True

    @staticmethod
    def _is_credential_renewal_needed(
        state: Dict[str, Any], days: int = 180
    ) -> bool:
        """Check if credential renewal is overdue (default: 180 days / ~6 months).

        Returns False when ``last_credential_renewal`` has never been set
        (first-time setup is handled by the regular credential check).
        """
        last_renewal = state.get('last_credential_renewal')
        if last_renewal is None:
            return False
        try:
            return (
                datetime.now() - datetime.fromisoformat(last_renewal)
            ).days > days
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _is_retry_needed(
        state: Dict[str, Any], last_attempt_key: str, weeks: int = 3
    ) -> bool:
        """
        Check if retry is needed for a failed operation (older than specified weeks).

        Args:
            state: Current setup state
            last_attempt_key: Key in state dict for last attempt timestamp
            weeks: Number of weeks before retry is allowed

        Returns:
            True if retry should be attempted (cooldown expired or first attempt)
        """
        last_attempt = state.get(last_attempt_key)
        if last_attempt is None:
            return True

        try:
            last_attempt_date = datetime.fromisoformat(last_attempt)
            age = datetime.now() - last_attempt_date
            return age.days > (weeks * 7)
        except (TypeError, ValueError) as e:
            logger.debug(
                f'Error parsing retry timestamp for {last_attempt_key}: {e}'
            )
            return True

    # ------------------------------------------------------------------
    # Interactive helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ask_proceed(question: str) -> bool:
        """
        Ask the user a Y/N question and return True if they confirm.

        Defaults to *Yes* so a plain Enter accepts.  Returns True also
        when stdin is not a TTY (e.g. piped input) so automated runs are
        not blocked.
        """
        if not sys.stdin.isatty():
            return True  # non-interactive: proceed as normal
        try:
            answer = input(f'{question} [Y/n]: ').strip().lower()
            return answer in {'', 'y', 'yes'}
        except EOFError:
            return True

    def run_setup(
        self,
        *,
        force: bool = False,
        include_maintainer_steps: Optional[bool] = None,
    ) -> bool:
        """
        Run the complete environment setup with smart caching.

        Uses a state file to track what needs to be re-run:
        - Conan tools: Only if conan_tools.yml changed
        - Credentials: Only if older than 5 weeks
        - Git hooks: Only if hooks changed
        - Bazel cache: Only on first run
        - Conan environment: Always (lightweight)

        Internally orchestrates a list of :class:`SetupPhase` instances
        (see :mod:`xc_ce_utils.core_engine.setup.phases`).  Each phase
        decides if it should run and performs its work against a shared
        :class:`SetupContext`.

        Args:
            force: Force full setup even if state is up-to-date
            include_maintainer_steps: Include maintainer-only setup behavior.
                When None, derive from maintainer role in loaded config.

        Returns:
            True if setup was successful
        """
        phases_module = importlib.import_module(
            'xc_ce_utils.core_engine.setup.phases'
        )
        setup_context_type = phases_module.SetupContext
        default_phases = phases_module.default_setup_phases

        setup_start = time.monotonic()
        if not self._acquire_lock():
            logger.error(
                'Another setup process is already running. Please wait for it to complete.'
            )
            return False

        state = self._load_setup_state()
        setup_log_dir = get_logs_root(self.repo_path) / 'xc-ce-utils-setup'
        setup_log_dir.mkdir(parents=True, exist_ok=True)
        logger.add_file_logger(
            'setup_log', setup_log_dir / 'xc-ce-utils_setup.log'
        )

        try:
            return self._run_setup_locked(
                state=state,
                force=force,
                include_maintainer_steps=include_maintainer_steps,
                setup_context_type=setup_context_type,
                default_phases=default_phases,
            )

        except KeyboardInterrupt:
            logger.warning('\n  Setup cancelled by user')
            return False
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            ImportError,
        ) as e:
            logger.error(f'Environment setup failed: {e}')
            return False
        finally:
            logger.info(
                f'⏱  Total setup time: {time.monotonic() - setup_start:.1f}s'
            )
            logger.stop_file_logging('setup_log')
            self._release_lock()

    def _run_setup_locked(
        self,
        *,
        state: Dict[str, Any],
        force: bool,
        include_maintainer_steps: Optional[bool],
        setup_context_type: Any,
        default_phases: Any,
    ) -> bool:
        self._log_version_information(state)
        first_time_setup = state['last_full_setup'] is None
        needs_credential_check = (
            first_time_setup
            or force
            or self._is_credential_check_needed(state, weeks=5)
        )

        self._log_setup_mode(
            first_time_setup=first_time_setup,
            force=force,
            needs_credential_check=needs_credential_check,
        )
        config = self._load_setup_configuration()

        if include_maintainer_steps is None:
            include_maintainer_steps = self._is_maintainer_config(config)

        self._dump_build_configuration(config)

        is_ci = (
            os.environ.get('GITHUB_ACTIONS') == 'true'
            or os.environ.get('CI') == 'true'
        )
        ctx = setup_context_type(
            setup=self,
            config=config,
            state=state,
            first_time_setup=first_time_setup,
            force=force,
            is_ci=is_ci,
            needs_credential_check=needs_credential_check,
        )
        ctx.extras['include_maintainer_steps'] = include_maintainer_steps
        for phase in default_phases():
            if phase.should_run(ctx):
                phase.run(ctx)

        self._finalize_setup_state(
            state=state,
            first_time_setup=first_time_setup,
            needs_credential_check=needs_credential_check,
        )
        return True

    @staticmethod
    def _log_version_information(state: Dict[str, Any]) -> None:
        current_version = version_manager.get_version_object()
        stored_version_str = state.get('xc_ce_utils_version')

        logger.info(f' XC-CE Utils version: {current_version}')
        if not stored_version_str:
            return

        stored_version = Version(stored_version_str)
        if current_version.major != stored_version.major:
            logger.info(
                'i  Major version changed - using separate setup folder'
            )

    @staticmethod
    def _log_setup_mode(
        *,
        first_time_setup: bool,
        force: bool,
        needs_credential_check: bool,
    ) -> None:
        logger.log_phase_header('ENVIRONMENT SETUP')
        if first_time_setup:
            logger.info(
                ' First-time setup detected - running full environment setup'
            )
        elif force:
            logger.info(' Force flag detected - running full environment setup')
        elif needs_credential_check:
            logger.info(' Credentials older than 5 weeks - re-validating...')
        else:
            logger.info(' Setup state loaded - checking for updates...')
        sys.stdout.flush()

    def _load_setup_configuration(self) -> Dict[str, Any]:
        logger.progress('Loading build configuration...')
        sys.stdout.flush()
        config = self._load_configuration(self.repo_path)
        logger.debug('Configuration loaded successfully')
        sys.stdout.flush()
        return config

    @staticmethod
    def _is_maintainer_config(config: Dict[str, Any]) -> bool:
        role_gating = importlib.import_module(
            'xc_ce_utils.core_engine.cli.role_gating'
        )
        return bool(role_gating.is_maintainer(config))

    def _dump_build_configuration(self, config: Dict[str, Any]) -> None:
        config_dump_dir = get_builds_root(self.repo_path) / 'xc-ce-utils-setup'
        config_dump_dir.mkdir(parents=True, exist_ok=True)
        config_dump_file = config_dump_dir / 'configuration.json'
        try:
            self._write_build_configuration_dump(config_dump_file, config)
            logger.debug(f'Build configuration dumped to: {config_dump_file}')
        except (OSError, TypeError, ValueError, RuntimeError) as e:
            logger.debug(f'Failed to dump build configuration: {e}')

    @staticmethod
    def _write_build_configuration_dump(
        config_dump_file: Path, config: Dict[str, Any]
    ) -> None:
        with open(config_dump_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, default=str)

    def _finalize_setup_state(
        self,
        *,
        state: Dict[str, Any],
        first_time_setup: bool,
        needs_credential_check: bool,
    ) -> None:
        if first_time_setup:
            state['last_full_setup'] = datetime.now().isoformat()
            logger.progress('Marking environment setup as complete...')
            sys.stdout.flush()
            self.mark_setup_complete()
            self._save_setup_state(state)
            logger.success(' Environment setup completed successfully')
            sys.stdout.flush()
            return

        self._save_setup_state(state)
        if needs_credential_check:
            logger.success(' Credential validation completed')
        else:
            logger.success(
                ' Environment setup check completed (all up-to-date)'
            )
        sys.stdout.flush()

    @staticmethod
    def _load_configuration(repo_path: Path) -> Dict[str, Any]:
        """Load build configuration from main_conf.yml using conf_file_loader.

        Args:
            repo_path: Path to the repository root

        Returns:
            Dictionary containing build configuration
        """
        try:
            config = load_entry_config(repo_path, entry_conf_file=True)

            # Set environment variables from config
            for key, value in config.items():
                if isinstance(value, str) and key.isupper():
                    os.environ[key] = value

            return config

        except (
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.warning(f'Failed to load configuration: {e}')
            logger.debug(traceback.format_exc())
            return {}

    # _setup_git_hooks           → GitHooksSetupMixin (setup_git_hooks.py)
    # _calculate_directory_hash  → GitHooksSetupMixin (setup_git_hooks.py)
    # _has_directory_changed     → GitHooksSetupMixin (setup_git_hooks.py)
    # _save_directory_hash       → GitHooksSetupMixin (setup_git_hooks.py)

    # _check_vscode_extensions_changed → VSCodeSetupMixin (setup/vscode/extensions.py)
    # _update_vscode_extensions_hash    → VSCodeSetupMixin (setup/vscode/extensions.py)
    # _install_vscode_extensions        → VSCodeSetupMixin (setup/vscode/extensions.py)

    # _setup_devmate_pat              → DevmateSetupMixin (setup_devmate.py)
    # _warn_vscode_restart_if_needed  → DevmateSetupMixin (setup_devmate.py)

    @staticmethod
    def _validate_artifactory_credentials(config: Dict[str, Any]) -> bool:
        """Validate credentials for all configured Artifactory instances."""
        try:
            return EnvironmentSetup._validate_artifactory_credentials_impl(
                config
            )

        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.error(f'Failed to validate Artifactory credentials: {e}')
            return False

    @staticmethod
    def _validate_artifactory_credentials_impl(config: Dict[str, Any]) -> bool:
        artifactories = config.get('ARTIFACTORIES', {})
        if not artifactories:
            logger.info('No Artifactory instances configured')
            return True

        if not isinstance(artifactories, dict):
            logger.warning(
                f'ARTIFACTORIES is not a dictionary (type: {type(artifactories).__name__}), skipping validation'
            )
            return True

        hosts_to_validate, artifactory_to_host = (
            EnvironmentSetup._group_artifactory_hosts(artifactories)
        )
        logger.info(
            f'Found {len(hosts_to_validate)} unique Artifactory host(s) to validate'
        )

        is_ci = EnvironmentSetup._is_ci_environment()
        validated_hosts: Dict[str, bool] = {}

        for hostname, host_info in hosts_to_validate.items():
            validated_hosts[hostname] = (
                EnvironmentSetup._validate_host_credentials(
                    hostname=hostname,
                    host_info=host_info,
                    is_ci=is_ci,
                )
            )

        all_valid = all(validated_hosts.values()) if validated_hosts else True
        EnvironmentSetup._log_artifactory_validation_summary(
            artifactories=artifactories,
            artifactory_to_host=artifactory_to_host,
            validated_hosts=validated_hosts,
        )

        if all_valid:
            logger.success('All Artifactory credentials validated successfully')
        else:
            logger.warning(
                'Some Artifactory credentials are invalid or unavailable'
            )

        return all_valid

    @staticmethod
    def _group_artifactory_hosts(
        artifactories: Dict[str, Any],
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        hosts_to_validate: Dict[str, Dict[str, Any]] = {}
        artifactory_to_host: Dict[str, str] = {}

        for artifactory_name, artifactory_config in artifactories.items():
            if not isinstance(artifactory_config, dict):
                logger.warning(
                    f'Skipping {artifactory_name}: configuration is not a dictionary'
                )
                continue

            url = artifactory_config.get('url', '')
            if not url:
                continue

            parsed_url = urlparse(url)
            netloc = parsed_url.netloc or parsed_url.path.split('/')[0]
            hostname = netloc.split(':')[0] if ':' in netloc else netloc
            base_url = (
                f'{parsed_url.scheme}://{hostname}'
                if parsed_url.scheme
                else f'https://{hostname}'
            )

            artifactory_to_host[artifactory_name] = hostname
            host_entry = hosts_to_validate.setdefault(
                hostname,
                {'url': base_url, 'artifactories': []},
            )
            host_entry['artifactories'].append(artifactory_name)

        return hosts_to_validate, artifactory_to_host

    @staticmethod
    def _is_ci_environment() -> bool:
        return (
            os.environ.get('GITHUB_ACTIONS') == 'true'
            or os.environ.get('CI') == 'true'
        )

    @staticmethod
    def _validate_host_credentials(
        *,
        hostname: str,
        host_info: Dict[str, Any],
        is_ci: bool,
    ) -> bool:
        artifactory_list = ', '.join(host_info['artifactories'])
        logger.progress(
            f'Validating credentials for {hostname} (used by: {artifactory_list})...'
        )

        max_retries = 3 if not is_ci else 1
        retry_count = 0

        while retry_count < max_retries:
            if retry_count > 0:
                logger.info(
                    f'Retry attempt {retry_count}/{max_retries - 1} for {hostname}'
                )

            username, password = get_auth_manager().get_credentials(
                host_info['url']
            )
            if not username or not password:
                retry_count += 1
                EnvironmentSetup._handle_missing_credentials(
                    hostname=hostname,
                    is_ci=is_ci,
                    retry_count=retry_count,
                    max_retries=max_retries,
                )
                continue

            if EnvironmentSetup._credentials_ping_success(
                hostname=hostname,
                base_url=host_info['url'],
                username=username,
                password=password,
            ):
                return True

            retry_count += 1
            EnvironmentSetup._handle_failed_credentials(
                hostname=hostname,
                is_ci=is_ci,
                retry_count=retry_count,
                max_retries=max_retries,
            )

        return False

    @staticmethod
    def _handle_missing_credentials(
        *,
        hostname: str,
        is_ci: bool,
        retry_count: int,
        max_retries: int,
    ) -> None:
        if is_ci:
            logger.error(
                f'Technical user credentials not valid for {hostname}. Check if they have expired.'
            )
            logger.error('Cannot prompt for credentials in CI environment.')
            sys.exit(1)

        if retry_count >= max_retries:
            logger.error(
                f'Failed to validate credentials for {hostname} after {max_retries} attempts.'
            )
            logger.error(
                'Aborting setup. Please verify your credentials and try again.'
            )
            sys.exit(1)

        logger.warning(f'No credentials available for {hostname}')

    @staticmethod
    def _credentials_ping_success(
        *,
        hostname: str,
        base_url: str,
        username: str,
        password: str,
    ) -> bool:
        ping_url = f"{base_url.rstrip('/')}/artifactory/api/system/ping"
        logger.debug(f'Testing {hostname} via /artifactory/api/system/ping...')

        response: Optional[requests.Response] = None
        try:
            response = requests.get(
                ping_url,
                auth=(username, password),
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            logger.error(f'Γ£ù {hostname}: Connection failed - {exc}')
            return False
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.error(
                f'Γ£ù {hostname}: Unexpected error during validation - {exc}'
            )
            return False

        if response.status_code == HTTP_STATUS_OK:
            logger.success(f'Γ£ô {hostname}: Credentials valid')
            return True

        if response.status_code in {401, 403}:
            logger.error(
                f'Γ£ù {hostname}: Invalid credentials (HTTP {response.status_code})'
            )
            return False

        logger.error(
            f'Γ£ù {hostname}: Unexpected response (HTTP {response.status_code})'
        )
        logger.debug(f'Response: {response.text[:200]}')
        return False

    @staticmethod
    def _handle_failed_credentials(
        *,
        hostname: str,
        is_ci: bool,
        retry_count: int,
        max_retries: int,
    ) -> None:
        if retry_count < max_retries:
            logger.warning(
                f'Credentials invalid. Please try again ({retry_count}/{max_retries})'
            )
            return

        if is_ci:
            logger.error(
                f'Technical user credentials not valid for {hostname}. Check if they have expired.'
            )
            logger.error(
                'Aborting setup due to invalid credentials in CI environment.'
            )
            sys.exit(1)

        logger.error(
            f'Failed to validate credentials for {hostname} after {max_retries} attempts.'
        )
        logger.error(
            'Aborting setup. Please verify your credentials and try again.'
        )
        sys.exit(1)

    @staticmethod
    def _log_artifactory_validation_summary(
        *,
        artifactories: Dict[str, Any],
        artifactory_to_host: Dict[str, str],
        validated_hosts: Dict[str, bool],
    ) -> None:
        logger.info('Validation summary by artifactory:')
        for artifactory_name in artifactories:
            hostname = artifactory_to_host.get(artifactory_name)
            if not hostname or hostname not in validated_hosts:
                continue

            if validated_hosts[hostname]:
                logger.success(f'  Γ£ô {artifactory_name}')
            else:
                logger.error(f'  Γ£ù {artifactory_name}')

    # _ensure_bazel_disk_cache_path → BazelSetupMixin (setup_bazel.py)
    # _notify_old_bazel_cache       → BazelSetupMixin (setup_bazel.py)
    # _format_size                  → BazelSetupMixin (setup_bazel.py)
    # setup_bazel_cache             → BazelSetupMixin (setup_bazel.py)

    def setup_vscode_extensions(self, *, force: bool = False) -> bool:
        """
        Install VS Code extensions from .vscode/extensions.json if it has changed.
        This method can be called standalone (e.g., when -vs flag is used).

        Args:
            force: Force installation even if extensions.json hasn't changed

        Returns:
            True if installation was successful or skipped
        """
        try:
            return EnvironmentSetup._setup_vscode_extensions_impl(
                self,
                force=force,
            )

        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.error(f'Failed to setup VS Code extensions: {e}')
            logger.debug(traceback.format_exc())
            return False

    def _setup_vscode_extensions_impl(self, *, force: bool) -> bool:
        vscode_extensions_file = self.repo_path / '.vscode' / 'extensions.json'

        if not vscode_extensions_file.exists():
            logger.info('No .vscode/extensions.json found')
            logger.info(
                'Run VS Code configurator to generate extensions.json first'
            )
            return False

        state = self._load_setup_state()
        extensions_changed = force or self._check_vscode_extensions_changed(
            vscode_extensions_file,
            state,
        )
        if not extensions_changed:
            logger.info(
                ' VS Code extensions are up-to-date (no changes detected)'
            )
            return True

        logger.log_phase_header('VS CODE EXTENSIONS')
        outcome = self._install_vscode_extensions()
        if outcome is VSCodeExtensionsOutcome.FAILED:
            return False
        if outcome is VSCodeExtensionsOutcome.CLI_UNAVAILABLE:
            return True

        self._update_vscode_extensions_hash(vscode_extensions_file, state)
        state['setup_steps']['vscode_extensions'] = datetime.now().isoformat()
        self._save_setup_state(state)

        logger.success('VS Code extensions setup completed')
        return True
