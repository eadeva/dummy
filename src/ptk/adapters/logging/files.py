"""RunObserver writing the logs of the workspace layout (unified logging).

    _logs/<variant>/<job>/run.log            the whole run, each line tagged with its step
    _logs/<variant>/<job>/steps/<step>.log   output of one step
    _logs/<variant>/<job>/events.jsonl       machine-readable events (one JSON per line)
    _logs/<variant>/<job>/run.json           summary of the run (status, steps, params)
    _logs/<variant>/<job>/_history/<run id>/ previous runs (``logging.keep_history``)

The latest run is always directly in the job folder. Everything arrives
already masked (secrets never reach this writer).
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from ...domain import layout as lay
from ...domain.execution.model import (
    JobPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)
from ...domain.logging import Level, history_name, runs_to_prune
from ...domain.reporting.summary import header, run_summary, step_dict
from .transcript import RunTranscript

HISTORY = "_history"
SUMMARY = "run.json"
EVENTS = "events.jsonl"


def _clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def rotate(folder: Path, keep: int) -> None:
    """Move the previous run into ``_history/<run id>/`` and prune old ones."""
    summary = folder / SUMMARY
    if summary.is_file():
        try:
            previous = json.loads(summary.read_text(encoding="utf-8"))["run_id"]
        except (ValueError, KeyError):
            previous = "unknown"
        entries = [p for p in folder.iterdir() if p.name != HISTORY]
        if keep > 0:
            history = folder / HISTORY
            history.mkdir(exist_ok=True)
            taken = [p.name for p in history.iterdir()]
            target = history / history_name(str(previous), taken)
            target.mkdir()
            for entry in entries:
                shutil.move(str(entry), target / entry.name)
            archived = target / SUMMARY
            data = json.loads(archived.read_text(encoding="utf-8"))

            def relocate(value):
                if isinstance(value, str) and (
                    value == str(folder) or value.startswith(str(folder) + os.sep)
                ):
                    return str(target) + value[len(str(folder)) :]
                if isinstance(value, dict):
                    return {k: relocate(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [relocate(v) for v in value]
                return value

            archived.write_text(json.dumps(relocate(data), indent=2), encoding="utf-8")
        else:
            for entry in entries:
                _remove(entry)
    elif folder.is_dir():  # leftovers without a summary (interrupted / old layout)
        for entry in folder.iterdir():
            if entry.name != HISTORY:
                _remove(entry)
    history = folder / HISTORY
    if history.is_dir():
        for name in runs_to_prune([p.name for p in history.iterdir()], keep):
            _remove(history / name)
        if not any(history.iterdir()):
            history.rmdir()


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


class FileLogObserver:
    def __init__(
        self, layout: lay.Layout, *, level: Level = Level.DEBUG, keep_history: int = 3
    ):
        self._layout = layout
        self._level = level
        self._keep = keep_history
        self._lock = threading.Lock()
        self._run: TextIO | None = None
        self._events: TextIO | None = None
        self._steps: dict[tuple[str, ...], TextIO] = {}
        self._plan: JobPlan | None = None
        self._folder: Path | None = None
        self._transcript = RunTranscript(self._line, level=level)

    # -- RunObserver -------------------------------------------------------------------

    def run_started(self, plan: JobPlan) -> None:
        self._plan = plan
        folder = Path(self._layout.job_log_dir(plan.variant, plan.job))
        folder.mkdir(parents=True, exist_ok=True)
        rotate(folder, self._keep)
        self._folder = folder
        self._run = (folder / "run.log").open("w", encoding="utf-8")
        self._events = (folder / EVENTS).open("w", encoding="utf-8")
        self._write_summary(
            {**header(plan), "status": "running", "started_at": _timestamp()}
        )
        self._transcript.run_started(plan)
        for name, value in plan.params.items():
            self._line(f"param {name} = {value!r} ({plan.param_sources[name]})")
        self._event("run_started", params=plan.params, param_sources=plan.param_sources)

    def step_started(self, step: PlannedStep, command: str | None) -> None:
        assert self._plan is not None
        path = Path(
            self._layout.step_log(self._plan.variant, self._plan.job, step.path)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._steps[step.path] = path.open("w", encoding="utf-8")
        self._step_line(step, f"$ {command}" if command else "start")
        self._transcript.step_started(step, command)
        self._event("step_started", step=step.label, kind=step.kind, command=command)

    def output(self, step: PlannedStep, line: str) -> None:
        self._step_line(step, line, stamp=False)
        self._transcript.output(step, line)

    def message(self, level: Level, text: str, step: PlannedStep | None = None) -> None:
        if level < self._level:
            return
        self._transcript.message(level, text, step)
        if step is not None:
            self._step_line(step, f"{level.label}: {text}")
        self._event(
            "message", level=level.label, text=text, step=step.label if step else None
        )

    def step_finished(self, step: PlannedStep, result: StepResult) -> None:
        text = describe(result)
        self._step_line(step, text)
        self._transcript.step_finished(step, result)
        self._event("step_finished", **step_dict(result))
        with self._lock:
            handle = self._steps.pop(step.path, None)
        if handle:
            handle.close()

    def run_finished(self, result: RunResult) -> None:
        self._transcript.run_finished(result)
        self._event(
            "run_finished",
            status=result.status.value,
            duration=round(result.duration, 3),
        )
        assert self._plan is not None
        assert self._folder is not None
        snapshot = self._folder / "report-inputs"
        source = Path(self._plan.dirs["reports_dir"])
        if source.is_dir():
            shutil.copytree(source, snapshot, dirs_exist_ok=True)
        summary = run_summary(self._plan, result)
        summary["reports_dir"] = str(snapshot)
        self._write_summary(summary)
        with self._lock:
            for handle in self._steps.values():
                handle.close()
            self._steps.clear()
            for handle in (self._run, self._events):
                if handle:
                    handle.close()
            self._run = self._events = None

    # -- helpers -----------------------------------------------------------------------

    def _write_summary(self, data: dict[str, Any]) -> None:
        assert self._folder is not None
        text = json.dumps(data, indent=2, default=str)
        (self._folder / SUMMARY).write_text(text + "\n", encoding="utf-8")

    def _event(self, name: str, **fields: Any) -> None:
        assert self._plan is not None
        record = {"ts": _timestamp(), "event": name, "run_id": self._plan.run_id}
        record.update({k: v for k, v in fields.items() if v is not None})
        with self._lock:
            if self._events:
                self._events.write(json.dumps(record, default=str) + "\n")
                self._events.flush()

    def _line(self, text: str) -> None:
        with self._lock:
            if self._run:
                self._run.write(
                    "".join(f"{_clock()} {line}\n" for line in text.split("\n"))
                )
                self._run.flush()

    def _step_line(self, step: PlannedStep, text: str, stamp: bool = True) -> None:
        with self._lock:
            handle = self._steps.get(step.path)
            if handle:
                handle.write(f"{_clock()} ptk: {text}\n" if stamp else f"{text}\n")
                handle.flush()


def describe(result: StepResult) -> str:
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
