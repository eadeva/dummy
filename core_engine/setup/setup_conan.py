"""
Conan package manager setup mixin for the XC-CE environment setup.

Extracted from ``environment_setup.py`` to keep that file focused on
orchestration.  This mixin provides all Conan-related methods that
can be mixed into
:class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`.

Methods provided
----------------
- :meth:`_run_conan_command`       – uvx-based Conan CLI wrapper
- :meth:`_parse_conan_env_script`  – extract env-vars from conanbuildenv scripts
- :meth:`_apply_conan_environment` – apply Conan-generated env-vars to os.environ
- :meth:`setup_conan`              – top-level Conan installation + configuration
- :meth:`_check_install_conan`     – version check / install guard
- :meth:`_compute_settings_hash`   – SHA-256 of config/conan/config/settings.yml
- :meth:`_conan_config_install`    – conan config install with file-lock protection
- :meth:`_has_conan_artifactories` – static guard: any Conan remotes in config?
- :meth:`_setup_conan_remotes`     – add/login Conan remotes from ARTIFACTORIES
- :meth:`install_conan_tools`      – install tools from conan_tools.yml

Note
----
Methods that access state (``_load_setup_state``, ``_save_setup_state``,
``_calculate_file_hash``, ``_has_file_changed``, ``_save_file_hash``) are
defined in :class:`~xc_ce_utils.core_engine.setup.environment_setup.EnvironmentSetup`
and resolved via ``self`` at runtime.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from filelock import FileLock, Timeout

from xc_ce_utils.auth import get_auth_manager
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)
from xc_ce_utils.global_modules.uv_sidecar import find_uvx
from xc_ce_utils.rb_logger import logger


class ConanSetupMixin:
    """
    Mixin class providing Conan package-manager lifecycle methods.

    This class is designed to be mixed in with :class:`EnvironmentSetup`.
    It expects the following attributes on the consuming class:

    - ``self.repo_path``      – :class:`~pathlib.Path` to the repository root
    - ``self.project_folder`` – :class:`~pathlib.Path` to the per-project state folder
    - ``self.conan_home``     – :class:`~pathlib.Path` to the project-local Conan home
    """

    _DEFAULT_CONAN_UVX_SPEC = 'conan==2.12.0'

    def _get_conan_uvx_spec(self) -> str:
        """Return Conan package spec used by uvx (override via env if needed)."""
        env_spec = os.environ.get('XC_CE_UTILS_CONAN_UVX_SPEC', '').strip()
        return env_spec or self._DEFAULT_CONAN_UVX_SPEC

    def _build_conan_command(self, args: List[str]) -> List[str]:
        """Build uvx command line for Conan execution."""
        uvx_path = find_uvx()
        if uvx_path is None:
            raise FileNotFoundError('uvx executable not found')

        uvx_cmd = shutil.which('uvx') or str(uvx_path)
        return [uvx_cmd, '--from', self._get_conan_uvx_spec(), 'conan', *args]

    @staticmethod
    def _parse_conan_major(version_output: str) -> Optional[int]:
        """Extract Conan major version from `conan --version` output."""
        match = re.search(r'Conan\s+version\s+(\d+)\.', version_output or '')
        if not match:
            return None
        return int(match.group(1))

    # ------------------------------------------------------------------
    # Conan CLI wrapper
    # ------------------------------------------------------------------

    def _run_conan_command(
        self, args: List[str], **kwargs
    ) -> subprocess.CompletedProcess:
        """
        Run Conan command via uvx using Conan 2.x.

        Args:
            args: Conan command arguments (e.g., ["config", "install", "path"])
            **kwargs: Additional arguments for subprocess.run (timeout, etc.)

        Returns:
            subprocess.CompletedProcess from subprocess.run
        """
        check = kwargs.pop('check', False)
        return subprocess.run(
            self._build_conan_command(args), check=check, **kwargs
        )

    # ------------------------------------------------------------------
    # Conan environment helpers
    # ------------------------------------------------------------------

    def _parse_conan_env_script(self, script_path: Path) -> Dict[str, str]:
        """
        Parse Conan environment script to extract environment variables.

        Args:
            script_path: Path to conanbuildenv batch/shell script

        Returns:
            Dictionary of environment variable names and values
        """
        env_vars = {}

        if not script_path.exists():
            logger.debug(f'Conan env script not found: {script_path}')
            return env_vars

        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if platform.system() == 'Windows':
                # Parse Windows batch file: set "VAR=value"
                pattern = r'set\s+"([^=]+)=([^"]*)"'
                matches = re.findall(pattern, content, re.MULTILINE)
                for var_name, var_value in matches:
                    # Expand %~dp0 to script directory
                    if '%~dp0' in var_value:
                        script_dir = script_path.parent
                        var_value = var_value.replace(
                            '%~dp0', str(script_dir) + '\\'
                        )
                    env_vars[var_name] = var_value
            else:
                # Parse Linux shell script: export VAR="value"
                pattern = r'export\s+([^=]+)="([^"]*)"'
                matches = re.findall(pattern, content, re.MULTILINE)
                for var_name, var_value in matches:
                    env_vars[var_name] = var_value

            logger.debug(
                f'Parsed {len(env_vars)} environment variables from {script_path.name}'
            )
            return env_vars

        except Exception as e:
            logger.warning(f'Failed to parse Conan env script: {e}')
            return env_vars

    def _apply_conan_environment(self) -> bool:
        """
        Apply Conan environment variables from generated scripts.
        This sources the conanbuildenv script and sets environment variables.

        Returns:
            True if environment was applied successfully
        """
        try:
            logger.debug('Looking for Conan environment script...')
            # Look for conanbuildenv script in conan install directory
            conan_install_dir = self.project_folder / 'conan_install'  # type: ignore[attr-defined]

            if platform.system() == 'Windows':
                env_script = (
                    conan_install_dir / 'conanbuildenv-release-x86_64.bat'
                )
                if not env_script.exists():
                    env_script = conan_install_dir / 'conanbuild.bat'
            else:
                env_script = (
                    conan_install_dir / 'conanbuildenv-release-x86_64.sh'
                )
                if not env_script.exists():
                    env_script = conan_install_dir / 'conanbuild.sh'

            if not env_script.exists():
                logger.info(
                    'No Conan environment script found, skipping environment setup'
                )
                logger.info(f'Looked for: {env_script}')
                return True

            logger.debug(f'Found Conan environment script: {env_script}')

            # Parse environment variables from script
            logger.debug('Parsing Conan environment script...')
            env_vars = self._parse_conan_env_script(env_script)

            if not env_vars:
                logger.warning('No environment variables found in Conan script')
                return True

            logger.debug(
                f'Parsed {len(env_vars)} environment variables from Conan script'
            )

            # Apply environment variables
            for var_name, var_value in env_vars.items():
                # Special handling for PATH - append rather than replace
                if var_name.upper() == 'PATH':
                    # Extract new paths (before %PATH% or $PATH)
                    if platform.system() == 'Windows':
                        new_paths = var_value.split('%PATH%')[0]
                    else:
                        new_paths = var_value.split('$PATH')[0]

                    if new_paths:
                        # Remove trailing path separator
                        new_paths = new_paths.rstrip(';:')
                        # Prepend to existing PATH
                        current_path = os.environ.get('PATH', '')
                        os.environ['PATH'] = (
                            f'{new_paths}{os.pathsep}{current_path}'
                        )
                        logger.debug('Updated PATH with Conan paths')
                else:
                    os.environ[var_name] = var_value
                    logger.debug(f'Set {var_name}={var_value[:80]}...')

            logger.debug('Conan environment variables applied successfully')
            return True

        except Exception as e:
            logger.error(f'Failed to apply Conan environment: {e}')
            logger.error(traceback.format_exc())
            return False

    # ------------------------------------------------------------------
    # Conan setup
    # ------------------------------------------------------------------

    def setup_conan(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Setup Conan installation and configuration.

        Args:
            config: Build configuration (if not provided, will load from file)

        Returns:
            True if setup was successful
        """
        try:
            # Load config if not provided
            if config is None:
                config = self._load_configuration(self.repo_path)  # type: ignore[attr-defined]

            # Check Conan is available
            if not self._check_conan_available():
                return False

            # Detect/create default profile
            if not self._conan_config_install():
                return False

            # Configure remotes using ARTIFACTORIES from config
            # (credentials already validated in run_setup)
            if not self._setup_conan_remotes(config):
                raise RuntimeError('Conan remote setup failed')

            logger.success('Conan setup completed successfully')
            return True

        except Exception as e:
            logger.error(f'Conan setup failed: {e}')
            return False

    def _check_conan_available(self) -> bool:
        """Check if Conan 2.x is available through uvx."""
        logger.progress('Checking for Conan installation...')

        try:
            result = self._run_conan_command(
                ['--version'], capture_output=True, text=True, timeout=10
            )

            version_output = (result.stdout or result.stderr or '').strip()
            version_line = (
                version_output.splitlines()[0] if version_output else ''
            )
            major = self._parse_conan_major(version_line)

            if result.returncode == 0 and major == 2:
                logger.success(
                    f'{version_line} is available via uvx ({self._get_conan_uvx_spec()})'
                )
                return True

            if result.returncode == 0:
                logger.warning(
                    f"Unsupported Conan version output '{version_line}'. Only Conan 2.x is supported."
                )
            else:
                logger.warning('Conan 2.x not available via uvx')
                if version_output:
                    logger.warning(version_output)
            logger.info('Install uv/uvx and ensure it is available in PATH')
            return False

        except FileNotFoundError:
            logger.warning('uvx not found in PATH')
            logger.info('Install uv and ensure uvx is available in PATH')
            return False
        except Exception as e:
            logger.error(f'Error checking Conan installation: {e}')
            return False

    def _check_install_conan(self, required_version: str) -> bool:
        """Check if Conan 2.x is available and matches required version if provided."""
        logger.progress(
            f'Checking for Conan installation (version {required_version} required)...'
        )

        try:
            result = self._run_conan_command(
                ['--version'], capture_output=True, text=True, timeout=10
            )

            version_output = (result.stdout or result.stderr or '').strip()
            version_line = (
                version_output.splitlines()[0] if version_output else ''
            )
            version_match = re.search(
                r'Conan\s+version\s+([0-9]+\.[0-9]+\.[0-9]+)', version_line
            )
            installed_version = version_match.group(1) if version_match else ''
            major = self._parse_conan_major(version_line)

            if result.returncode != 0 or major != 2:
                logger.warning('Conan 2.x not available via uvx')
                if version_output:
                    logger.warning(version_output)
                logger.info('Install uv and ensure uvx is available in PATH')
                return False

            if (
                required_version
                and installed_version
                and installed_version != required_version
            ):
                logger.warning(
                    f'Conan version {installed_version} found, but {required_version} required'
                )
                logger.info(
                    'Adjust XC_CE_UTILS_CONAN_UVX_SPEC to select the required Conan package version'
                )
                return False

            logger.success(
                f'Conan version {installed_version or version_line} is available'
            )
            return True

        except FileNotFoundError:
            logger.warning('uvx not found in PATH')
            logger.info('Install uv and ensure uvx is available in PATH')
            return False
        except Exception as e:
            logger.error(f'Error checking Conan installation: {e}')
            return False

    def _compute_settings_hash(self) -> str:
        """
        Compute hash of repository settings.yml.

        Returns:
            SHA256 hash of config/conan/config/settings.yml
        """
        config_root = get_project_config_root(self.repo_path)  # type: ignore[attr-defined]
        settings_file = config_root / 'conan' / 'config' / 'settings.yml'

        if not settings_file.exists():
            logger.warning(
                f'Repository settings.yml not found: {settings_file}'
            )
            return ''

        return self._calculate_file_hash(settings_file)  # type: ignore[attr-defined]

    def _conan_config_install(self) -> bool:
        """Setup Conan configuration using conan config install with file lock protection."""
        # Use Conan-specific lock to protect settings.yml updates
        conan_lock_file = self.project_folder / 'conan_config.lock'  # type: ignore[attr-defined]

        try:
            with FileLock(conan_lock_file, timeout=900):  # 15 minutes timeout
                logger.debug('Acquired conan_config.lock')

                # Check if settings.yml needs update
                current_hash = self._compute_settings_hash()
                state = self._load_setup_state()  # type: ignore[attr-defined]
                stored_hash = state.get('conan_settings_hash')

                force_settings_update = False
                if current_hash and current_hash != stored_hash:
                    logger.info(
                        ' Repository settings.yml has changed - forcing update'
                    )
                    force_settings_update = True

                logger.progress('Installing Conan configuration...')

                # Path to Conan config folder
                config_root = get_project_config_root(self.repo_path)  # type: ignore[attr-defined]
                conan_config_path = config_root / 'conan' / 'config'

                if not conan_config_path.exists():
                    logger.warning(
                        f'Conan config folder not found: {conan_config_path}'
                    )
                    logger.info('Falling back to conan profile detect...')

                    # Fallback: detect default profile
                    result = self._run_conan_command(
                        ['profile', 'detect', '--force'],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        logger.success('Conan profile detected successfully')
                        return True
                    else:
                        logger.warning(
                            f'Conan profile detection failed: {result.stderr}'
                        )
                        return False

                # Install Conan configuration from folder
                logger.progress(
                    f"Running 'conan config install {conan_config_path}'..."
                )
                result = self._run_conan_command(
                    ['config', 'install', str(conan_config_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    logger.success('Conan configuration installed successfully')

                    # After successful config install, update settings.yml if needed
                    if force_settings_update or not stored_hash:
                        repo_settings = (
                            config_root / 'conan' / 'config' / 'settings.yml'
                        )
                        conan_settings = self.conan_home / 'settings.yml'  # type: ignore[attr-defined]

                        if repo_settings.exists():
                            conan_settings.parent.mkdir(
                                parents=True, exist_ok=True
                            )

                            # Copy file
                            shutil.copy2(repo_settings, conan_settings)
                            logger.debug(
                                f' Copied settings.yml: {repo_settings} → {conan_settings}'
                            )

                            # Set permissions: read/write for all users (cross-platform)
                            try:
                                os.chmod(
                                    conan_settings,
                                    stat.S_IRUSR
                                    | stat.S_IWUSR
                                    | stat.S_IRGRP
                                    | stat.S_IWGRP
                                    | stat.S_IROTH
                                    | stat.S_IWOTH,
                                )
                                logger.debug(
                                    f' Set write permissions for all users on {conan_settings.name}'
                                )
                            except Exception as e:
                                logger.debug(
                                    f'Failed to set permissions (non-critical): {e}'
                                )

                            logger.success(
                                ' Updated Conan settings.yml from repository'
                            )

                            # Update stored hash
                            state['conan_settings_hash'] = current_hash
                            self._save_setup_state(state)  # type: ignore[attr-defined]

                    return True
                else:
                    logger.warning(
                        f'Conan config install failed: {result.stderr}'
                    )
                    logger.info('Falling back to conan profile detect...')

                # Fallback: detect default profile
                result = self._run_conan_command(
                    ['profile', 'detect', '--force'],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    logger.success('Conan profile detected successfully')
                    return True
                else:
                    logger.warning(
                        f'Conan profile detection failed: {result.stderr}'
                    )
                    return False

                logger.debug('Released conan_config.lock')

        except Timeout:
            logger.error(
                'Could not acquire conan_config.lock - another process is configuring Conan'
            )
            logger.error(
                'Please wait for the other process to complete or try again later'
            )
            return False
        except Exception as e:
            logger.error(f'Failed to setup Conan configuration: {e}')
            return False

    @staticmethod
    def _has_conan_artifactories(config: Dict[str, Any]) -> bool:
        """Return True if the config contains at least one Conan-type artifactory."""
        artifactories = config.get('ARTIFACTORIES', {})
        if not isinstance(artifactories, dict):
            return False
        return any(
            isinstance(v, dict)
            and (
                v.get('type') == 'conan'
                or 'conan' in v.get('repository', '').lower()
            )
            for v in artifactories.values()
        )

    def _setup_conan_remotes(self, config: Dict[str, Any]) -> bool:
        """Setup Conan remote repositories using ARTIFACTORIES from config."""
        try:
            artifactories = config.get('ARTIFACTORIES', {})

            if not artifactories:
                logger.info(
                    'No Artifactory instances configured for Conan remotes'
                )
                return True

            # Ensure artifactories is a dict, not a string
            if not isinstance(artifactories, dict):
                logger.warning(
                    f'ARTIFACTORIES is not a dictionary (type: {type(artifactories).__name__}), skipping Conan remotes setup'
                )
                return True

            logger.progress('Configuring Conan remotes from ARTIFACTORIES...')

            # Filter only Conan artifactories
            conan_remotes = {
                name: art_config
                for name, art_config in artifactories.items()
                if isinstance(art_config, dict)
                and (
                    art_config.get('type') == 'conan'
                    or 'conan' in art_config.get('repository', '').lower()
                )
            }

            if not conan_remotes:
                logger.info('No Conan artifactories found in configuration')
                return True

            logger.info(
                f'Found {len(conan_remotes)} Conan remote(s) to configure'
            )

            for remote_name, art_config in conan_remotes.items():
                url = art_config.get('url', '')
                repository = art_config.get('repository', '')

                if not url:
                    logger.warning(f'No URL configured for {remote_name}')
                    continue

                # Construct full Conan remote URL: base_url/repository
                # Example: https://rb-artifactory.bosch.com/artifactory/api/conan/gw-2wp-conan-local
                if repository:
                    # Ensure URL doesn't end with / and repository doesn't start with /
                    full_url = f"{url.rstrip('/')}/{repository.lstrip('/')}"
                else:
                    logger.warning(
                        f'No repository configured for {remote_name}, using base URL only'
                    )
                    full_url = url

                # First, check if remote exists, if not add it
                logger.debug(
                    f"Checking if Conan remote '{remote_name}' exists..."
                )
                list_result = self._run_conan_command(
                    ['remote', 'list'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                remote_exists = remote_name in list_result.stdout

                if not remote_exists:
                    # Add the remote with full URL including repository
                    logger.progress(
                        f"Adding Conan remote '{remote_name}' with URL: {full_url}"
                    )
                    add_result = self._run_conan_command(
                        ['remote', 'add', remote_name, full_url],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if add_result.returncode == 0:
                        logger.success(f"Added Conan remote '{remote_name}'")
                    else:
                        logger.error(
                            f"Failed to add remote '{remote_name}': {add_result.stderr}"
                        )
                        raise RuntimeError(
                            f"Conan remote add failed for '{remote_name}'"
                        )
                else:
                    logger.debug(f"Conan remote '{remote_name}' already exists")

                # Get credentials using base URL (without repository) for keyring lookup
                username, password = get_auth_manager().get_credentials(url)

                # Login if credentials available
                if username and password:
                    logger.progress(
                        f"Logging in to Conan remote '{remote_name}' as {username}..."
                    )
                    result = self._run_conan_command(
                        [
                            'remote',
                            'login',
                            remote_name,
                            username,
                            '-p',
                            password,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if result.returncode == 0:
                        logger.success(
                            f"Logged in to '{remote_name}' successfully"
                        )
                    else:
                        logger.error(
                            f"Failed to login to '{remote_name}': {result.stderr}"
                        )
                        raise RuntimeError(
                            f"Conan remote login failed for '{remote_name}'"
                        )
                else:
                    logger.info(
                        f"No credentials available for remote '{remote_name}', skipping login"
                    )

            logger.success('Conan remotes configured successfully')
            return True

        except Exception as e:
            logger.error(f'Failed to setup Conan remotes: {e}')
            logger.error(traceback.format_exc())
            return False

    # ------------------------------------------------------------------
    # Conan tools installation
    # ------------------------------------------------------------------

    def install_conan_tools(self, force_install: bool = False) -> bool:
        """
        Install Conan tools from config/requirements/conan_tools.yml.

        Args:
            force_install: Force installation even if tools configuration hasn't changed

        Returns:
            True if installation was successful or not needed
        """
        try:
            config_root = get_project_config_root(self.repo_path)  # type: ignore[attr-defined]
            tools_file = config_root / 'requirements' / 'conan_tools.yml'

            if not tools_file.exists():
                logger.info(
                    f'Legacy Conan tools file not found, skipping tool installation: {tools_file}'
                )
                return True

            # Check if tools configuration has changed
            if not force_install and not self._has_file_changed(
                tools_file, 'conan_tools.yml'
            ):  # type: ignore[attr-defined]
                logger.debug('Conan tools configuration unchanged')
                return True

            logger.progress('Loading Conan tools configuration...')

            # Load tools configuration
            with open(tools_file, 'r', encoding='utf-8') as f:
                tools = yaml.safe_load(f) or {}

            if not tools:
                logger.warning('No Conan tools specified in configuration')
                # Still save hash since file was processed
                self._save_file_hash(tools_file, 'conan_tools.yml')  # type: ignore[attr-defined]
                return True

            logger.info(f'Found {len(tools)} Conan tool(s) to install')

            # Create conan install directory in project folder
            logger.debug('Creating conan install directory...')
            conan_install_dir = self.project_folder / 'conan_install'  # type: ignore[attr-defined]
            conan_install_dir.mkdir(parents=True, exist_ok=True)

            conanfile_path = conan_install_dir / 'conanfile.txt'
            logger.debug(f'Generating {conanfile_path}...')

            # Generate conanfile.txt with all tool_requires
            conanfile_content = '[tool_requires]\n'
            for tool_name, tool_config in tools.items():
                version = tool_config.get('version', 'latest')
                conanfile_content += f'{tool_name}/{version}\n'

            conanfile_content += '\n[generators]\n'
            conanfile_content += 'VirtualBuildEnv\n'

            # Write conanfile.txt
            with open(conanfile_path, 'w', encoding='utf-8') as f:
                f.write(conanfile_content)

            logger.debug(f'Generated conanfile.txt with {len(tools)} tool(s)')
            logger.progress(
                f'Installing {len(tools)} Conan tool(s) (this may take several minutes)...'
            )
            logger.info("Running 'conan install --build=missing'...")

            # Run conan install once for all tools - show output
            # Use -of to specify output folder for generated files
            result = self._run_conan_command(
                [
                    'install',
                    str(conanfile_path),
                    '--build=missing',
                    '-of',
                    str(conan_install_dir),
                ],
                text=True,
                timeout=600,  # 10 minutes for all tools
            )

            if result.returncode == 0:
                logger.success(
                    f'All {len(tools)} Conan tool(s) installed successfully'
                )
                # Save hash for future change detection
                self._save_file_hash(tools_file, 'conan_tools.yml')  # type: ignore[attr-defined]
                return True
            else:
                logger.error(
                    f"Failed to install Conan tools: {result.stderr if hasattr(result, 'stderr') else ''}"
                )
                raise RuntimeError('Conan tools installation failed')

        except subprocess.TimeoutExpired:
            logger.error('Conan tools installation timed out')
            raise RuntimeError('Conan tools installation timed out')
        except Exception as e:
            logger.error(f'Failed to install Conan tools: {e}')
            return False
