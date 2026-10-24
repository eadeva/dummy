"""Helpers for safe CMake toolchain argument handling.

This module centralizes the decision logic for when
``-DCMAKE_TOOLCHAIN_FILE=...`` should be passed to CMake. The variable is
consumed only on the first configure of a build directory; passing it again
on incremental configures commonly triggers the warning:

  "Manually-specified variables were not used by the project"

for ``CMAKE_TOOLCHAIN_FILE``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

TOOLCHAIN_ARG_PREFIX = '-DCMAKE_TOOLCHAIN_FILE='


def _read_cached_toolchain_file(cache_file: Path) -> Optional[str]:
    """Read ``CMAKE_TOOLCHAIN_FILE`` from a CMake cache file."""
    try:
        lines = cache_file.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return None

    for line in lines.splitlines():
        if line.startswith('CMAKE_TOOLCHAIN_FILE:FILEPATH='):
            return line.split('=', 1)[1].strip() or None
    return None


def _normalize_toolchain_path(path_value: str | Path, source_dir: Path) -> str:
    """Normalize toolchain paths for robust comparisons.

    Relative paths are resolved against ``source_dir`` to match how CMake
    usually canonicalizes the value in ``CMakeCache.txt``.
    """
    path_text = str(path_value).strip().strip('"')
    path = Path(path_text)
    if not path.is_absolute():
        path = source_dir / path
    normalized = path.resolve(strict=False).as_posix()
    if os.name == 'nt':
        normalized = normalized.lower()
    return normalized


def decide_toolchain_argument(
    build_dir: Path,
    source_dir: Path,
    toolchain_file: str | Path,
) -> Tuple[bool, Optional[str]]:
    """Decide whether to pass ``-DCMAKE_TOOLCHAIN_FILE`` for configure.

    Returns:
        (should_pass, warning)
        - ``should_pass`` is ``True`` only when no cache exists yet, or when
          the cache exists but has no ``CMAKE_TOOLCHAIN_FILE`` entry.
        - ``warning`` is populated when a different cached toolchain is found;
          changing it requires cache deletion / fresh build directory.
    """
    cache_file = build_dir / 'CMakeCache.txt'
    if not cache_file.exists():
        return True, None

    cached_toolchain = _read_cached_toolchain_file(cache_file)
    if not cached_toolchain:
        return True, None

    cached_norm = _normalize_toolchain_path(cached_toolchain, source_dir)
    current_norm = _normalize_toolchain_path(toolchain_file, source_dir)
    if cached_norm == current_norm:
        return False, None

    warning = (
        'toolchain file changed but CMake cache already pins '
        f'{cached_toolchain}. Delete {cache_file} to apply {toolchain_file}.'
    )
    return False, warning


def prepare_toolchain_argument(
    cmake_args: Iterable[str],
    build_dir: Path,
    source_dir: Path,
) -> Tuple[List[str], Optional[str]]:
    """Normalize ``cmake_args`` and conditionally keep toolchain argument.

    If multiple ``-DCMAKE_TOOLCHAIN_FILE=...`` args are present, the last
    one wins.
    """
    args_without_toolchain: List[str] = []
    toolchain_file: Optional[str] = None

    for arg in cmake_args:
        if arg.startswith(TOOLCHAIN_ARG_PREFIX):
            toolchain_file = arg[len(TOOLCHAIN_ARG_PREFIX) :]
        else:
            args_without_toolchain.append(arg)

    if not toolchain_file:
        return args_without_toolchain, None

    should_pass, warning = decide_toolchain_argument(
        build_dir=build_dir,
        source_dir=source_dir,
        toolchain_file=toolchain_file,
    )
    if should_pass:
        args_without_toolchain.append(f'{TOOLCHAIN_ARG_PREFIX}{toolchain_file}')
    return args_without_toolchain, warning
