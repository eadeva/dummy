"""File system implementation of the ConfigSource port."""
from __future__ import annotations

from pathlib import Path

from ...application.ports import MAIN_FILE
from ...domain.config.tree import Node
from ...domain.errors import ConfigError, Problem
from .yaml_loader import YamlConfigReader


class FileConfigSource:
    def __init__(self) -> None:
        self._reader: YamlConfigReader | None = None

    def find_main(self, start: Path) -> Path:
        start = start.resolve()
        for directory in [start, *start.parents]:
            candidate = directory / MAIN_FILE
            if candidate.is_file():
                return candidate
        raise ConfigError([Problem(f"no {MAIN_FILE} found in {start} or any parent directory "
                                   f"(create one with 'ptk init')")])

    def read(self, file: Path) -> Node:
        if self._reader is None:
            self._reader = YamlConfigReader(display_root=file.resolve().parent)
        return self._reader.read(file)

    def exists(self, file: Path) -> bool:
        return file.is_file()

    @property
    def files(self) -> list[Path]:
        return list(self._reader.files) if self._reader else []
