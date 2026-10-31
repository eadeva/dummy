"""Composition root: the only module that wires concrete adapters to use cases."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__
from .adapters.config.source import FileConfigSource
from .adapters.host import SystemHost
from .adapters.workspace import WorkspaceDiscovery
from .application.use_cases.project import LoadProject
from .application.use_cases.role import resolve_role, role_for_ids
from .domain.errors import PtkError

if TYPE_CHECKING:
    from .adapters.tools import SystemToolInstaller
    from .application.ports import (
        ConfigSource,
        HostEnvironment,
        ProcessRunner,
        Prompter,
        PythonEnvManager,
        RunObserver,
        SecretProvider,
    )
    from .application.use_cases.artifacts import ResolveDestination
    from .application.use_cases.authoring import SetupAuthoring
    from .application.use_cases.configs import SharedConfigs
    from .application.use_cases.credentials import CredentialService
    from .application.use_cases.help import BuildHelp, HelpDocument
    from .application.use_cases.hooks import EnsureHooks
    from .application.use_cases.init import InitProject
    from .application.use_cases.project import (
        ExportSchema,
        Project,
        ShowConfig,
    )
    from .application.use_cases.report import ReportService
    from .application.use_cases.role import Role
    from .application.use_cases.run import (
        PreparedRun,
        PrepareRun,
        RunJob,
    )
    from .application.use_cases.setup import Doctor, Environment
    from .application.use_cases.tools import ToolService
    from .application.use_cases.variants import VariantService
    from .application.use_cases.vscode import VSCodeTasks


@dataclass
class App:
    host: HostEnvironment
    load_project: LoadProject
    version: str = __version__
    started_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    workspace: WorkspaceDiscovery = field(
        default_factory=WorkspaceDiscovery, repr=False
    )
    _credentials: dict[int, CredentialService] = field(default_factory=dict, repr=False)
    _workspace_roles: dict[Path, Role] = field(default_factory=dict, repr=False)

    @cached_property
    def init_project(self) -> InitProject:
        from .adapters.scaffold import FileProjectScaffold
        from .application.use_cases.init import InitProject

        return InitProject(FileProjectScaffold(), self.host)

    @cached_property
    def show_config(self) -> ShowConfig:
        from .application.use_cases.project import ShowConfig

        return ShowConfig()

    @cached_property
    def export_schema(self) -> ExportSchema:
        from .application.use_cases.project import ExportSchema

        return ExportSchema()

    @cached_property
    def runner(self) -> ProcessRunner:
        from .adapters.process import SubprocessRunner

        return SubprocessRunner()

    @cached_property
    def prompter(self) -> Prompter:
        from .adapters.credentials.prompt import ConsolePrompter

        return ConsolePrompter(self.host.is_ci)

    @cached_property
    def _uv(self) -> str:
        from .adapters.python_env import find_uv

        return find_uv(dict(self.host.variables))

    @cached_property
    def python_envs(self) -> PythonEnvManager:
        from .adapters.python_env import UvPythonEnvManager

        return UvPythonEnvManager(
            self.runner, uv=self._uv, environ=dict(self.host.variables)
        )

    @cached_property
    def installer(self) -> SystemToolInstaller:
        from .adapters.tools import SystemToolInstaller

        return SystemToolInstaller(self.runner, self.host.variables, uv=self._uv)

    @cached_property
    def tools(self) -> ToolService:
        from .application.use_cases.tools import ToolService

        return ToolService(self.host, self.runner, self.installer)

    @cached_property
    def shared_configs(self) -> SharedConfigs:
        from .adapters.shared_configs import PackageConfigFiles
        from .application.use_cases.configs import SharedConfigs

        return SharedConfigs(PackageConfigFiles())

    @cached_property
    def _environment(self) -> Environment:
        from .application.use_cases.setup import Environment

        return Environment(self.host, self.runner, self._uv)

    @cached_property
    def hooks(self) -> EnsureHooks:
        from .adapters.hooks import GitHooks
        from .application.use_cases.hooks import EnsureHooks

        return EnsureHooks(GitHooks(self.runner, self.host.variables, uv=self._uv))

    @cached_property
    def doctor(self) -> Doctor:
        from .application.use_cases.setup import Doctor

        return Doctor(
            self._environment, self.tools, self.shared_configs, self.version, self.hooks
        )

    @cached_property
    def build_help(self) -> BuildHelp:
        from .application.use_cases.help import BuildHelp

        return BuildHelp(self.version)

    @cached_property
    def vscode_tasks(self) -> VSCodeTasks:
        from .adapters.vscode_file import TasksFile
        from .application.use_cases.vscode import VSCodeTasks

        return VSCodeTasks(TasksFile)

    @cached_property
    def setup_authoring(self) -> SetupAuthoring:
        from .adapters.authoring import AuthoringFiles
        from .application.use_cases.authoring import SetupAuthoring

        return SetupAuthoring(AuthoringFiles(), self.version)

    @cached_property
    def reports(self) -> ReportService:
        from .adapters.reporting.store import FileReportStore
        from .application.use_cases.report import ReportService

        return ReportService(FileReportStore(self.host.variables), self.version)

    @cached_property
    def secret_providers(self) -> dict[str, SecretProvider]:
        return default_secret_providers(self.host.variables, self.prompter)

    def variants(self, project: Project) -> VariantService:
        from .application.use_cases.variants import VariantService

        return VariantService(project)

    def credentials(self, project: Project) -> CredentialService:
        """One service per project and ptk process (caches values, vault unlocked once)."""
        from .application.use_cases.credentials import CredentialService

        key = id(project)
        if key not in self._credentials:
            definitions = project.config.credentials
            workspace = self.workspace.root(project.root)
            if workspace is not None:
                workspace_id = hashlib.sha256(str(workspace).encode()).hexdigest()[:12]
                definitions = {
                    name: spec.model_copy(
                        update={
                            "namespace": spec.namespace
                            or "vmr/"
                            + workspace_id
                            + "/"
                            + hashlib.sha256(
                                json.dumps(
                                    spec.model_dump(mode="json"), sort_keys=True
                                ).encode()
                            ).hexdigest()[:12]
                        }
                    )
                    for name, spec in definitions.items()
                }
            self._credentials[key] = CredentialService(
                definitions,
                self.secret_providers,
                self.host,
                self.runner,
                root=project.root,
            )
        return self._credentials[key]

    def versions(self):
        from .adapters.versioning import VersionIO
        from .application.use_cases.versioning import VersionService

        def dependency(member, alias):
            root = self.workspace.root(member.root)
            entries = self.workspace.repositories(root) if root else {}
            if alias not in entries:
                raise PtkError(
                    f"version dependency {alias!r} is not a repository in this VMR"
                )
            # A fresh reader avoids leaking another repository's include state.
            return LoadProject(FileConfigSource(), self.host, __version__).execute(
                config_file=entries[alias], ci=member.ci
            )

        return VersionService(VersionIO(self.runner, self.host), dependency)

    def prepare_run(self, project: Project) -> PrepareRun:
        from .application.use_cases.run import PrepareRun

        return PrepareRun(
            self.host,
            self.credentials(project),
            clock=lambda: self.started_at,
            tools=self.tools,
            versions=self.versions(),
            ptk_version=__version__,
            git=self.git_metadata,
        )

    @cached_property
    def git_metadata(self):
        from .adapters.git_metadata import GitMetadata

        return GitMetadata(self.runner, self.host)

    def artifacts(self) -> ResolveDestination:
        from .adapters.github_context import github_context
        from .application.use_cases.artifacts import ResolveDestination

        return ResolveDestination(
            self.versions(),
            lambda: github_context(self.host.variables),
            self.started_at,
            self.host.variables,
            git=self.git_metadata,
        )

    def run_job(self, project: Project) -> RunJob:
        from .adapters.builtins import (
            file_cleaner,
            files_copy,
            report_import,
        )
        from .adapters.reporting.runner import ReportingRunner
        from .adapters.variant_files import variant_writer
        from .adapters.versioning import version_generator
        from .application.use_cases.run import BUILTINS, RunJob, layout_of
        from .domain.variants.generators import GENERATORS

        layout = layout_of(project)

        def sync(step, out, ctx):
            names = step.with_.get("names")
            if isinstance(names, str):
                names = [names]
            for item in self.shared_configs.sync(project, names):
                out(f"{item.path}: {item.status}")
            return 0

        def ensure(step, out, ctx):
            names = step.with_.get("tools", list(project.config.tools))
            if isinstance(names, str):
                names = [names]
            if not isinstance(names, list) or any(
                n not in project.config.tools for n in names
            ):
                raise PtkError("tools.ensure needs declared tool names")
            results = self.tools.setup(
                project,
                names,
                allow_system=bool(step.with_.get("allow_system", False)),
                out=out,
            )
            return 0 if all(r.ok for r in results) else 1

        builtins = {
            **BUILTINS,
            "report.import": report_import,
            "configs.sync": sync,
            "tools.ensure": ensure,
            "files.copy": files_copy,
            "files.clean": file_cleaner(
                [
                    layout.root / n
                    for n in (layout.builds, layout.bin, layout.logs, layout.reports)
                ]
            ),
            "version.generate": version_generator,
        }

        def verify_tools(job, env, cwd):
            names = project.config.jobs[job].required_tool_names
            statuses = self.tools.status(project, names, env=env, cwd=cwd)
            problems = [s for s in statuses if not s.ok]
            if problems:
                raise PtkError(
                    "tool requirements are not satisfied in the command environment: "
                    + "; ".join(f"{s.name}: {s.problem}" for s in problems)
                )

            return statuses

        from .adapters.output_cache import LocalOutputCache

        return RunJob(
            self.host,
            self.runner,
            self.python_envs,
            builtins=builtins,
            path_provider=lambda: self.tools.paths(project),
            environment_check=verify_tools,
            version_writer=self.versions().write,
            variant_writer=variant_writer(GENERATORS),
            reporting_runner=ReportingRunner(self.runner, self.host.os_name()),
            output_cache=LocalOutputCache(project.root),
        )

    def role(self, project: Project | None) -> Role:
        return resolve_role(project, self.host)

    def workspace_role(self, root: Path) -> Role:
        if root not in self._workspace_roles:
            self._workspace_roles[root] = role_for_ids(
                self.load_project.maintainers(root), self.host
            )
        return self._workspace_roles[root]

    def write_help(self, doc: HelpDocument, target: Path) -> Path:
        from .adapters import help_html

        return help_html.write_help(doc, target)

    def open_in_browser(self, path: Path) -> bool:
        from .adapters import help_html

        return help_html.open_in_browser(path)

    def log_observers(
        self, prepared: PreparedRun, *, verbose: int = 0
    ) -> list[RunObserver]:
        from .adapters.logging.files import FileLogObserver
        from .domain.logging import file_level

        return [
            FileLogObserver(
                prepared.layout,
                level=file_level("trace" if verbose >= 2 else "debug"),
                keep_history=prepared.project.config.logging_history_backups,
            )
        ]


def create_app(
    *,
    source: ConfigSource | None = None,
    host: HostEnvironment | None = None,
    environ: Mapping[str, str] | None = None,
    version: str = __version__,
    runner: ProcessRunner | None = None,
    python_envs: PythonEnvManager | None = None,
    prompter: Prompter | None = None,
    secret_providers: dict[str, SecretProvider] | None = None,
    workspace: WorkspaceDiscovery | None = None,
    started_at: datetime | None = None,
) -> App:
    host = host or SystemHost(environ)
    app = App(
        host=host,
        load_project=LoadProject(source or FileConfigSource(), host, version),
        version=version,
        workspace=workspace if workspace is not None else WorkspaceDiscovery(),
        started_at=started_at
        if started_at is not None
        else datetime.now().astimezone(),
    )
    # cached_property allows explicit adapters without constructing unused defaults.
    for name, adapter in (
        ("runner", runner),
        ("python_envs", python_envs),
        ("prompter", prompter),
        ("secret_providers", secret_providers),
    ):
        if adapter:
            setattr(app, name, adapter)
    return app


def default_secret_providers(
    environ: Mapping[str, str], prompter: Prompter
) -> dict[str, SecretProvider]:
    from .adapters.credentials.env import EnvProvider
    from .adapters.credentials.gopass import GopassProvider
    from .adapters.credentials.keyring_provider import KeyringProvider
    from .adapters.credentials.prompt import PromptProvider
    from .adapters.credentials.vault import Vault, VaultProvider, default_vault_file

    def vault_password(confirm: bool) -> str:
        if environ.get("PTK_VAULT_PASSWORD"):
            return environ["PTK_VAULT_PASSWORD"]
        if not prompter.interactive():
            raise PtkError(
                "the vault is locked: set PTK_VAULT_PASSWORD or run ptk in a terminal"
            )
        password = prompter.secret("ptk vault master password")
        if confirm and prompter.secret("repeat the master password") != password:
            raise PtkError("the passwords do not match")
        return password

    vault = Vault(default_vault_file(environ), vault_password)
    return {
        "env": EnvProvider(environ),
        "keyring": KeyringProvider(),
        "gopass": GopassProvider(),
        "vault": VaultProvider(vault),
        "prompt": PromptProvider(prompter),
    }


def load(start: Path | None = None, **kwargs) -> Project:
    """Convenience for scripts: ``ptk.bootstrap.load()`` -> validated project."""
    return create_app().load_project.execute(start, **kwargs)
