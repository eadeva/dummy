"""Errors shared by all layers.

Every user-facing problem is a ``Problem`` with an optional source location,
so drivers can print ``file:line: path: message`` consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Location:
    file: str
    line: int = 0  # 1-based; 0 = unknown (e.g. command line)

    def __str__(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


@dataclass(frozen=True)
class Problem:
    message: str
    path: str = ""
    location: Location | None = None

    def __str__(self) -> str:
        parts = [str(self.location)] if self.location else []
        if self.path:
            parts.append(self.path)
        parts.append(self.message)
        return ": ".join(parts)


class PtkError(Exception):
    """Base class for all expected, user-facing errors."""


class RunNotFoundError(PtkError):
    """No saved run is available for the requested report."""


@dataclass
class ConfigError(PtkError):
    problems: list[Problem] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__("\n".join(str(p) for p in self.problems))

    def __str__(self) -> str:
        return "\n".join(str(p) for p in self.problems)


class ProjectNotFoundError(ConfigError):
    """No project marker exists within the repository search boundary."""


class UnknownNameError(PtkError):
    """An unknown job, variant, feature, ... (message contains suggestions)."""
