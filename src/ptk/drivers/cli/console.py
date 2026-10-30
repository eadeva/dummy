"""Console presentation of runs and dry runs (driver)."""

from __future__ import annotations

import threading

from rich.console import Console
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ...application.use_cases.run import PreparedRun, RunJob
from ...domain.execution.model import (
    JobPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)
from ...domain.layout import NO_VARIANT
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
ICON = {
    Status.PASSED: "✔",
    Status.FAILED: "✘",
    Status.SKIPPED: "–",
    Status.CANCELLED: "■",
    Status.PENDING: "·",
}


class ConsoleObserver:
    """Identify step records consistently, including concurrent jobs and variants."""

    def __init__(
        self, console: Console, *, quiet: bool = False, level: Level = Level.INFO
    ):
        self._console = console
        self._quiet = quiet
        self._level = level
        self._run_prefix = ""
        self._lock = threading.Lock()

    def run_started(self, plan: JobPlan) -> None:
        self._run_prefix = f"[{plan.job}][{plan.variant or NO_VARIANT}]"
        if plan.only_step:
            self._print(
                f"[yellow]Only step {escape(plan.only_step)}; prerequisites not run: {escape(', '.join(plan.omitted_dependencies) or 'none')}. Required outputs must already exist.[/]"
            )
        variant = f" [dim]variant[/] {escape(plan.variant)}" if plan.variant else ""
        self._print(
            f"[bold]ptk {escape(plan.job)}[/]{variant} [dim]run {plan.run_id}[/]"
        )

    def step_started(self, step: PlannedStep, command: str | None) -> None:
        self._record(Text.assemble(("▶ ", "bold cyan"), (command or "", "dim")), step)

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
        style = STYLE[result.status]
        message = result.message if result.message != result.status.value else ""
        timing = (
            f" {result.duration:.1f}s"
            if result.status in (Status.PASSED, Status.FAILED)
            else ""
        )
        text = Text(f"{ICON[result.status]} {result.status.value}{timing}", style=style)
        if message:
            text.append(f" {message}", style="dim")
        if result.allowed_failure:
            text.append(" (allowed)", style="yellow")
        self._record(text, step)

    def run_finished(self, result: RunResult) -> None:
        pass

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


def summary(console: Console, result: RunResult) -> None:
    tree = Tree(
        f"[bold]{escape(result.job)}[/] [{STYLE[result.status]}]{result.status.value}[/] "
        f"in {result.duration:.1f}s"
    )

    def add(node: Tree, step: StepResult) -> None:
        style = STYLE[step.status]
        timing = (
            f" {step.duration:.1f}s"
            if step.status in (Status.PASSED, Status.FAILED)
            else ""
        )
        show = (
            step.message
            and step.status is not Status.PASSED
            and step.message != step.status.value
        )
        extra = f" [dim]{escape(step.message)}[/]" if show else ""
        if step.allowed_failure:
            extra += " [yellow](allowed)[/]"
        node.add(f"[{style}]{ICON[step.status]} {escape(step.name)}{timing}[/]{extra}")

    for step in result.steps:
        add(tree, step)
    console.print(tree, highlight=False)
    if result.log_file:
        console.print(
            f"[dim]log: {escape(result.log_file)}[/]", highlight=False, soft_wrap=True
        )


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
        child = node.add(f"[bold cyan]{escape(step.name)}[/]  {escape(command)}")
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
