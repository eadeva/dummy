"""File system implementation of the ConfigSource port."""

from __future__ import annotations

from pathlib import Path

from ...application.ports import MAIN_FILE
from ...domain.config.tree import Node
from ...domain.errors import ConfigError, Problem
from .discovery import discover_files
from .yaml_loader import YamlConfigReader


class FileConfigSource:
    def __init__(self) -> None:
        self._reader: YamlConfigReader | None = None

    def find_main(self, start: Path) -> Path:
        start = start.resolve()
        found = None
        for directory in [start, *start.parents]:
            candidate = directory / MAIN_FILE
            if found is None and candidate.is_file():
                found = candidate
            if (directory / ".git").exists() or (directory / ".git").is_symlink():
                if found is not None and found.parent != directory:
                    raise ConfigError(
                        [
                            Problem(
                                f"{MAIN_FILE} must be at repository root: {directory}"
                            )
                        ]
                    )
                break
        if found is not None:
            return found
        raise ConfigError(
            [
                Problem(
                    f"no {MAIN_FILE} found in {start} or any parent directory "
                    f"(create one with 'ptk setup init')"
                )
            ]
        )

    def read(self, file: Path) -> Node:
        if self._reader is None:
            self._reader = YamlConfigReader(display_root=file.resolve().parent)
        return self._reader.read(file)

    def discover(self, main: Path, *, ci: bool = False) -> list[Path]:
        return discover_files(main, ci=ci)

    def exists(self, file: Path) -> bool:
        return file.is_file()

    @property
    def files(self) -> list[Path]:
        return list(self._reader.files) if self._reader else []

    @property
    def fingerprints(self) -> dict[str, str]:
        return dict(self._reader.fingerprints) if self._reader else {}
