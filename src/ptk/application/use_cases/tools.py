"""Check and install the tools jobs need (use case ``ToolService``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from ...domain.config.model import ToolSpec
from ...domain.errors import PtkError
from ...domain.execution.commands import split_words
from ...domain.execution.environment import base_environment, prepend_path
from ...domain.execution.model import CommandSpec
from ...domain.suggest import did_you_mean
from ...domain.tools import (
    ToolStatus,
    check_command,
    check_version,
    install_methods,
    tool_applies,
)
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


def tools_for_jobs(project: Project, jobs: list[str] | None = None) -> Project:
    """Apply per-tool settings without modifying other jobs or the source project."""
    config = project.config.model_copy(deep=True)
    selections = [config.requires_tools] if jobs is None else []
    for name in jobs or []:
        if name not in config.jobs:
            raise PtkError(f"unknown job '{name}'")
        selections.append(config.jobs[name].requires_tools)
    overrides = {}
    for selection in selections:
        for name, spec in selection.items():
            if spec is False or name not in config.tools:
                continue
            base = project.config.tools[name]
            effective = (
                ToolSpec.model_validate(
                    {**base.model_dump(), **spec.model_dump(exclude_unset=True)}
                )
                if isinstance(spec, ToolSpec)
                else base
            )
            if name in overrides and overrides[name] != effective:
                raise PtkError(
                    f"selected jobs require different settings for tool '{name}'; install per job"
                )
            overrides[name] = effective
    config.tools.update(overrides)
    selected = None
    if jobs:
        selected = list(
            dict.fromkeys(
                n for job in jobs for n in config.jobs[job].required_tool_names
            )
        )
        for job in jobs:
            spec = config.jobs[job]
            if len(jobs) == 1 and spec.environment is not None:
                config.environment = config.environment.model_copy(
                    update=spec.environment.model_dump(exclude_unset=True)
                )
            for step in spec.walk_steps():
                if step.uses == "tools.ensure":
                    names = step.with_.get("tools", spec.required_tool_names)
                    if isinstance(names, str):
                        names = [names]
                    selected.extend(
                        n for n in names if n in config.tools and n not in selected
                    )
    return replace(project, config=config, selected_tools=selected)


class ToolService:
    def __init__(
        self, host: HostEnvironment, runner: ProcessRunner, installer: ToolInstaller
    ):
        self._host = host
        self._runner = runner
        self._installer = installer

    def paths(self, project: Project | None = None) -> list[str]:
        if project is None:
            return []
        names = (
            project.selected_tools
            if project.selected_tools is not None
            else self.required(project)
        )
        return self._installer.bin_dirs(
            {
                n: project.config.tools[n]
                for n in names
                if tool_applies(project.config.tools[n], self._host.os_name())
            }
        )

    def clean_environment(self, env):
        return self._installer.clean_environment(env)

    def environment(self, project: Project) -> dict[str, str]:
        spec = project.config.environment
        env = base_environment(
            self.clean_environment(self._host.variables),
            os_name=self._host.os_name(),
            isolate=spec.isolate,
            keep=spec.keep,
            set_=spec.set,
            unset=spec.unset,
            path_prepend=spec.path_prepend,
            path_append=spec.path_append,
            inherit_path=spec.inherit_path,
        )
        for folder in reversed(self.paths(project)):
            env = prepend_path(env, folder, os_name=self._host.os_name())
        return env

    def required(self, project: Project, jobs: list[str] | None = None) -> list[str]:
        config = project.config
        if not jobs:
            if "requires_tools" in config.model_fields_set:
                return [n for n, v in config.requires_tools.items() if v is not False]
            return list(config.tools)
        names: list[str] = []
        for job in jobs:
            if job not in config.jobs:
                raise PtkError(f"unknown job '{job}'{did_you_mean(job, config.jobs)}")
            names += [t for t in config.jobs[job].required_tool_names if t not in names]
        return names

    def status(
        self, project: Project, names: list[str] | None = None, *, env=None, cwd=None
    ) -> list[ToolStatus]:
        tools = project.config.tools
        env = self.environment(project) if env is None else env
        result = []
        for name in names if names is not None else list(tools):
            spec = tools[name]
            if not tool_applies(spec, self._host.os_name()):
                continue
            argv = split_words(check_command(name, spec), self._host.os_name())
            lines: list[str] = []
            outcome = self._runner.run(
                CommandSpec(
                    argv=argv,
                    cwd=str(cwd or project.root),
                    env=env,
                    timeout=CHECK_TIMEOUT,
                ),
                lines.append,
            )
            output = "\n".join(lines) if outcome.exit_code == 0 else None
            path = next((v for k, v in env.items() if k.upper() == "PATH"), "")
            source = self._runner.which(argv[0], path=path) or ""
            result.append(replace(check_version(name, spec, output), source=source))
        return result

    def problems(self, project: Project, job: str) -> list[ToolStatus]:
        project = tools_for_jobs(project, [job])
        names = project.config.jobs[job].required_tool_names
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
        project = replace(project, selected_tools=names)
        tools = project.config.tools
        results = []
        for before in self.status(project, names):
            if before.ok:
                results.append(SetupResult(before.name, before, "ok"))
                continue
            if not tools[before.name].docker and self._host.is_docker():
                results.append(
                    SetupResult(
                        before.name,
                        before,
                        "installation disabled inside Docker (docker: false)",
                    )
                )
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
