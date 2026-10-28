"""Delete validated output directories without following directory symlinks."""

import shutil
from pathlib import Path

from ..domain.errors import PtkError
from .process_options import captured_process_options


def validate_directory(path: Path, root: Path, protected=()) -> None:
    root = root.resolve()
    if (
        path.is_symlink()
        or path.resolve() == root
        or not path.resolve().is_relative_to(root)
    ):
        raise PtkError(
            f"unsafe cleanup path: {path}; outputs must stay inside the repository"
        )
    current = path
    while current != root:
        if current.is_symlink():
            raise PtkError(f"unsafe cleanup path through symlink: {current}")
        if current.parent == current:
            raise PtkError(f"unsafe cleanup path: {path}")
        current = current.parent
    for item in [root / ".git", root / ".ptk", root / ".repo", *protected]:
        if item.resolve().is_relative_to(path.resolve()):
            raise PtkError(f"cleanup would remove protected project data: {item}")
    # A misspelled output folder must not wipe tracked source files.
    import subprocess

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--",
                str(path.relative_to(root)),
            ],
            capture_output=True,
            check=False,
            **captured_process_options(),
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout:
        raise PtkError(f"cleanup would remove Git-tracked files: {path}")
    if path.exists() and not path.is_dir():
        raise PtkError(f"cleanup expected a directory: {path}")


def delete_directory(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError as exc:
        raise PtkError(f"cannot clean {path}: {exc}") from exc
