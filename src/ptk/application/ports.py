"""Ports: interfaces the use cases depend on (implemented by adapters)."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from ..domain.config.tree import Node

MAIN_FILE = "main.ptk.yml"
CI_FILE = "ci.ptk.yml"
LOCAL_FILE = "local.ptk.yml"
MAINTAINERS_FILE = "maintainers.ptk.yml"


class ConfigSource(Protocol):
    """Reads ptk configuration files into located trees."""

    def find_main(self, start: Path) -> Path:
        """Locate ``main.ptk.yml`` in ``start`` or a parent directory."""

    def read(self, file: Path) -> Node:
        """Read a file including everything it includes."""

    def exists(self, file: Path) -> bool: ...

    @property
    def files(self) -> list[Path]:
        """All files read so far, in order."""


class HostEnvironment(Protocol):
    """Facts about the machine and user the CLI runs for."""

    @property
    def variables(self) -> Mapping[str, str]: ...

    def is_ci(self) -> bool: ...

    def os_name(self) -> str:
        """'windows' or 'linux' (or 'macos')."""

    def user_identity(self) -> tuple[str | None, str | None]:
        """(git e-mail, OS user name)."""
