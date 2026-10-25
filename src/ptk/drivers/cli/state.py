"""Shared CLI state: consoles, lazily loaded project, error handling."""

from __future__ import annotations

import functools
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console

from ...application.use_cases.project import Project
from ...application.use_cases.role import Role
from ...bootstrap import App, create_app
from ...domain.errors import ConfigError, PtkError

console = Console()
err_console = Console(stderr=True)


@dataclass
class CliState:
    app: App
    config: Path | None = None
    overrides: tuple[str, ...] = ()
    ci: bool | None = None
    verbose: int = 0
    _project: Project | None = field(default=None, repr=False)

    def project(self) -> Project:
        if self._project is None:
            self._project = self.app.load_project.execute(
                config_file=self.config, overrides=self.overrides, ci=self.ci
            )
        self.app.configure_project(self._project)
        return self._project

    def try_project(self) -> Project | None:
        try:
            return self.project()
        except PtkError:
            return None

    def role(self) -> Role:
        return self.app.role(self.try_project())


def state_of(ctx: click.Context) -> CliState:
    """The CLI state; created from the root options if the root callback has not
    run yet (click resolves sub-commands - our generated actions - before it)."""
    current = ctx
    while current is not None:
        if isinstance(current.obj, CliState):
            return current.obj
        current = current.parent
    root = ctx.find_root()
    if not isinstance(root.obj, CliState):
        params = root.params
        root.obj = CliState(
            app=create_app(),
            config=params.get("config"),
            overrides=tuple(
                v for v in (params.get("overrides") or ()) if not v.startswith("vh.")
            ),
            ci=params.get("ci"),
            verbose=params.get("verbose") or 0,
        )
    return root.obj


def report_error(exc: PtkError) -> None:
    if isinstance(exc, ConfigError):
        err_console.print("[bold red]error:[/] invalid configuration")
        for problem in exc.problems:
            err_console.print(
                f"  {problem}", markup=False, highlight=False, soft_wrap=True
            )
    else:
        err_console.print(f"[bold red]error:[/] {exc}", highlight=False, soft_wrap=True)


def guarded(fn):
    """Turn expected errors into clean messages and exit code 2."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except PtkError as exc:
            report_error(exc)
            sys.exit(2)

    return wrapper
