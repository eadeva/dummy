"""Execution model: planned steps, commands and results (entities)."""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..config.model import PythonSpec, StepSpec


class Status(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class CommandSpec:
    """A fully resolved command, ready for the ProcessRunner."""

    argv: list[str] | None = None  # executed directly (preferred)
    shell: str | None = None  # executed through the platform shell
    cwd: str = "."
    env: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None

    def display(self) -> str:
        if self.shell is not None:
            return self.shell
        argv = self.argv or []
        return (
            subprocess.list2cmdline(argv)
            if sys.platform.startswith("win")
            else shlex.join(argv)
        )


@dataclass
class PlannedStep:
    path: tuple[str, ...]  # one named step relative to the job output folder
    spec: StepSpec
    skip_reason: str | None = None  # condition false, not selected, ...
    run: str | list[str] | None = None  # after substitution (+ pass-through args)
    cwd: str = "."
    env: dict[str, str] = field(default_factory=dict)  # step env (substituted)
    with_: dict[str, Any] = field(default_factory=dict)  # uses parameters (substituted)
    secrets: dict[str, str] = field(default_factory=dict)  # ENV_VAR: credential.field

    @property
    def name(self) -> str:
        return self.path[0]

    @property
    def kind(self) -> str:
        return self.spec.kind

    @property
    def title(self) -> str:
        return self.spec.title or self.name

    @property
    def label(self) -> str:
        return "/".join(self.path)

    @property
    def python(self) -> PythonSpec | None:
        return self.spec.python

    def walk(self):
        yield self


@dataclass
class JobPlan:
    project: str
    job: str
    variant: str | None
    run_id: str
    params: dict[str, Any]
    param_sources: dict[str, str]
    steps: list[PlannedStep]
    base_env: dict[
        str, str
    ]  # host/isolated env + config env + generated PTK_/VARIANT_ vars + job env
    dirs: dict[str, str]  # bin_dir, log_dir, reports_dir (job level)

    max_workers: int = 4
    only_step: str | None = None
    omitted_dependencies: list[str] = field(default_factory=list)
    report_context: dict[str, Any] = field(default_factory=dict)
    log_analysis: dict[str, Any] = field(default_factory=dict)

    def walk(self):
        for step in self.steps:
            yield from step.walk()


@dataclass
class StepResult:
    path: tuple[str, ...]
    name: str
    kind: str
    status: Status = Status.PENDING
    exit_code: int | None = None
    duration: float = 0.0
    start: float = 0.0  # seconds after the run started (for timelines)
    attempts: int = 0
    message: str = ""
    command: str = ""
    log_file: str | None = None
    allowed_failure: bool = False  # failed, but continue_on_error was set
    needs: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "/".join(self.path)

    @property
    def blocking_failure(self) -> bool:
        return (
            self.status in (Status.FAILED, Status.CANCELLED)
            and not self.allowed_failure
        )

    def walk(self):
        yield self


@dataclass
class RunResult:
    project: str
    job: str
    variant: str | None
    run_id: str
    status: Status
    started_at: str
    duration: float
    params: dict[str, Any]
    param_sources: dict[str, str]
    steps: list[StepResult]
    log_file: str | None = None
    report_problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status is Status.PASSED

    def walk(self):
        for step in self.steps:
            yield from step.walk()
