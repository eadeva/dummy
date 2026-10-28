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
from ...application.use_cases.role import Role, resolve_role
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
    variant: str | None = None
    clean: bool = False
    re_run: bool = False
    completion: bool = False
    _project: Project | None = field(default=None, repr=False)
    _project_error: PtkError | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)
    _role: Role | None = field(default=None, repr=False)

    def project(self) -> Project:
        if not self._loaded:
            try:
                project = self.app.load_project.execute(
                    config_file=self.config, overrides=self.overrides, ci=self.ci
                )
                if (
                    self.ci is not None
                    and resolve_role(project, self.app.host) != "maintainer"
                ):
                    raise PtkError("--ci/--no-ci is a maintainer-only option")
                if not self.completion:
                    self.app.configure_project(project)
                self._project = project
            except PtkError as exc:
                self._project_error = exc
            self._loaded = True
        if self._project_error is not None:
            raise self._project_error
        assert self._project is not None
        return self._project

    def try_project(self) -> Project | None:
        try:
            return self.project()
        except PtkError:
            return None

    def role(self) -> Role:
        if self._role is None:
            self._role = self.app.role(self.try_project())
        return self._role


def state_of(ctx: click.Context) -> CliState:
    """The CLI state; created from the root options if the root callback has not
    run yet (click resolves sub-commands - our generated jobs - before it)."""
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
            variant=params.get("variant"),
            clean=params.get("clean", False),
            re_run=params.get("re_run", False),
            completion=root.resilient_parsing,
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
