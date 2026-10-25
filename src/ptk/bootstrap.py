"""Composition root: the only module that wires concrete adapters to use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .adapters import help_html
from .adapters.builtins import (
    file_cleaner,
    files_copy,
    report_import,
    variant_generator,
)
from .adapters.config.source import FileConfigSource
from .adapters.credentials.env import EnvProvider
from .adapters.credentials.gopass import GopassProvider
from .adapters.credentials.keyring_provider import KeyringProvider
from .adapters.credentials.prompt import ConsolePrompter, PromptProvider
from .adapters.credentials.vault import Vault, VaultProvider, default_vault_file
from .adapters.host import SystemHost
from .adapters.logging.files import FileLogObserver
from .adapters.plugins import PluginInstaller, load_plugins
from .adapters.process import SubprocessRunner
from .adapters.python_env import UvPythonEnvManager, find_uv
from .adapters.reporting.store import FileReportStore
from .adapters.scaffold import FileProjectScaffold
from .adapters.shared_configs import PackageConfigFiles
from .adapters.tools import SystemToolInstaller
from .adapters.vscode_file import TasksFile
from .application.ports import (
    ConfigSource,
    HostEnvironment,
    ProcessRunner,
    Prompter,
    PythonEnvManager,
    RunObserver,
    SecretProvider,
)
from .application.use_cases.configs import SharedConfigs
from .application.use_cases.credentials import CredentialService
from .application.use_cases.help import BuildHelp, HelpDocument
from .application.use_cases.init import InitProject
from .application.use_cases.project import (
    ExportSchema,
    LoadProject,
    Project,
    ShowConfig,
)
from .application.use_cases.report import ReportService
from .application.use_cases.role import Role, resolve_role
from .application.use_cases.run import (
    BUILTINS,
    PreparedRun,
    PrepareRun,
    RunAction,
    layout_of,
)
from .application.use_cases.setup import Doctor, Environment, SelfSetup
from .application.use_cases.tools import ToolService
from .application.use_cases.variants import VariantService
from .application.use_cases.vscode import VSCodeTasks
from .domain.errors import PtkError
from .domain.logging import file_level
from .domain.variants.generators import GENERATORS


@dataclass
class App:
    host: HostEnvironment
    init_project: InitProject
    load_project: LoadProject
    show_config: ShowConfig
    export_schema: ExportSchema
    runner: ProcessRunner
    python_envs: PythonEnvManager
    build_help: BuildHelp
    vscode_tasks: VSCodeTasks
    reports: ReportService
    shared_configs: SharedConfigs
    tools: ToolService
    doctor: Doctor
    self_setup: SelfSetup
    installer: SystemToolInstaller
    prompter: Prompter
    secret_providers: dict[str, SecretProvider]
    _plugin_cache: dict = field(default_factory=dict, repr=False)
    _active_plugins: tuple | None = field(default=None, repr=False)
    _base_providers: dict | None = field(default=None, repr=False)
    _credentials: dict[int, CredentialService] = field(default_factory=dict, repr=False)

    def configure_project(self, project: Project):
        key = tuple(project.config.plugins)
        if key not in self._plugin_cache:
            self._plugin_cache[key] = load_plugins(list(key))
        plugins = self._plugin_cache[key]
        if self._active_plugins != key:
            if self._base_providers is None:
                self._base_providers = dict(self.secret_providers)
            providers = dict(self._base_providers)
            for name, factory in plugins["secret_providers"].items():
                provider = factory()
                if not all(
                    hasattr(provider, attr)
                    for attr in (
                        "name",
                        "can_store",
                        "available",
                        "get",
                        "store",
                        "remove",
                    )
                ):
                    raise PtkError(
                        f"secret provider '{name}' does not implement SecretProvider"
                    )
                providers[name] = provider
            self.secret_providers = providers
            self._credentials.clear()
            self.tools.set_installer(
                PluginInstaller(self.installer, plugins["installers"])
            )
            self.reports = ReportService(
                FileReportStore(
                    self.host.variables,
                    plugins["reporters"],
                    plugins["report_contributors"],
                ),
                self.reports.version,
            )
            self._active_plugins = key
        formats = {"json", "junit", "html", "markdown", "github"} | plugins[
            "reporters"
        ].keys()
        for name in project.config.reporting.formats:
            if name not in formats:
                raise PtkError(f"reporter '{name}' is not enabled")
        for credential in project.config.credentials.values():
            for name in credential.providers:
                if name not in self.secret_providers:
                    raise PtkError(f"secret provider '{name}' is not enabled")
        for tool in project.config.tools.values():
            for name in tool.installers:
                if name not in plugins["installers"]:
                    raise PtkError(f"installer '{name}' is not enabled")
        return plugins

    def variants(self, project: Project) -> VariantService:
        return VariantService(project)

    def credentials(self, project: Project) -> CredentialService:
        """One service per project and ptk process (caches values, vault unlocked once)."""
        self.configure_project(project)
        key = id(project)
        if key not in self._credentials:
            self._credentials[key] = CredentialService(
                project.config.credentials,
                self.secret_providers,
                self.host,
                self.runner,
            )
        return self._credentials[key]

    def prepare_run(self, project: Project) -> PrepareRun:
        return PrepareRun(self.host, self.credentials(project), tools=self.tools)

    def run_action(self, project: Project) -> RunAction:
        plugins = self.configure_project(project)
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
            "variant.generate": variant_generator(
                {**GENERATORS, **plugins["generators"]}
            ),
            **plugins["steps"],
        }
        return RunAction(
            self.host,
            self.runner,
            self.python_envs,
            builtins=builtins,
            path_provider=self.tools.paths,
        )

    def role(self, project: Project | None) -> Role:
        return resolve_role(project, self.host)

    def write_help(self, doc: HelpDocument, target: Path) -> Path:
        return help_html.write_help(doc, target)

    def open_in_browser(self, path: Path) -> bool:
        return help_html.open_in_browser(path)

    def log_observers(self, prepared: PreparedRun) -> list[RunObserver]:
        logging = prepared.project.config.logging
        return [
            FileLogObserver(
                prepared.layout,
                level=file_level(logging.level),
                keep_history=logging.keep_history,
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
) -> App:
    host = host or SystemHost(environ)
    runner = runner or SubprocessRunner()
    prompter = prompter or ConsolePrompter(host.is_ci)
    uv = find_uv(dict(host.variables))
    installer = SystemToolInstaller(runner, host.variables, uv=uv)
    tools = ToolService(host, runner, installer)
    configs = SharedConfigs(PackageConfigFiles())
    machine = Environment(host, runner, uv)
    return App(
        host=host,
        init_project=InitProject(FileProjectScaffold()),
        load_project=LoadProject(source or FileConfigSource(), host, version),
        show_config=ShowConfig(),
        export_schema=ExportSchema(),
        runner=runner,
        python_envs=python_envs
        or UvPythonEnvManager(runner, environ=dict(host.variables)),
        build_help=BuildHelp(version),
        vscode_tasks=VSCodeTasks(TasksFile),
        reports=ReportService(FileReportStore(host.variables), version),
        shared_configs=configs,
        tools=tools,
        doctor=Doctor(machine, tools, configs, version),
        self_setup=SelfSetup(machine, tools, configs),
        installer=installer,
        prompter=prompter,
        secret_providers=secret_providers
        or default_secret_providers(host.variables, prompter),
    )


def default_secret_providers(
    environ: Mapping[str, str], prompter: Prompter
) -> dict[str, SecretProvider]:
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
