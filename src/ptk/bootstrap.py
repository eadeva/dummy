"""Composition root: the only module that wires concrete adapters to use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .adapters import help_html
from .adapters.builtins import report_import
from .adapters.config.source import FileConfigSource
from .adapters.credentials.env import EnvProvider
from .adapters.credentials.gopass import GopassProvider
from .adapters.credentials.keyring_provider import KeyringProvider
from .adapters.credentials.prompt import ConsolePrompter, PromptProvider
from .adapters.credentials.vault import Vault, VaultProvider, default_vault_file
from .adapters.host import SystemHost
from .adapters.logging.files import FileLogObserver
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
from .application.use_cases.run import BUILTINS, PreparedRun, PrepareRun, RunAction
from .application.use_cases.setup import Doctor, Environment, SelfSetup
from .application.use_cases.tools import ToolService
from .application.use_cases.variants import VariantService
from .application.use_cases.vscode import VSCodeTasks
from .domain.errors import PtkError
from .domain.logging import file_level


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
    _credentials: dict[int, CredentialService] = field(default_factory=dict, repr=False)

    def variants(self, project: Project) -> VariantService:
        return VariantService(project)

    def credentials(self, project: Project) -> CredentialService:
        """One service per project and ptk process (caches values, vault unlocked once)."""
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
        builtins = {**BUILTINS, "report.import": report_import}
        return RunAction(self.host, self.runner, self.python_envs, builtins=builtins)

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
