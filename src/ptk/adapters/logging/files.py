"""RunObserver writing the log files of the workspace layout.

    _logs/<variant>/<action>/run.log            whole run, every line prefixed with the step
    _logs/<variant>/<action>/<set>/<step>.log   output of one step

Output arrives already masked. M4 extends this with events.jsonl and history.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import TextIO

from ...domain import layout as lay
from ...domain.execution.model import (
    ActionPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)


def _now() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


class FileLogObserver:
    def __init__(self, layout: lay.Layout):
        self._layout = layout
        self._lock = threading.Lock()
        self._run: TextIO | None = None
        self._steps: dict[tuple[str, ...], TextIO] = {}
        self._plan: ActionPlan | None = None

    def run_started(self, plan: ActionPlan) -> None:
        self._plan = plan
        path = Path(self._layout.run_log(plan.variant, plan.action))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._run = path.open("w", encoding="utf-8")
        self._write_run(
            f"ptk run {plan.run_id}: project {plan.project}, action {plan.action}, "
            f"variant {plan.variant or lay.NO_VARIANT}"
        )
        for name, value in plan.params.items():
            self._write_run(f"param {name} = {value!r} ({plan.param_sources[name]})")

    def step_started(self, step: PlannedStep, command: str | None) -> None:
        if step.kind == "set":
            self._write_run(
                f"[{step.label}] start ({'parallel' if step.spec.parallel else 'sequential'})"
            )
            return
        assert self._plan is not None
        path = Path(
            self._layout.step_log(self._plan.variant, self._plan.action, step.path)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._steps[step.path] = path.open("w", encoding="utf-8")
        self._write_step(step, f"$ {command}" if command else "start")
        self._write_run(f"[{step.label}] $ {command}")

    def output(self, step: PlannedStep, line: str) -> None:
        self._write_step(step, line, stamp=False)
        self._write_run(f"[{step.label}] {line}")

    def step_finished(self, step: PlannedStep, result: StepResult) -> None:
        text = _describe(result)
        self._write_step(step, text)
        self._write_run(f"[{step.label}] {text}")
        with self._lock:
            handle = self._steps.pop(step.path, None)
        if handle:
            handle.close()

    def run_finished(self, result: RunResult) -> None:
        self._write_run(f"run {result.status.value} in {result.duration:.1f}s")
        with self._lock:
            for handle in self._steps.values():
                handle.close()
            self._steps.clear()
            if self._run:
                self._run.close()
                self._run = None

    # -- helpers -----------------------------------------------------------------------

    def _write_run(self, text: str) -> None:
        with self._lock:
            if self._run:
                self._run.write(f"{_now()} {text}\n")
                self._run.flush()

    def _write_step(self, step: PlannedStep, text: str, stamp: bool = True) -> None:
        with self._lock:
            handle = self._steps.get(step.path)
            if handle:
                handle.write(f"{_now()} ptk: {text}\n" if stamp else f"{text}\n")
                handle.flush()


def _describe(result: StepResult) -> str:
    text = f"{result.status.value}"
    if result.status in (Status.PASSED, Status.FAILED):
        text += f" in {result.duration:.1f}s"
    if result.exit_code not in (None, 0):
        text += f" (exit code {result.exit_code})"
    if result.attempts > 1:
        text += f" after {result.attempts} attempts"
    if result.message and result.message != f"exit code {result.exit_code}":
        text += f": {result.message}"
    if result.allowed_failure:
        text += " - allowed (continue_on_error)"
    return text
