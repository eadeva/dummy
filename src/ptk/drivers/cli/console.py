"""Console presentation of runs and dry runs (driver)."""

from __future__ import annotations

import threading

from rich.console import Console
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ...application.use_cases.run import PreparedRun, RunJob
from ...domain import run_output as display
from ...domain.execution.model import (
    JobPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)
from ...domain.logging import Level

MESSAGE_STYLE = {
    Level.TRACE: "dim",
    Level.DEBUG: "dim",
    Level.INFO: "default",
    Level.WARNING: "yellow",
    Level.ERROR: "bold red",
}
STYLE = {
    Status.PASSED: "green",
    Status.FAILED: "red",
    Status.SKIPPED: "dim",
    Status.CANCELLED: "yellow",
    Status.PENDING: "white",
}


ENTITY_STYLE = {"WORKFLOW": "bold magenta", "JOB": "bold cyan", "STEP": "bold blue"}


def header(console, kind, identity, state, rows=(), *, status=None):
    text = Text(display.boundary(kind, identity, state, console.width))
    text.stylize(ENTITY_STYLE[kind])
    if status is not None:
        start = text.plain.find(str(status).upper(), text.plain.find(" | "))
        if start >= 0:
            text.stylize(STYLE[status], start, start + len(str(status)))
    for row in rows:
        text.append("\n" + row, style="default")
    console.print(text, highlight=False, soft_wrap=True)


class ConsoleObserver:
    """Identify step records consistently, including concurrent jobs and variants."""

    def __init__(
        self,
        console: Console,
        *,
        quiet: bool = False,
        level: Level = Level.INFO,
        job_label: str | None = None,
    ):
        self._console = console
        self._quiet = quiet
        self._level = level
        self._run_prefix = ""
        self._job_label = job_label
        self._lock = threading.Lock()

    def run_started(self, plan: JobPlan) -> None:
        self._job_label = self._job_label or plan.job
        self._run_prefix = display.prefix(self._job_label, plan.variant)
        header(
            self._console,
            "JOB",
            self._job_label,
            "START",
            display.job_rows(plan, verbose=self._level <= Level.DEBUG),
        )

    def step_started(self, step: PlannedStep, command: str | None) -> None:
        self._record(
            Text("\n").join(
                [
                    self._step_boundary(step, "START"),
                    *(
                        Text(row, style="dim")
                        for row in display.step_rows(step, command)
                    ),
                ]
            ),
            step,
        )

    def _step_boundary(self, step, state, status=None):
        width = self._console.width - len(self._run_prefix) - len(step.name) - 3
        text = Text(display.boundary("STEP", "", state, width))
        text.stylize(ENTITY_STYLE["STEP"])
        if status is not None:
            start = text.plain.find(str(status).upper(), text.plain.find(" | "))
            if start >= 0:
                text.stylize(STYLE[status], start, start + len(str(status)))
        return text

    def output(self, step: PlannedStep, line: str) -> None:
        if self._quiet:
            return
        # Captured tools cannot redraw a shared console. Keep progress updates
        # as separate records and interpret ANSI styling without cursor motion.
        line = line.replace("\r\n", "\n").replace("\r", "\n")
        self._record(Text.from_ansi(line), step)

    def message(self, level: Level, text: str, step: PlannedStep | None = None) -> None:
        if level < self._level:
            return
        style = MESSAGE_STYLE[level]
        self._record(Text(f"{level.label}: {text}", style=style), step)

    def step_finished(self, step: PlannedStep, result: StepResult) -> None:
        text = self._step_boundary(step, display.outcome(result), result.status)
        if result.message and result.message != result.status.value:
            text.append("\n" + result.message, style="dim")
        self._record(text, step)

    def run_finished(self, result: RunResult) -> None:
        header(
            self._console,
            "JOB",
            self._job_label,
            f"{str(result.status).upper()} | {result.duration:.1f}s",
            display.result_rows(result),
            status=result.status,
        )

    def _record(self, text: Text, step: PlannedStep | None = None) -> None:
        prefix = Text(
            self._run_prefix + (f"[{step.name}]" if step else "") + " ", style="dim"
        )
        # Expand relative to the tool's text, not the variable-width PTK prefix.
        text.expand_tabs(8)
        self._print(
            Text("\n").join(
                Text.assemble(prefix, line)
                for line in text.split("\n", allow_blank=True)
            )
        )

    def _print(self, text: str | Text) -> None:
        with self._lock:
            self._console.print(text, highlight=False, soft_wrap=True)


def dry_run(
    console: Console,
    prepared: PreparedRun,
    runner: RunJob,
    *,
    show_env: bool = False,
) -> None:
    plan = prepared.plan
    from .graphs import show_graph

    show_graph(
        prepared.project.root,
        plan.job,
        "job",
        {step.name: step.spec for step in plan.steps},
        selected={step.name for step in plan.steps if step.skip_reason is None},
        variant=plan.variant,
        only_step=plan.only_step,
        skipped={
            step.name: step.skip_reason for step in plan.steps if step.skip_reason
        },
    )
    head = f"[bold]{escape(plan.job)}[/] [dim](dry run - nothing is executed)[/]"
    if plan.variant:
        head += f"  variant [bold]{escape(plan.variant)}[/]"
    tree = Tree(head)
    if plan.params:
        params = tree.add("[bold]parameters[/]")
        for name, value in plan.params.items():
            params.add(
                f"{escape(name)} = {escape(repr(value))} [dim]({escape(plan.param_sources[name])})[/]"
            )

    def add(node: Tree, step: PlannedStep) -> None:
        if step.skip_reason:
            node.add(
                f"[dim]– {escape(step.name)}: skipped ({escape(step.skip_reason)})[/]"
            )
            return
        command, python = runner.describe(prepared, step)
        child = node.add(f"[bold blue]{escape(step.name)}[/]  {escape(command)}")
        child.add(
            "needs: " + escape(", ".join(step.spec.needs))
            if step.spec.needs
            else "ready"
        )
        details = []
        if step.spec.generators:
            folder = prepared.layout.build_dir(plan.variant, plan.job, step.path)
            details.append(f"generators: {', '.join(step.spec.generators)} → {folder}")
        if step.cwd not in (".", ""):
            details.append(f"cwd {step.cwd}")
        if python and step.python is not None:
            details.append(f"python: {python}")
        flags = [
            f"timeout {step.spec.timeout:g}s" if step.spec.timeout else "",
            f"retries {step.spec.retries}" if step.spec.retries else "",
            "continue_on_error" if step.spec.continue_on_error else "",
        ]
        details += [f for f in flags if f]
        if details:
            child.add(f"[dim]{escape(', '.join(details))}[/]")
        env = {**step.env, **{k: "********" for k in step.secrets}}
        for key, value in env.items():
            child.add(f"[dim]env {escape(key)}={escape(prepared.mask(value))}[/]")

    for step in plan.steps:
        add(tree, step)
    console.print(tree, highlight=False)
    if show_env:
        console.print("[bold]generated environment[/]")
        for key in sorted(
            k for k in plan.base_env if k.startswith(("PTK_", "VARIANT_"))
        ):
            console.print(
                f"  {escape(key)}={escape(prepared.mask(plan.base_env[key]))}",
                highlight=False,
            )
