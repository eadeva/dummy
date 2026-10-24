"""Runtime staging for packaged resources.

Some Windows installations inherit restrictive ACLs for files under
``site-packages``. Tools that copy or mutate those resources can fail at
runtime. This module provides a reusable fallback that mirrors such resources
to a writable runtime directory.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path


def _is_packaged_site_path(path: Path) -> bool:
    normalized = path.as_posix().lower()
    return 'site-packages' in normalized or 'dist-packages' in normalized


def _is_pyinstaller_internal_path(path: Path) -> bool:
    return '_internal/' in path.as_posix().lower()


def _is_dir_writable(path: Path) -> bool:
    probe = path / '.xc_ce_utils_write_probe'
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text('probe', encoding='utf-8')
        probe.unlink()
        return True
    except Exception:
        return False


def _force_user_writable(path: Path) -> None:
    for item in path.rglob('*'):
        try:
            mode = item.stat().st_mode
            item.chmod(mode | stat.S_IWRITE)
        except Exception:
            continue


def _build_runtime_candidates(
    repo_root: Path | None,
    preferred_runtime_root: Path | None,
) -> list[Path]:
    candidates: list[Path] = []

    if preferred_runtime_root is not None:
        candidates.append(preferred_runtime_root)

    env_root = os.getenv('XC_CE_UTILS_RUNTIME_RESOURCES_DIR')
    if env_root:
        candidates.append(Path(env_root))

    if repo_root is not None:
        candidates.append(repo_root / '.xc_ce_utils_runtime')

    xc_ce_tmp = os.getenv('XC_CE_UTILS_TMPDIR')
    if xc_ce_tmp:
        candidates.append(Path(xc_ce_tmp) / 'xc_ce_utils_runtime')

    candidates.append(Path(tempfile.gettempdir()) / 'xc_ce_utils_runtime')
    return candidates


def _pick_runtime_root(
    repo_root: Path | None,
    preferred_runtime_root: Path | None,
) -> Path:
    for candidate in _build_runtime_candidates(
        repo_root, preferred_runtime_root
    ):
        if _is_dir_writable(candidate):
            return candidate
    raise Exception(
        'No writable runtime directory available for resource staging'
    )


def stage_resource_directory(
    source_path: Path,
    *,
    resource_name: str,
    repo_root: Path | None = None,
    preferred_runtime_root: Path | None = None,
    logger=None,
) -> Path:
    """Return a path that is safe to use by tools needing writable resources.

    - Source checkouts and PyInstaller internal bundles are returned as-is.
    - ``site-packages`` resources are mirrored to a writable runtime cache.
    """
    resolved_source = source_path.resolve()

    if _is_pyinstaller_internal_path(resolved_source):
        return resolved_source

    if not _is_packaged_site_path(resolved_source):
        return resolved_source

    runtime_root = _pick_runtime_root(repo_root, preferred_runtime_root)
    source_key = hashlib.sha256(
        str(resolved_source).encode('utf-8')
    ).hexdigest()[:12]
    mirror_path = runtime_root / f'{resource_name}_{source_key}'
    marker_path = mirror_path / '.source_path'

    current_marker = ''
    if marker_path.exists():
        try:
            current_marker = marker_path.read_text(encoding='utf-8')
        except Exception:
            current_marker = ''

    if current_marker != str(resolved_source):
        if mirror_path.exists():
            shutil.rmtree(mirror_path, ignore_errors=True)
        shutil.copytree(resolved_source, mirror_path, dirs_exist_ok=True)
        _force_user_writable(mirror_path)
        marker_path.write_text(str(resolved_source), encoding='utf-8')
        if logger is not None:
            logger.info(
                f'Using writable runtime mirror for {resource_name}: {mirror_path}'
            )

    return mirror_path
