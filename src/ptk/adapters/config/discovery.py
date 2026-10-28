"""Repository configuration discovery, shared by CLI and editor clients."""

import os
from pathlib import Path

from ...domain.config.discovery import IGNORED_DIRECTORIES


def discover_files(main: Path, *, ci: bool = False) -> list[Path]:
    """Do not cross symlinks, generated resources or another project boundary.

    config_path is the preferred authoring folder, not a loading boundary.
    Maintainer identities remain an independently validated identity document.
    """
    main = main.resolve()
    root = main.parent
    files = [main]
    for directory, folders, names in os.walk(root, followlinks=False):
        base = Path(directory)
        folders[:] = sorted(
            name
            for name in folders
            if name not in IGNORED_DIRECTORIES
            and not (base / name).is_symlink()
            and not (base / name / ".main.ptk.yml").exists()
            and not (base / name / ".git").exists()
            and not (base.name == ".github" and name == "ptk")
        )
        for name in sorted(names):
            if not name.endswith((".ptk.yml", ".ptk.yaml")):
                continue
            if name in {".main.ptk.yml", ".gen.version.ptk.yml", "maintainers.ptk.yml"}:
                continue
            if name == "cx.ptk.yml" and not ci:
                continue
            file = base / name
            if not file.is_symlink() and file.is_file():
                files.append(file)
    return files
