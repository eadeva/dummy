"""Composition root: the only module that wires concrete adapters to use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .adapters import help_html
from .adapters.config.source import FileConfigSource
from .adapters.credentials_env import EnvSecretResolver
from .adapters.host import SystemHost
from .adapters.logging.files import FileLogObserver
from .adapters.process import SubprocessRunner
from .adapters.python_env import UvPythonEnvManager
from .application.ports import (
    ConfigSource,
    HostEnvironment,
    ProcessRunner,
    PythonEnvManager,
    RunObserver,
)
from .application.use_cases.help import BuildHelp, HelpDocument
from .application.use_cases.project import (
    ExportSchema,
    LoadProject,
    Project,
    ShowConfig,
)
from .application.use_cases.role import Role, resolve_role
from .application.use_cases.run import PreparedRun, PrepareRun, RunAction
from .application.use_cases.variants import VariantService


@dataclass
class App:
    host: HostEnvironment
    load_project: LoadProject
    show_config: ShowConfig
    export_schema: ExportSchema
    runner: ProcessRunner
    python_envs: PythonEnvManager
    build_help: BuildHelp

    def variants(self, project: Project) -> VariantService:
        return VariantService(project)

    def _secrets(self, project: Project) -> EnvSecretResolver:
        return EnvSecretResolver(project.config.credentials, self.host.variables)

    def prepare_run(self, project: Project) -> PrepareRun:
        return PrepareRun(self.host, self._secrets(project))

    def run_action(self, project: Project) -> RunAction:
        return RunAction(
            self.host, self.runner, self.python_envs, self._secrets(project)
        )

    def role(self, project: Project | None) -> Role:
        return resolve_role(project, self.host)

    def write_help(self, doc: HelpDocument, target: Path) -> Path:
        return help_html.write_help(doc, target)

    def open_in_browser(self, path: Path) -> bool:
        return help_html.open_in_browser(path)

    def log_observers(self, prepared: PreparedRun) -> list[RunObserver]:
        return [FileLogObserver(prepared.layout)]


def create_app(
    *,
    source: ConfigSource | None = None,
    host: HostEnvironment | None = None,
    environ: Mapping[str, str] | None = None,
    version: str = __version__,
    runner: ProcessRunner | None = None,
    python_envs: PythonEnvManager | None = None,
) -> App:
    host = host or SystemHost(environ)
    runner = runner or SubprocessRunner()
    return App(
        host=host,
        load_project=LoadProject(source or FileConfigSource(), host, version),
        show_config=ShowConfig(),
        export_schema=ExportSchema(),
        runner=runner,
        python_envs=python_envs
        or UvPythonEnvManager(runner, environ=dict(host.variables)),
        build_help=BuildHelp(version),
    )


def load(start: Path | None = None, **kwargs) -> Project:
    """Convenience for scripts: ``ptk.bootstrap.load()`` -> validated project."""
    return create_app().load_project.execute(start, **kwargs)
