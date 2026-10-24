"""Locate the bundled `uv` sidecar binary.

`uv` is shipped in `_internal/bin/` in the PyInstaller onedir bundle
(see ``xc-ce_core-engine.spec::_find_uv_binary``). It is the real interpreter
manager used wherever a genuine Python is required — most notably by the
default pre-commit template, whose external hygiene hooks are invoked as
``uvx --from <pkg>==<rev> <entry>``.

Inside a PyInstaller bundle, ``sys.executable`` points at the frozen exe and
therefore cannot serve as a Python interpreter for tools like ``virtualenv``
or ``pip``. Routing through the sidecar avoids that leaky abstraction
entirely.

Sidecar path is ``Path(sys.executable).parent / '_internal' / 'bin' / 'uv[.exe]'``

"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

__all__ = ['find_uv', 'find_uvx', 'uv_sidecar_dir']


def _binary_name(tool: str) -> str:
    suffix = '.exe' if sys.platform.startswith('win') else ''
    return f'{tool}{suffix}'


def _find_tool(tool: str) -> Path | None:
    name = _binary_name(tool)

    if getattr(sys, 'frozen', False):
        # Location is ``_internal/bin/``
        exe_dir = Path(sys.executable).parent
        side_car_path = exe_dir / '_internal' / 'bin' / name
        if side_car_path.exists():
            return side_car_path

    on_path = shutil.which(tool)
    if on_path:
        return Path(on_path)

    return None


def find_uv() -> Path | None:
    """Return the path to the `uv` binary, or ``None`` if not found.

    Returns:
        Absolute path to the sidecar `uv` binary when frozen, the PATH-located
        `uv` during development, or ``None`` if neither is available.
    """
    return _find_tool('uv')


def find_uvx() -> Path | None:
    """Return the path to the `uvx` binary, or ``None`` if not found."""
    return _find_tool('uvx')


def uv_sidecar_dir() -> Path | None:
    """Return the directory containing the bundled `uv` binary, or ``None``.

    Useful for prepending to ``PATH`` of subprocesses (e.g. ``pre-commit
    install``) so child processes resolve ``uv`` / ``uvx`` to the sidecar.
    """
    uv = find_uv()
    return uv.parent if uv is not None else None
