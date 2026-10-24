"""Reusable layered config-deployment primitives.

Shared building blocks for any xc-ce-utils subsystem that ships a *base*
configuration template alongside an optional, project-owned *overrides*
file. Originally extracted from :mod:`xc_ce_utils.git_hooks.config_layer`
so that other modules (e.g. ``xc_ce_utils.clang``) can deploy their own
configs without duplicating the boilerplate.

Two layers per tool:

* BASE  -- shipped by xc-ce-utils. Copied verbatim to
           ``<config-root>/<tool>/<file_name>`` on every setup run.
* LOCAL -- optional, project-owned, hand-edited; lives next to BASE,
           typically ``<config-root>/<tool>/overrides.<ext>``.

The shipped *base* and *overrides example* live in a templates directory
private to the caller (e.g. ``xc_ce_utils/git_hooks/templates/`` or
``xc_ce_utils/clang/templates/``). All public helpers in this module take
that templates root as an explicit parameter, so multiple subsystems can
coexist without sharing state.

Subsystems that generate a root-of-repo file (e.g. ``.pre-commit-config.yaml``,
``.clang-format``) should call :func:`safe_write_generated` to write it.
That helper refuses to clobber any pre-existing root file lacking the
:data:`GENERATED_MARKER`, so projects with hand-crafted configs are never
silently overwritten.
"""

from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Marker that must appear in the first 10 lines of any generated root file.
#: :func:`safe_write_generated` uses this to detect hand-edited files and
#: refuse to overwrite them.
GENERATED_MARKER = '!!! GENERATED FILE'


# ---------------------------------------------------------------------------
# Template-source resolution
# ---------------------------------------------------------------------------


def resolve_templates_root(module_file: str, subdir: str = 'templates') -> Path:
    """Resolve a caller module's templates directory.

    Convention: each subsystem ships its base templates inside a sibling
    ``templates/`` directory next to its ``__init__.py`` / ``config_layer.py``.
    Callers pass ``__file__`` and get back the absolute path.

    >>> # In xc_ce_utils/clang/config_layer.py:
    >>> TEMPLATES_ROOT = resolve_templates_root(__file__)
    """
    return Path(module_file).resolve().parent / subdir


# ---------------------------------------------------------------------------
# Base deployment (verbatim copy)
# ---------------------------------------------------------------------------


def deploy_base(
    tool: str, file_name: str, repo_root: Path, templates_root: Path
) -> Path:
    """Copy the shipped *base* template for *tool* into ``<config-root>/<tool>/``.

    Always overwrites: base files are owned by xc-ce-utils, not the project.
    Skips the write (but still returns the destination path) when the
    destination is already byte-identical.
    """
    src = templates_root / tool / file_name
    if not src.exists():
        msg = f'Shipped base template not found: {src}'
        raise FileNotFoundError(msg)
    config_root = get_project_config_root(repo_root)
    dest_dir = config_root / tool
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_name
    if dest.exists() and dest.read_bytes() == src.read_bytes():
        return dest
    shutil.copy2(src, dest)
    rel = Path(os.path.relpath(str(dest), str(repo_root))).as_posix()
    logger.info(f'Refreshed {rel} from xc-ce-utils base')
    return dest


def deploy_overrides_example(
    tool: str, file_name: str, repo_root: Path, templates_root: Path
) -> Path | None:
    """Copy the shipped *overrides example* next to the deployed base.

    Idempotent: only writes when missing, so a project's hand-edited copy of
    the example is never clobbered. Returns ``None`` when no such example
    template is shipped.
    """
    src = templates_root / tool / file_name
    if not src.exists():
        return None
    config_root = get_project_config_root(repo_root)
    dest_dir = config_root / tool
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_name
    if dest.exists():
        return dest
    shutil.copy2(src, dest)
    rel = Path(os.path.relpath(str(dest), str(repo_root))).as_posix()
    logger.debug(f'Installed example {rel}')
    return dest


# ---------------------------------------------------------------------------
# Generated-file writer with hand-edit safety net
# ---------------------------------------------------------------------------


def safe_write_generated(
    path: Path, content: str, marker: str = GENERATED_MARKER
) -> bool:
    """Write *content* to *path*, refusing to overwrite a hand-edited file.

    A file is considered hand-edited when it exists and *marker* does not
    appear within the first 10 lines.

    Returns ``True`` when the file was written, ``False`` when skipped
    (either because the file is hand-edited or because the existing content
    already matches).
    """
    if path.exists():
        head = path.read_text(encoding='utf-8', errors='replace').splitlines()[
            :10
        ]
        if not any(marker in line for line in head):
            logger.warning(
                f'{path.name} exists without the GENERATED marker -- assuming '
                f'hand-edited; skipping regeneration. To opt into the layered '
                f'config system, move customisations to '
                f'config/<tool>/overrides.* and delete {path.name}.'
            )
            return False
        if path.read_text(encoding='utf-8') == content:
            return False  # already up-to-date
    path.write_text(content, encoding='utf-8')
    logger.info(f'Generated {path.name}')
    return True


# ---------------------------------------------------------------------------
# Runtime layered-config merge helpers
# ---------------------------------------------------------------------------


def deep_merge_layered_config(base: Any, override: Any) -> Any:
    """Deep-merge layered configuration values.

    Merge semantics are intentionally generic so multiple subsystems can
    reuse the helper:

    - ``dict`` + ``dict``: recursive key merge.
    - ``list`` + ``list``: append missing values from override while
      preserving order and de-duplicating by equality.
    - all other types: override replaces base.
    """
    if isinstance(base, dict) and isinstance(override, dict):
        merged: dict[str, Any] = {}
        for key in set(base.keys()).union(override.keys()):
            if key in base and key in override:
                merged[key] = deep_merge_layered_config(
                    base[key], override[key]
                )
            elif key in base:
                merged[key] = deepcopy(base[key])
            else:
                merged[key] = deepcopy(override[key])
        return merged

    if isinstance(base, list) and isinstance(override, list):
        merged_list = [deepcopy(item) for item in base]
        for item in override:
            if any(existing == item for existing in merged_list):
                continue
            merged_list.append(deepcopy(item))
        return merged_list

    return deepcopy(override)
