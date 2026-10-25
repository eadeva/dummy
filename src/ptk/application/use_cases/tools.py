"""Check and install the tools actions need (use case ``ToolService``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ...domain.errors import PtkError
from ...domain.execution.commands import split_words
from ...domain.execution.environment import prepend_path
from ...domain.execution.model import CommandSpec
from ...domain.suggest import did_you_mean
from ...domain.tools import ToolStatus, check_command, check_version, install_methods
from ..ports import HostEnvironment, ProcessRunner, ToolInstaller
from .project import Project

CHECK_TIMEOUT = 30.0


@dataclass
class SetupResult:
    name: str
    before: ToolStatus
    outcome: str  # "ok", "installed via ...", "would install via ...", "failed: ...", "no method"
    after: ToolStatus | None = None

    @property
    def ok(self) -> bool:
        status = self.after or self.before
        return status.ok or self.outcome.startswith("would install")


class ToolService:
    def __init__(
        self, host: HostEnvironment, runner: ProcessRunner, installer: ToolInstaller
    ):
        self._host = host
        self._runner = runner
        self._installer = installer

    def set_installer(self, installer: ToolInstaller) -> None:
        self._installer = installer

    def paths(self) -> list[str]:
        return self._installer.bin_dirs()

    def environment(self) -> dict[str, str]:
        env = dict(self._host.variables)
        for folder in reversed(self.paths()):
            env = prepend_path(env, folder, os_name=self._host.os_name())
        return env

    def required(self, project: Project, actions: list[str] | None = None) -> list[str]:
        config = project.config
        if not actions:
            return list(config.tools)
        names: list[str] = []
        for action in actions:
            if action not in config.actions:
                raise PtkError(
                    f"unknown action '{action}'{did_you_mean(action, config.actions)}"
                )
            names += [
                t for t in config.actions[action].requires_tools if t not in names
            ]
        return names

    def status(
        self, project: Project, names: list[str] | None = None
    ) -> list[ToolStatus]:
        tools = project.config.tools
        env = self.environment()
        result = []
        for name in names if names is not None else list(tools):
            spec = tools[name]
            argv = split_words(check_command(name, spec), self._host.os_name())
            lines: list[str] = []
            outcome = self._runner.run(
                CommandSpec(
                    argv=argv, cwd=str(project.root), env=env, timeout=CHECK_TIMEOUT
                ),
                lines.append,
            )
            output = "\n".join(lines) if outcome.exit_code == 0 else None
            result.append(check_version(name, spec, output))
        return result

    def problems(self, project: Project, action: str) -> list[ToolStatus]:
        names = project.config.actions[action].requires_tools
        return (
            [s for s in self.status(project, list(names)) if not s.ok] if names else []
        )

    def setup(
        self,
        project: Project,
        names: list[str],
        *,
        dry_run: bool = False,
        allow_system: bool = False,
        out: Callable[[str], None] = lambda _line: None,
    ) -> list[SetupResult]:
        tools = project.config.tools
        results = []
        for before in self.status(project, names):
            if before.ok:
                results.append(SetupResult(before.name, before, "ok"))
                continue
            methods = install_methods(
                tools[before.name], self._host.os_name(), allow_system=allow_system
            )
            if not methods:
                hint = (
                    " (apt/dnf need --allow-system)"
                    if tools[before.name].apt or tools[before.name].dnf
                    else ""
                )
                results.append(
                    SetupResult(before.name, before, f"no install method{hint}")
                )
                continue
            if dry_run:
                results.append(
                    SetupResult(
                        before.name,
                        before,
                        f"would install via {methods[0].describe()}",
                    )
                )
                continue
            errors = []
            for method in methods:
                out(f"{before.name}: {method.describe()}")
                try:
                    self._installer.install(before.name, method, out)
                except PtkError as exc:
                    errors.append(f"{method.kind}: {exc}")
                    out(f"{before.name}: {method.kind} failed - {exc}")
                    continue
                [after] = self.status(project, [before.name])
                if after.ok:
                    results.append(
                        SetupResult(
                            before.name, before, f"installed via {method.kind}", after
                        )
                    )
                    break
                errors.append(f"{method.kind}: installed, but {after.problem}")
            else:
                results.append(
                    SetupResult(before.name, before, "failed: " + "; ".join(errors))
                )
        return results
