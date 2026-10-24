"""Ports: interfaces the use cases depend on (implemented by adapters)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..domain.config.model import PythonSpec
from ..domain.config.tree import Node
from ..domain.execution.commands import PythonRuntime
from ..domain.execution.model import (
    ActionPlan,
    CommandSpec,
    PlannedStep,
    RunResult,
    StepResult,
)
from ..domain.logging import Level

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


# --------------------------------------------------------------------------- execution


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int
    timed_out: bool = False
    cancelled: bool = False
    error: str | None = None  # e.g. program not found


class CancelToken(Protocol):
    def is_set(self) -> bool: ...


class ProcessRunner(Protocol):
    """Runs one command, streaming its output line by line."""

    def run(
        self,
        command: CommandSpec,
        on_output: Callable[[str], None],
        cancel: CancelToken | None = None,
    ) -> ProcessOutcome: ...

    def which(self, program: str, path: str | None = None) -> str | None: ...


class PythonEnvManager(Protocol):
    """Provides Python runtimes through uv (uvx, cached venvs, uv run --project, ptk's own)."""

    def runtime(
        self,
        spec: PythonSpec | None,
        root: Path,
        *,
        create: bool,
        on_output: Callable[[str], None] | None = None,
    ) -> PythonRuntime | None:
        """``create=False`` only describes (dry run); ``create=True`` builds missing venvs."""


class RunObserver(Protocol):
    """Receives the progress of a run (console, log files, reports...)."""

    def run_started(self, plan: ActionPlan) -> None: ...

    def step_started(self, step: PlannedStep, command: str | None) -> None: ...

    def output(self, step: PlannedStep, line: str) -> None: ...

    def message(self, level: Level, text: str, step: PlannedStep | None) -> None:
        """ptk's own messages (retries, errors, debug details); optional."""

    def step_finished(self, step: PlannedStep, result: StepResult) -> None: ...

    def run_finished(self, result: RunResult) -> None: ...


class SecretResolver(Protocol):
    def __call__(self, ref: str) -> str:
        """``credential.field`` -> secret value."""
