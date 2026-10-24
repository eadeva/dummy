"""Install the project's TACO adapter (``taco`` CLI) into the running environment."""

from __future__ import annotations

import importlib.metadata
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

from xc_ce_utils.auth.rb_credentials_manager import get_credentials_manager
from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci, run_command
from xc_ce_utils.global_modules.uv_sidecar import find_uv
from xc_ce_utils.rb_logger import logger


def adapter_path(ctx: SetupContext) -> Optional[Path]:
    """Return the adapter folder configured as ``TACO.adapter_path`` in main_conf.yml."""
    taco_config = ctx.config.get('TACO') or {}
    configured = taco_config.get('adapter_path') if isinstance(taco_config, dict) else None
    return Path(ctx.setup.repo_path) / configured if configured else None


def read_adapter_project(path: Path) -> Dict[str, Any]:
    """Return name, version and uv indexes of the adapter's pyproject.toml."""
    with (path / 'pyproject.toml').open('rb') as handle:
        pyproject = tomllib.load(handle)
    project = pyproject.get('project', {})
    return {
        'name': project.get('name', ''),
        'version': project.get('version', ''),
        'indexes': pyproject.get('tool', {}).get('uv', {}).get('index', []),
    }


def installed_version(distribution: str) -> Optional[str]:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def index_credentials_env(indexes: list) -> Dict[str, str]:
    """Return uv's per-index credential variables (``UV_INDEX_<NAME>_USERNAME/PASSWORD``)."""
    env: Dict[str, str] = {}
    for index in indexes:
        name, url = index.get('name'), index.get('url')
        if not name or not url:
            continue
        username, password = get_credentials_manager().get_credentials(url)
        if username and password:
            # BDC rejects the bare NT ID stored in the keyring; it expects <id>@bosch.com
            if 'boschdevcloud.com' in url and '@' not in username and not is_running_in_ci():
                username = f'{username}@bosch.com'
            key = re.sub(r'[^A-Z0-9]', '_', name.upper())
            env[f'UV_INDEX_{key}_USERNAME'] = username
            env[f'UV_INDEX_{key}_PASSWORD'] = password
    return env


class TacoAdapterPhase(SetupPhase):
    """Install the TACO adapter when it is configured and not installed in its current version."""

    name = 'taco_adapter'

    def should_run(self, ctx: SetupContext) -> bool:
        path = adapter_path(ctx)
        if path is None or getattr(sys, 'frozen', False):
            return False
        if not (path / 'pyproject.toml').is_file():
            logger.warning(f'TACO adapter not found: {path / "pyproject.toml"}')
            return False
        if tomllib is None:
            logger.warning('Installing the TACO adapter requires Python 3.11 or later.')
            return False
        project = read_adapter_project(path)
        return installed_version(project['name']) != project['version']

    def run(self, ctx: SetupContext) -> None:
        path = adapter_path(ctx)
        project = read_adapter_project(path)
        logger.log_phase_header('SETUP - TACO')
        uv = find_uv()
        if uv is None:
            logger.error('uv is required to install the TACO adapter but was not found.')
            return
        logger.progress(
            f'Installing TACO adapter {project["name"]} {project["version"]} from {path}'
        )
        cmd = [
            str(uv),
            '--project',
            str(path),
            'pip',
            'install',
            '--python',
            sys.executable,
            '--editable',
            str(path),
        ]
        try:
            credentials = index_credentials_env(project['indexes'])
        except Exception as exc:  # CI raises when the technical user is not configured
            logger.warning(f'No credentials for the TACO package indexes ({exc}); trying without.')
            credentials = {}
        try:
            run_command(cmd, env={**os.environ, **credentials})
        except subprocess.CalledProcessError:
            logger.error(
                'Installing the TACO adapter failed. Check access to the package indexes listed in '
                f'{path / "pyproject.toml"} (Artifactory IDM roles, identity token).'
            )
