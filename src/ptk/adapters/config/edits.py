"""Write ordinary YAML overlays atomically; reject symlinks and concurrent writers."""

import os
import tempfile
from pathlib import Path

import yaml

from ...domain.config.tree import from_plain, merge, to_plain
from ...domain.errors import PtkError


def write_overlay(target: Path, patch: dict, *, dry_run: bool = False) -> str:
    try:
        if target.is_symlink():
            raise PtkError(f"refusing symlink output: {target}")
        before = target.read_bytes() if target.exists() else None
        old = yaml.safe_load(before) if before is not None else {}
        if not isinstance(old, dict):
            raise PtkError("overlay must be an ordinary YAML mapping")
        text = yaml.safe_dump(
            to_plain(merge(from_plain(old), from_plain(patch))), sort_keys=False
        )
        if dry_run:
            return text
        lock = target.with_name(target.name + ".lock")
        with lock.open("x"):
            pass
        temp = None
        try:
            current = target.read_bytes() if target.exists() else None
            if target.is_symlink() or before != current:
                raise PtkError("overlay changed during editing; retry")
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, delete=False
            ) as handle:
                temp = Path(handle.name)
                handle.write(text)
            os.replace(temp, target)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
            lock.unlink(missing_ok=True)
        return text
    except (OSError, yaml.YAMLError) as exc:
        raise PtkError(f"cannot update overlay {target}: {exc}") from None
