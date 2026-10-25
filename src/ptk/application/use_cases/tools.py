"""Check and install the tools actions need (use case ``ToolService``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from ...domain.config.model import ToolSpec
from ...domain.errors import PtkError
from ...domain.execution.commands import split_words
from ...domain.execution.environment import base_environment, prepend_path
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


def tools_for_actions(project: Project, actions: list[str] | None = None) -> Project:
    """Apply per-tool settings without modifying other actions or the source project."""
    config = project.config.model_copy(deep=True)
    selections = [config.requires_tools] if actions is None else []
    for name in actions or []:
        if name not in config.actions:
            raise PtkError(f"unknown action '{name}'")
        selections.append(config.actions[name].requires_tools)
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
                    f"selected actions require different settings for tool '{name}'; install per action"
                )
            overrides[name] = effective
    config.tools.update(overrides)
    selected = None
    if actions:
        selected = list(
            dict.fromkeys(
                n
                for action in actions
                for n in config.actions[action].required_tool_names
            )
        )
        for action in actions:
            spec = config.actions[action]
            if len(actions) == 1 and spec.environment is not None:
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

    def set_installer(self, installer: ToolInstaller) -> None:
        self._installer = installer

    def paths(self, project: Project | None = None) -> list[str]:
        if project is None:
            return []
        names = (
            project.selected_tools
            if project.selected_tools is not None
            else self.required(project)
        )
        return self._installer.bin_dirs({n: project.config.tools[n] for n in names})

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

    def required(self, project: Project, actions: list[str] | None = None) -> list[str]:
        config = project.config
        if not actions:
            if "requires_tools" in config.model_fields_set:
                return [n for n, v in config.requires_tools.items() if v is not False]
            return list(config.tools)
        names: list[str] = []
        for action in actions:
            if action not in config.actions:
                raise PtkError(
                    f"unknown action '{action}'{did_you_mean(action, config.actions)}"
                )
            names += [
                t for t in config.actions[action].required_tool_names if t not in names
            ]
        return names

    def status(
        self, project: Project, names: list[str] | None = None, *, env=None, cwd=None
    ) -> list[ToolStatus]:
        tools = project.config.tools
        env = self.environment(project) if env is None else env
        result = []
        for name in names if names is not None else list(tools):
            spec = tools[name]
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
            result.append(check_version(name, spec, output))
        return result

    def problems(self, project: Project, action: str) -> list[ToolStatus]:
        project = tools_for_actions(project, [action])
        names = project.config.actions[action].required_tool_names
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
