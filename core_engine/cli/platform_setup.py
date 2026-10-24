"""Platform environment/console setup for the dynamic CLI.

Extracted from the former ``core_engine/dynamic_cli.py`` monolith. Handles
Windows console UTF-8 reconfiguration, PyInstaller PATH setup, rich-click
defaults, cross-platform ``XC_CE_UTILS_*`` environment variables, and the
optional dev-tooling provider override read from
``XC_CE_UTILS_DEV_TOOLING_PROVIDER``.
"""

from __future__ import annotations

import contextlib
import getpass
import io
import os
import platform
import socket
import sys
import tempfile
from importlib import import_module
from pathlib import Path
from typing import Any

from xc_ce_utils import logger

# Fix Windows console encoding to support Unicode (emojis, special characters)
# This is critical for PyInstaller executables on Windows with CP1252 encoding
if sys.platform == 'win32':
    try:
        # Reconfigure stdout/stderr to use UTF-8 with error handling
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace'
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace'
        )
    except Exception:
        # Fallback: set environment variable (less reliable but better than nothing)
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Setup PATH for PyInstaller executable
# This ensures embedded tools (e.g., Conan) can be found by subprocess calls
if getattr(sys, 'frozen', False):
    exe_dir = Path(sys.executable).parent
    current_path = os.environ.get('PATH', '')
    if str(exe_dir) not in current_path:
        os.environ['PATH'] = str(exe_dir) + os.pathsep + current_path
        logger.debug(
            f'[PyInstaller] Added executable directory to PATH: {exe_dir}'
        )


_RICH_CLICK_STATE = {'configured': False}


def _get_click_module() -> Any:
    return import_module('rich_click')


def configure_rich_click_defaults() -> None:
    """Configure rich-click lazily when CLI construction starts."""
    if _RICH_CLICK_STATE['configured']:
        return

    click = _get_click_module()

    click.rich_click.USE_RICH_MARKUP = True
    click.rich_click.USE_MARKDOWN = True
    click.rich_click.SHOW_ARGUMENTS = True
    click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
    click.rich_click.SHOW_METAVARS_COLUMN = True
    click.rich_click.APPEND_METAVARS_HELP = True
    _RICH_CLICK_STATE['configured'] = True


def set_platform_env_variables() -> None:
    """Set cross-platform XC_CE_UTILS_* environment variables.

    Mirrors ``ActionConfiguration._set_platform_env_variables`` so CLI startup
    does not need to import heavy execution modules during help/version flows.
    """
    os.environ['XC_CE_UTILS_MACHINENAME'] = socket.gethostname().lower()
    os.environ['XC_CE_UTILS_USERNAME'] = getpass.getuser().lower()
    os.environ['XC_CE_UTILS_HOME'] = str(Path.home())
    os.environ['XC_CE_UTILS_TMPDIR'] = tempfile.gettempdir()
    os.environ['XC_CE_UTILS_OS'] = platform.system().lower()


def _get_dev_tooling_provider_api() -> tuple[Any, Any]:
    # Resolved through the application-layer public API (the driving-port
    # boundary) rather than the adapters package directly, so tests may
    # monkeypatch ``xc_ce_utils.core_engine.application`` attributes.
    module = import_module('xc_ce_utils.core_engine.application')
    return module.reset_dev_tooling_provider, module.set_dev_tooling_provider


def configure_dev_tooling_provider_from_env() -> None:
    """Configure optional dev-tooling provider override from environment.

    Set ``XC_CE_UTILS_DEV_TOOLING_PROVIDER`` to ``module:attribute`` where
    ``attribute`` is either a provider instance or a zero-arg factory that
    returns one.
    """
    reset_dev_tooling_provider, set_dev_tooling_provider = (
        _get_dev_tooling_provider_api()
    )

    raw_spec = os.environ.get('XC_CE_UTILS_DEV_TOOLING_PROVIDER', '').strip()
    if not raw_spec:
        reset_dev_tooling_provider()
        return

    module_name, separator, attribute_name = raw_spec.partition(':')
    if not separator or not module_name or not attribute_name:
        logger.warning(
            'Invalid XC_CE_UTILS_DEV_TOOLING_PROVIDER format. '
            'Expected module:attribute. Falling back to default provider.'
        )
        reset_dev_tooling_provider()
        return

    try:
        module = import_module(module_name)
        target = getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        logger.warning(
            'Failed to configure custom dev-tooling provider '
            f'({raw_spec}): {exc}. Falling back to default provider.'
        )
        reset_dev_tooling_provider()
        return

    if callable(target):
        try:
            provider = target()
        except TypeError as exc:
            logger.warning(
                'Failed to construct custom dev-tooling provider '
                f'({raw_spec}): {exc}. Falling back to default provider.'
            )
            reset_dev_tooling_provider()
            return
    else:
        provider = target

    set_dev_tooling_provider(provider)
    logger.info(
        f'Using custom dev-tooling provider: {module_name}:{attribute_name}'
    )


def ensure_utf8_stdout() -> None:
    """Force UTF-8 unbuffered output (needed for PyInstaller executables)."""
    if hasattr(sys.stdout, 'reconfigure'):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    else:
        with contextlib.suppress(Exception):
            sys.stdout = os.fdopen(
                sys.stdout.fileno(),
                'w',
                buffering=1,
                encoding='utf-8',
                errors='replace',
            )
