"""Discover repo-managed virtual monorepos without invoking Git or repo."""

from __future__ import annotations

import os
from pathlib import Path

from ..domain.config.tree import get
from ..domain.errors import PtkError
from .config.yaml_loader import YamlConfigReader


def workspace_root(start: Path) -> Path | None:
    start = start.resolve()
    for directory in (start, *start.parents):
        if (directory / ".repo").is_dir():
            return directory
        git = directory / ".git"
        target = None
        if git.is_symlink():
            target = git.resolve()
        elif git.is_file():
            try:
                text = git.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if text.startswith("gitdir:"):
                target = (directory / text.removeprefix("gitdir:").strip()).resolve()
        if target is not None and target.is_dir():
            for parent in (target, *target.parents):
                if parent.name == ".repo" and parent.is_dir():
                    return parent.parent
    return None


def repositories(root: Path) -> dict[str, Path]:
    """Return alias -> entry file, restricted to workspace members.

    repo's project.list is authoritative. For workspaces without that index,
    inspect working-tree roots, never Git storage or symlinked directory trees.
    """
    index = root / ".repo" / "project.list"
    candidates = []
    if index.is_file():
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            relative = Path(line.strip())
            path = (root / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(root):
                raise PtkError(f"VMR member path escapes workspace: {line!r}")
            candidates.append(path)
    else:
        for directory, dirs, _files in os.walk(root, followlinks=False):
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in {".repo", ".git"} and not (Path(directory) / d).is_symlink()
            )
            path = Path(directory)
            if (path / ".git").exists() or (path / ".git").is_symlink():
                candidates.append(path)
    result = {}
    for directory in sorted(set(candidates)):
        main = directory / ".main.ptk.yml"
        if not main.is_file():
            continue
        tree = YamlConfigReader().read(main, metadata_only=True)
        alias = get(tree, ("repository", "alias"))
        if alias is None:
            raise PtkError(f"missing repository alias: {main}")
        if alias.value in result:
            raise PtkError(
                f"duplicate repository alias {alias.value!r}: {result[alias.value]} and {main}"
            )
        result[alias.value] = main
    return result
