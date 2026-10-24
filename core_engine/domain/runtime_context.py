"""Runtime context detection for xc_ce_utils.

This module centralizes runtime discovery so all policy decisions can rely on
the same interpretation of host/container environment.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_TRUE_VALUES = {'1', 'true', 'yes', 'on', 'enable', 'enabled'}
_FALSE_VALUES = {'0', 'false', 'no', 'off', 'disable', 'disabled'}
_CGROUP_DOCKER_MARKERS = ('docker', 'containerd', 'podman', 'kubepods')


@dataclass(frozen=True)
class RuntimeContext:
    """Normalized runtime context for policy decisions."""

    os_name: str
    is_windows: bool
    is_linux: bool
    is_docker: bool


def _parse_forced_docker() -> bool | None:
    """Parse optional explicit docker override from environment."""
    raw_value = os.getenv('XC_CE_UTILS_FORCE_DOCKER', '').strip().lower()
    if not raw_value:
        return None
    if raw_value in _TRUE_VALUES:
        return True
    if raw_value in _FALSE_VALUES:
        return False
    return None


def _detect_docker_by_markers() -> bool:
    """Detect whether current process runs in a containerized environment."""
    if Path('/.dockerenv').exists() or Path('/run/.containerenv').exists():
        return True

    container_hint = os.getenv('container', '').strip().lower()
    if container_hint in {'docker', 'podman', 'containerd'}:
        return True

    cgroup_path = Path('/proc/1/cgroup')
    if cgroup_path.exists():
        try:
            cgroup_text = cgroup_path.read_text(
                encoding='utf-8', errors='ignore'
            ).lower()
        except OSError:
            cgroup_text = ''
        if any(marker in cgroup_text for marker in _CGROUP_DOCKER_MARKERS):
            return True

    return False


@lru_cache(maxsize=1)
def get_runtime_context() -> RuntimeContext:
    """Return runtime context with cached detection result."""
    detected_os = platform.system().strip().lower() or 'unknown'
    forced_docker = _parse_forced_docker()
    if forced_docker is None:
        is_docker = _detect_docker_by_markers()
    else:
        is_docker = forced_docker

    return RuntimeContext(
        os_name=detected_os,
        is_windows=detected_os == 'windows',
        is_linux=detected_os == 'linux',
        is_docker=is_docker,
    )


def get_xc_ce_utils_base_path() -> Path:
    """Return the directory containing the ``xc_ce_utils`` package.

    Works identically in both xc-ce-utils run modes:

    * Frozen (PyInstaller) executable: returns ``sys._MEIPASS``, the bundle
      root where ``xc_ce_utils/...`` data files are extracted at runtime.
    * Venv / source / installed-wheel: derived from the ``xc_ce_utils``
      package's own ``__file__``, so it stays correct regardless of how
      deeply the calling module is nested inside the package -- unlike a
      hardcoded ``Path(__file__).resolve().parent.parent.parent`` chain,
      which silently breaks if a caller file moves to a different depth.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    import xc_ce_utils

    return Path(xc_ce_utils.__file__).resolve().parent.parent
