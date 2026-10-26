"""Ports: interfaces the use cases depend on (implemented by adapters)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..domain.config.model import PythonSpec
    from ..domain.config.tree import Node
    from ..domain.credentials import SecretKey
    from ..domain.execution.commands import PythonRuntime
    from ..domain.execution.model import (
        CommandSpec,
        JobPlan,
        PlannedStep,
        RunResult,
        StepResult,
    )
    from ..domain.logging import Level
    from ..domain.reporting.model import Contribution, Report
    from ..domain.tools import InstallMethod
    from ..domain.versioning import VersionSource

MAIN_FILE = ".main.ptk.yml"
CX_FILE = "cx.ptk.yml"
LOCAL_FILE = "local.ptk.yml"
MAINTAINERS_FILE = "maintainers.ptk.yml"


class ConfigSource(Protocol):
    """Reads ptk configuration files into located trees."""

    def find_main(self, start: Path) -> Path:
        """Locate ``.main.ptk.yml`` in ``start`` or a parent directory."""

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

    def is_docker(self) -> bool: ...

    def os_name(self) -> str:
        """'windows' or 'linux' (or 'macos')."""

    def user_id(self) -> str | None:
        """OS login name locally, triggering actor on GitHub Actions."""


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

    def run_started(self, plan: JobPlan) -> None: ...

    def step_started(self, step: PlannedStep, command: str | None) -> None: ...

    def output(self, step: PlannedStep, line: str) -> None: ...

    def message(self, level: Level, text: str, step: PlannedStep | None) -> None:
        """ptk's own messages (retries, errors, debug details); optional."""

    def step_finished(self, step: PlannedStep, result: StepResult) -> None: ...

    def run_finished(self, result: RunResult) -> None: ...


class SecretResolver(Protocol):
    def __call__(self, ref: str) -> str:
        """``credential.field`` -> secret value."""


class TasksFile(Protocol):
    """``.vscode/tasks.json`` (JSON with comments)."""

    path: Path
    had_comments: bool

    def read(self) -> dict | None: ...

    def render(self, data: dict) -> str: ...

    def write(self, data: dict) -> None: ...


class AuthoringResources(Protocol):
    def bundle(self) -> dict[str, bytes]: ...

    def sync(
        self, root: Path, files: dict[str, bytes], *, version: str, check: bool
    ) -> list[str]: ...


# --------------------------------------------------------------------------- credentials


class SecretProvider(Protocol):
    """One link of the credential chain (env, keyring, gopass, vault, prompt)."""

    name: str
    can_store: bool

    def available(self) -> tuple[bool, str]:
        """(usable here?, reason if not)."""

    def get(self, key: SecretKey) -> str | None: ...

    def store(self, key: SecretKey, value: str) -> None: ...

    def remove(self, key: SecretKey) -> bool: ...


class Prompter(Protocol):
    def interactive(self) -> bool:
        """A person can answer (terminal attached and not in CI)."""

    def secret(self, question: str) -> str: ...


# --------------------------------------------------------------------------- reporting


class ReportStore(Protocol):
    """Reads run summaries and tool results, writes report files."""

    def read_summary(self, log_dir: Path, run_id: str | None = None) -> dict: ...

    def contributions(
        self, reports_dir: Path, labels: list[str]
    ) -> list[Contribution]: ...

    def write(self, report: Report, formats: list[str], target: Path) -> list[Path]: ...


# --------------------------------------------------------------------------- shared configs


class SharedConfigFiles(Protocol):
    """Base configs shipped with ptk and the project's config files."""

    def base(self, name: str) -> tuple[str, str]:
        """(text, version) of a shipped base config."""

    def parse(self, text: str, source: str) -> dict: ...

    def render(self, name: str, data: dict) -> str: ...

    def read(self, path: Path) -> str | None: ...

    def write(self, path: Path, text: str) -> None: ...


# --------------------------------------------------------------------------- tools


class ToolInstaller(Protocol):
    """Installs tools (Chocolatey, uv tool, downloads, apt/dnf) and knows their folders."""

    def bin_dirs(self, tools=None) -> list[str]:
        """Folders with ptk-installed tools; put first on PATH for every command."""

    def clean_environment(self, env: dict[str, str]) -> dict[str, str]: ...

    def install(
        self, name: str, method: InstallMethod, out: Callable[[str], None]
    ) -> None: ...


class ProjectScaffold(Protocol):
    def create(self, target: Path, files: dict[str, str], *, dry_run: bool) -> bool:
        """Create new scaffold files; return whether an existing .gitignore was kept.

        Refuse existing .main.ptk.yml. A dry run performs checks without writes.
        """


@dataclass(frozen=True)
class WorkspaceMember:
    root: Path
    alias: str | None = None
    skip_reason: str | None = None


class VersionDiscovery(Protocol):
    """External version sources and atomic generated snapshot storage."""

    def discover(self, spec: VersionSource, root: Path) -> dict: ...

    def snapshot(self, path: str | Path, snapshot: dict) -> None: ...
