"""Environment isolation module for xc-ce-utils.

Provides a clean, reproducible build environment by stripping all inherited
environment variables and PATH entries except those explicitly allowed.
"""

import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict

from xc_ce_utils.rb_logger import logger

# Minimal OS-critical env vars that must always survive (case-insensitive on Windows)
_WINDOWS_ESSENTIAL = {
    'SYSTEMROOT',
    'SYSTEMDRIVE',
    'WINDIR',
    'TEMP',
    'TMP',
    'USERPROFILE',
    'HOMEDRIVE',
    'HOMEPATH',
    'COMPUTERNAME',
    'USERNAME',
    'USERDOMAIN',
    'USERDNSDOMAIN',
    'OS',
    'PATHEXT',
    'COMSPEC',
    'NUMBER_OF_PROCESSORS',
    'PROCESSOR_ARCHITECTURE',
    'PROGRAMFILES',
    'PROGRAMFILES(X86)',
    'PROGRAMW6432',
    'APPDATA',
    'LOCALAPPDATA',
    'COMMONPROGRAMFILES',
    'COMMONPROGRAMFILES(X86)',
    'COMMONPROGRAMW6432',
    'PSModulePath',
    'PUBLIC',
}

_LINUX_ESSENTIAL = {
    'HOME',
    'USER',
    'LOGNAME',
    'SHELL',
    'LANG',
    'LC_ALL',
    'TERM',
    'DISPLAY',
    'XDG_RUNTIME_DIR',
    'XDG_CONFIG_HOME',
    'XDG_DATA_HOME',
    'HOSTNAME',
    'SSH_AUTH_SOCK',
    'DBUS_SESSION_BUS_ADDRESS',
}

# Env vars that xc-ce-utils itself needs to function
_XC_CE_INTERNAL = {
    'PROJECT_NAME',
    'VERSION',
    'TB_HOMEDIR',
    # Set by dynamic_cli._run_environment_setup() and read by many modules
    # (action_configuration._get_git_info, helix_qac, init_repo, rb_logger,
    # rb_file_lock) AFTER env isolation runs. Must survive the isolation step.
    'REPO_PATH',
}

# Prefixes that are always bypassed (env vars starting with these are kept)
_BYPASS_PREFIXES = (
    'ACTIONS_',
    'ARTIFACT_',
    'CI_',
    'CONAN_',
    'GITHUB_',
    'GIT_',
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'NO_PROXY',
    'RUNNER_',
    'TECHNICAL_USER_',
    'TOOLBASE_',
    'XC_CE_UTILS_',
)

# Toolbase variables required by TBExCmd / Toolbase Client workflows on Windows.
# Keep these by default so projects do not need YAML overrides.
_WINDOWS_TOOLBASE_DEFAULT_ENV = {
    'TB_HOMEDIR',
    'TB_APPDATA',
    'TBC_HOME',
    'TBC_MODE',
    'TBCPROFILE_DIR',
}


def isolate_environment(config: Dict[str, Any]) -> None:
    """Apply environment isolation based on configuration.

    Removes all environment variables except:
    - OS-essential variables (hardcoded per platform)
    - xc-ce-utils internal variables
    - Variables listed in config['bypass_env_vars']

    Rebuilds PATH keeping only:
    - OS-essential paths (System32, Windows)
    - Entries matching config['bypass_path_elements']

    Args:
        config: The ENV_ISOLATION configuration dict with keys:
            - enabled (bool): Master switch (default True)
            - bypass_env_vars (list[str]): Env var names to preserve
            - bypass_path_elements (list[str]): PATH entries/patterns to preserve
    """
    # Validate against the EnvIsolationModel schema. Schema uses
    # ``extra="allow"`` so unknown keys are preserved; only type errors on
    # known fields are rejected. This catches misconfiguration early with a
    # clear error path. Always validate schema to catch invalid types early.
    try:
        from pydantic import ValidationError as _ValidationError

        from xc_ce_utils.core_engine.config.config_models import (
            EnvIsolationModel,
        )
        from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError

        try:
            validated = EnvIsolationModel.model_validate(config or {})
        except _ValidationError as ve:
            raise ConfigurationError(
                f'Invalid ENV_ISOLATION configuration: {ve}'
            ) from ve
        # Use the validated, type-coerced view going forward.
        config = validated.model_dump()
    except ImportError:  # pragma: no cover - pydantic is a hard dep
        pass

    # Check if isolation is enabled. After schema validation above, we know
    # 'enabled' is a valid bool.
    enabled = config.get('enabled', True)
    if not enabled:
        logger.info('Environment isolation is disabled')
        return

    logger.log_phase_header('ENVIRONMENT ISOLATION')
    logger.info('Isolating build environment...')

    bypass_env_vars = set(v.upper() for v in config.get('bypass_env_vars', []))
    bypass_path_elements = config.get('bypass_path_elements', [])

    # Build the allowlist
    if platform.system() == 'Windows':
        essential = _WINDOWS_ESSENTIAL
    else:
        essential = _LINUX_ESSENTIAL

    allowlist = essential | _XC_CE_INTERNAL | bypass_env_vars

    # Toolbase env vars are required to invoke TBExCmd reliably on Windows.
    if platform.system() == 'Windows':
        allowlist |= _WINDOWS_TOOLBASE_DEFAULT_ENV

    # Snapshot current env
    original_env = dict(os.environ)
    original_path = os.environ.get('PATH', '')

    # Remove all non-allowed env vars
    removed_vars = []
    for key in list(os.environ.keys()):
        key_upper = key.upper()
        if key_upper in allowlist:
            continue
        if any(key_upper.startswith(prefix) for prefix in _BYPASS_PREFIXES):
            continue
        del os.environ[key]
        removed_vars.append(key)

    logger.debug(f'Removed {len(removed_vars)} environment variables')
    if removed_vars:
        logger.debug(
            f"  Removed: {', '.join(sorted(removed_vars)[:20])}{'...' if len(removed_vars) > 20 else ''}"
        )

    # Rebuild PATH
    if platform.system() == 'Windows':
        separator = ';'
        # Always keep System32 and Windows dirs
        system_root = original_env.get('SYSTEMROOT', r'C:\Windows')
        essential_paths = [
            os.path.join(system_root, 'system32'),
            system_root,
            os.path.join(system_root, 'System32', 'Wbem'),
            # WindowsPowerShell v1.0 - required so subprocess.run(["powershell", ...])
            # can locate powershell.exe (used by e.g. DEVMATE_PAT registry write).
            os.path.join(system_root, 'System32', 'WindowsPowerShell', 'v1.0'),
        ]
    else:
        separator = ':'
        essential_paths = ['/usr/local/bin', '/usr/bin', '/bin']

    # Auto-bypass all PATH entries under CONAN_HOME (cmake, ninja, etc.)
    conan_home = original_env.get('CONAN_HOME', '')
    if conan_home:
        bypass_path_elements = list(bypass_path_elements) + [conan_home]
        logger.debug(f'Auto-bypassing CONAN_HOME paths: {conan_home}')

    # Always allow Git for Windows directories. Several actions need `git`
    # (e.g. channel computation in action_configuration._get_git_info), and
    # the install location varies (Program Files / Program Files (x86) / user
    # install / portable). Match by substring on the canonical layout.
    if platform.system() == 'Windows':
        bypass_path_elements = list(bypass_path_elements) + [
            r'\Git\cmd',
            r'\Git\bin',
            r'\Git\usr\bin',
        ]
        logger.debug('Auto-bypassing Git for Windows PATH entries')

        # Keep 7-Zip command path (7z.exe) available for artifact extraction
        # in installer/downloader flows that run after env isolation.
        bypass_path_elements = list(bypass_path_elements) + [
            r'\7-Zip',
        ]
        logger.debug('Auto-bypassing 7-Zip PATH entries')

        # Keep Toolbase Client command path (TBExCmd.exe / tbexcmd) available.
        # This is required for toolbase installation phases executed after env
        # isolation has trimmed PATH.
        bypass_path_elements = list(bypass_path_elements) + [
            r'\Toolbase Client',
        ]
        logger.debug('Auto-bypassing Toolbase Client PATH entries')

    # Auto-bypass the directory containing the running xc-ce-utils executable
    # itself. When frozen (PyInstaller), in-process `shutil.which("xc-ce-utils")`
    # lookups (e.g. by `_install_pre_commit_hook`) need to locate ourselves;
    # without this the exe cannot find itself even when the user put it on PATH.
    if getattr(sys, 'frozen', False):
        self_dir = str(Path(sys.executable).parent)
        bypass_path_elements = list(bypass_path_elements) + [self_dir]
        logger.debug(f'Auto-bypassing self exe directory: {self_dir}')

    # Filter PATH entries
    original_entries = original_path.split(separator)
    allowed_entries = list(essential_paths)

    for entry in original_entries:
        if not entry.strip():
            continue
        entry_normalized = entry.replace('\\', '/').rstrip('/').lower()
        for pattern in bypass_path_elements:
            pattern_normalized = pattern.replace('\\', '/').rstrip('/').lower()
            if (
                pattern_normalized in entry_normalized
                or entry_normalized.startswith(pattern_normalized)
            ):
                if entry not in allowed_entries:
                    allowed_entries.append(entry)
                break

    os.environ['PATH'] = separator.join(allowed_entries)

    kept_count = len(allowed_entries)
    removed_count = len(original_entries) - kept_count
    logger.info(
        f'PATH: kept {kept_count} entries, removed {removed_count} entries'
    )
    logger.debug('  Final PATH entries:')
    for p in allowed_entries:
        logger.debug(f'    - {p}')

    logger.success('Environment isolation applied')
