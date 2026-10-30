"""Meta-model of the ptk configuration (entities).

Entry point is ``.main.ptk.yml``. Conventional documents own each section or
named entity; registered components own their local feature definitions.
Unknown keys are errors everywhere.

Steps are a mapping of IDs to commands or plugins with explicit needs dependencies.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

from ..artifacts import ArtifactoryStructure
from ..graphs import IDENTIFIER, DependencyId, validate_graph
from ..variants.model import ProductLineSpec
from ..versioning import VersionDependency, VersioningSpec
from ..workflows import WorkflowFile, WorkflowSpec

JOB_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
PARAM_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

RESERVED_JOBS = {
    "init",
    "self-service",
    "maintainer",
    "validate",
    "variant",
    "report",
    "workflow",
    "pre-commit",
    "clean-all",
    "vmr-clean-all",
    "run",
    "describe",
    "help",
    "config",
    "sync",
    "version",
    "artifacts",
}
RESERVED_PARAMS = {
    "clean",
    "re_run",
    "only_step",
    "graph",
    "to",
    "variant",
    "all_variants",
    "feature",
    "dry_run",
    "setup",
    "set",
    "params",
    "env",
    "quiet",
    "args_for",
    "help",
}

SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _listify(value: Any) -> Any:
    if value is None:
        return []
    return [value] if isinstance(value, str) else value


# --------------------------------------------------------------------------- project


class RepositorySpec(_Strict):
    alias: str = Field(
        description="Short repository name used in VMR commands and workflow repository references. Use lowercase letters, digits, underscores and hyphens.",
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    config_path: str = Field(
        description="Configuration directory relative to .main.ptk.yml. PTK loads the conventional configuration files from this directory.",
        min_length=1,
    )


class WorkspaceSpec(_Strict):
    """A manual VMR entry file; paths are relative to its containing directory."""

    virtual_monorepo: StrictBool = Field(
        description="Set true to make this .main.ptk.yml a workspace marker instead of a repository configuration."
    )
    members: list[str] | None = Field(
        default=None,
        description="Exact workspace-relative repository paths; omission checks direct children only.",
    )

    @field_validator("virtual_monorepo")
    @classmethod
    def _enabled(cls, value: bool) -> bool:
        if not value:
            raise ValueError("a workspace marker requires virtual_monorepo: true")
        return value


class ComponentRegistration(_Strict):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"x-ptk-directory-template": "components/{name}"},
    )
    path: str = Field(
        description="Component directory relative to the repository root. Its component.variants.ptk.yml lives here, beside the build definition.",
        min_length=1,
    )


class ProjectSpec(_Strict):
    name: str = Field(
        description="Human-readable project name shown in reports and the extension."
    )
    description: str = Field(
        default="",
        description="Short explanation of the project for users and reports.",
    )
    default_job: str | None = Field(
        default=None,
        description="Job used when PTK is invoked without a command. Choose a job defined in this repository.",
    )
    components: dict[str, ComponentRegistration] = Field(
        description="Register component names and their source directories. Each component owns its local variant and feature definitions.",
        default_factory=dict,
    )


# --------------------------------------------------------------------------- params


ParamType = Literal["str", "int", "float", "bool", "choice", "path", "secret", "list"]


class ParamSpec(_Strict):
    """A job parameter.

    ``default`` may use ``${env:...}``, ``${vars.x}``, ``${vh.*}`` and
    ``${project.*}`` - e.g. a per-variant default ``${vh.data.build_type}``;
    such defaults are resolved and type-checked when the job runs.
    """

    type: ParamType = Field(
        default="str",
        description="Value type accepted by this job parameter. Use choice for a fixed list, path for a filesystem path, or secret for hidden input.",
    )
    default: Any = Field(
        default=None,
        description="Value used when no explicit argument or environment value is supplied. Supports PTK variables resolved when the job runs. Required and secret parameters cannot have defaults.",
    )
    choices: list[str] | None = Field(
        default=None,
        description="Allowed values for a choice parameter. Required only when type is choice.",
    )
    help: str = Field(
        default="",
        description="Explanation shown in command help and the job parameter form.",
    )
    required: bool = Field(
        default=False,
        description="Require a value when the job runs. Cannot be combined with a default.",
    )
    env: str | None = Field(
        default=None,
        description="Name of the environment variable supplying this parameter. Explicit arguments take precedence; the configured default is used if the environment value is absent.",
    )  # read the value from this environment variable

    @model_validator(mode="after")
    def _check(self) -> ParamSpec:
        if self.type == "secret" and self.default is not None:
            raise ValueError(
                "secret parameters must use env or hidden input, not defaults"
            )
        if self.type == "choice":
            if not self.choices:
                raise ValueError("choice parameters need 'choices'")
        elif self.choices is not None:
            raise ValueError("'choices' is only allowed for type: choice")
        if self.default is not None and not self.default_is_template:
            self.default = self.convert(self.default)
        if self.required and self.default is not None:
            raise ValueError("a required parameter cannot have a default")
        return self

    @property
    def default_is_template(self) -> bool:
        return isinstance(self.default, str) and "${" in self.default.replace("$${", "")

    def convert(self, raw: Any) -> Any:
        """Typed value from YAML or command-line text; raises ValueError."""
        kind = self.type
        if kind == "bool":
            if isinstance(raw, bool):
                return raw
            low = str(raw).strip().lower()
            if low in {"1", "true", "yes", "on", "y"}:
                return True
            if low in {"0", "false", "no", "off", "n"}:
                return False
            raise ValueError(f"expected a boolean, got {raw!r}")
        if kind == "int":
            if isinstance(raw, bool):
                raise ValueError(f"expected an integer, got {raw!r}")
            try:
                return int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"expected an integer, got {raw!r}") from None
        if kind == "float":
            try:
                return float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"expected a number, got {raw!r}") from None
        if kind == "choice":
            value = str(raw)
            if value not in (self.choices or []):
                raise ValueError(
                    f"expected one of {', '.join(self.choices or [])}, got {raw!r}"
                )
            return value
        if kind == "list":
            if isinstance(raw, list):
                return [str(v) for v in raw]
            return [part.strip() for part in str(raw).split(",") if part.strip()]
        return str(raw)


# --------------------------------------------------------------------------- python


class VenvSpec(_Strict):
    requirements: list[str] = Field(
        description="Requirement files to install in this step’s isolated Python environment.",
        default_factory=list,
    )  # requirement files
    packages: list[str] = Field(
        description="Additional Python package requirements to install, for example pytest>=8.",
        default_factory=list,
    )  # extra packages
    python: str | None = Field(
        default=None,
        description="Python interpreter or version requested for this environment.",
    )

    @field_validator("requirements", "packages", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> Any:
        return _listify(v)


class PythonSpec(_Strict):
    uvx: str | None = Field(
        default=None,
        description="Python tool requirement to run with uvx, for example ruff==0.6.9. Choose exactly one of uvx, venv, project or interpreter.",
    )  # "ruff==0.6.9"
    with_: list[str] = Field(
        description="Additional Python packages supplied to uvx. Only valid with uvx.",
        default_factory=list,
        alias="with",
    )  # extra packages for uvx
    venv: VenvSpec | None = Field(
        default=None,
        description="Create an isolated environment with the specified requirements, packages and Python version.",
    )
    project: str | None = Field(
        default=None,
        description="Python project directory passed to uv run --project. Uses that project’s dependencies.",
    )  # uv run --project <dir>
    groups: list[str] = Field(
        description="Dependency groups to include with uv run. Only valid with project mode.",
        default_factory=list,
    )  # dependency groups for project mode
    interpreter: Literal["cli"] | None = Field(
        default=None,
        description="Use cli to run with PTK’s own Python environment. Choose exactly one Python execution mode.",
    )  # ptk's own environment

    @field_validator("with_", "groups", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> Any:
        return _listify(v)

    @model_validator(mode="after")
    def _exactly_one(self) -> PythonSpec:
        chosen = [
            k
            for k in ("uvx", "venv", "project", "interpreter")
            if getattr(self, k) is not None
        ]
        if len(chosen) != 1:
            raise ValueError(
                "python needs exactly one of: uvx, venv, project, interpreter"
            )
        if self.groups and self.project is None:
            raise ValueError("'groups' is only allowed together with project")
        if any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", group)
            for group in self.groups
        ):
            raise ValueError("invalid dependency group name")
        if self.with_ and self.uvx is None:
            raise ValueError("'with' is only allowed together with uvx")
        return self


# --------------------------------------------------------------------------- steps


class StepSpec(_Strict):
    generators: list[str] = Field(
        default_factory=list,
        description="Variant generators run in order before each command or plugin attempt. Outputs are written into this step's build directory. A step may contain only generators. Built-ins: header, make, cmake, bazel, gn, yocto, robot, sphinx; installed generator plugins may add names.",
    )

    @field_validator("generators")
    @classmethod
    def _generators(cls, names):
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name) for name in names):
            raise ValueError("invalid generator name")
        if len(set(names)) != len(names):
            raise ValueError("generators must be unique within a step")
        return names

    only_cx: bool = Field(
        default=False, description="Skip this step outside CX execution."
    )
    only_variants: list[str] = Field(
        description="Run this step only for these variants. Other variants skip it; this does not select a variant.",
        default_factory=list,
    )
    omit_variants: list[str] = Field(
        description="Skip this step for these variants. This does not change the job’s selected variant.",
        default_factory=list,
    )
    needs: list[DependencyId] = Field(
        default_factory=list,
        description="Step IDs that must succeed first. Accepts one ID or a list; omission makes the step immediately eligible.",
    )

    @field_validator(
        "needs", mode="before", json_schema_input_type=DependencyId | list[DependencyId]
    )
    @classmethod
    def _needs(cls, value):
        return [value] if isinstance(value, str) else value

    title: str | None = Field(
        default=None, description="Readable title used to describe this step."
    )
    run: str | list[str] | None = Field(
        default=None,
        description="Command string or argument list to execute. A list preserves spaces within arguments. Use run or uses, or omit both for a generation-only step.",
    )
    uses: str | None = Field(
        default=None,
        description="Registered plugin that executes this step. Supply its inputs in with.",
    )
    with_: dict[str, Any] = Field(
        description="Inputs passed to the plugin named in uses.",
        default_factory=dict,
        alias="with",
    )
    when: str | None = Field(
        default=None,
        description="Condition evaluated against PTK execution symbols. The step is skipped when the expression is false.",
    )
    continue_on_error: bool = Field(
        default=False, description="Allow execution to continue after this step fails."
    )
    timeout: float | None = Field(
        description="Maximum time for the step in seconds. Must be greater than zero.",
        default=None,
        gt=0,
    )
    retries: int = Field(
        description="Number of additional attempts after a failed step. Zero means no retries.",
        default=0,
        ge=0,
    )
    cwd: str | None = Field(
        default=None,
        description="Working directory for this step; defaults to the repository root. Supports PTK variable expressions.",
    )
    env: dict[str, str] = Field(
        description="Environment variables added or overridden for this step. Values support PTK variables.",
        default_factory=dict,
    )
    secrets: dict[str, str] = Field(
        description="Map environment variable names to credential fields, for example TOKEN: artifactory.token. Store references here, not secret values.",
        default_factory=dict,
    )  # ENV_VAR: credential.field
    python: PythonSpec | None = Field(
        default=None,
        description="Python environment used for this command step. Choose one execution mode.",
    )
    passthrough: bool = Field(
        default=False,
        description="Accept extra command-line arguments passed after -- or targeted with --args-for. Only valid with run.",
    )
    report: bool = Field(
        default=True, description="Include this step in the job report."
    )

    @field_validator("env", mode="before")
    @classmethod
    def _env_strings(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {str(k): "" if val is None else str(val) for k, val in v.items()}
        return v

    @model_validator(mode="after")
    def _check(self) -> StepSpec:
        if self.uses == "variant.generate":
            raise ValueError(
                "variant.generate was removed; put generators directly on the step"
            )
        if self.run is not None and self.uses is not None:
            raise ValueError("step needs at most one of: run, uses")
        if self.run is None and self.uses is None and not self.generators:
            raise ValueError("step needs run, uses or non-empty generators")
        if self.python is not None and self.run is None:
            raise ValueError("'python' is only allowed together with run")
        if self.with_ and self.uses is None:
            raise ValueError("'with' is only allowed together with uses")
        if self.passthrough and self.run is None:
            raise ValueError("'passthrough' is only allowed together with run")
        return self

    @property
    def kind(self) -> str:
        return "uses" if self.uses else "run" if self.run is not None else "generate"


# --------------------------------------------------------------------------- jobs


class JobSpec(_Strict):
    only_cx: bool = Field(
        default=False,
        description="Expose this job only during CX execution. It is hidden from local command and extension listings.",
    )
    only_variants: list[str] = Field(
        description="Allow this job only for these variants. Running it with another variant is a configuration error; this does not select a variant.",
        default_factory=list,
    )
    omit_variants: list[str] = Field(
        description="Disallow this job for these variants. Running it with an omitted variant is an error.",
        default_factory=list,
    )
    open_report: Literal["always", "on_errors"] | None = Field(
        default=None,
        description="Open the report after every run (always), only after failures (on_errors), or leave automatic opening disabled (null).",
    )
    version_dependencies: dict[str, VersionDependency] = Field(
        description="Other repositories whose versions this job needs, with optional variant selections.",
        default_factory=dict,
    )
    environment: EnvironmentSpec | None = Field(
        default=None,
        description="Override environment isolation and PATH settings for this job.",
    )
    help: str = Field(
        default="",
        description="Job description shown in the tree, command help and parameter form.",
    )
    audience: Literal["all", "maintainer"] = Field(
        default="all",
        description="Choose whether everyone or only configured maintainers can access this job.",
    )
    params: dict[str, ParamSpec] = Field(
        description="Named parameters accepted by this job. Define their types, help, choices and defaults.",
        default_factory=dict,
    )
    requires_tools: dict[str, bool | ToolSpec] = Field(
        description="Tools required before the job runs. Reference a registered tool, disable it with false, or supply an inline tool definition.",
        default_factory=dict,
    )
    env: dict[str, str] = Field(
        description="Environment variables supplied to this job’s steps. Step settings can override them.",
        default_factory=dict,
    )
    max_workers: int = Field(
        default=4, ge=1, le=32, description="Maximum concurrent steps in this job."
    )
    steps: dict[str, StepSpec] = Field(
        description="Named steps with explicit needs dependencies. YAML order only controls presentation.",
        min_length=1,
        json_schema_extra={"propertyNames": {"pattern": IDENTIFIER}},
    )

    @field_validator("requires_tools", mode="before")
    @classmethod
    def _tool_list(cls, value: Any) -> Any:
        if isinstance(value, list) and all(isinstance(n, str) for n in value):
            return dict.fromkeys(value, True)
        return value

    @property
    def required_tool_names(self) -> list[str]:
        return [name for name, spec in self.requires_tools.items() if spec is not False]

    @field_validator("params")
    @classmethod
    def _param_names(cls, v: dict[str, ParamSpec]) -> dict[str, ParamSpec]:
        for name in v:
            if not PARAM_RE.match(name):
                raise ValueError(f"parameter name {name!r} must be lower_snake_case")
            if name in RESERVED_PARAMS:
                raise ValueError(f"parameter name {name!r} is reserved by ptk")
        return v

    @model_validator(mode="after")
    def _step_graph(self) -> JobSpec:
        validate_graph(self.steps, "step")
        return self

    def walk_steps(self):
        return iter(self.steps.values())


# --------------------------------------------------------------------------- environment / tools / credentials


class EnvironmentSpec(_Strict):
    isolate: bool = Field(
        default=True,
        description="Start from a minimal operating-system environment instead of copying the caller’s full environment.",
    )  # start from a minimal OS environment
    inherit_path: bool = Field(
        default=False,
        description="Include the caller’s PATH when creating an isolated environment.",
    )  # opt in to caller PATH
    keep: list[str] = Field(
        description="Environment variable names to preserve from the caller when isolation is enabled.",
        default_factory=list,
    )
    set: dict[str, str] = Field(
        description="Environment variable values to add or override.",
        default_factory=dict,
    )
    unset: list[str] = Field(
        description="Environment variable names to remove.", default_factory=list
    )
    path_prepend: list[str] = Field(
        description="Directories placed before the existing PATH entries, in this order.",
        default_factory=list,
    )
    path_append: list[str] = Field(
        description="Directories placed after the existing PATH entries, in this order.",
        default_factory=list,
    )


class ChocoSource(_Strict):
    package: str = Field(description="Chocolatey package ID used on Windows.")
    version: str | None = Field(
        default=None,
        description="Exact Chocolatey package version to install. Omit to use the installer default.",
    )


class DownloadSource(_Strict):
    url: str = Field(description="Download URL for the tool archive or executable.")
    sha256: str | None = Field(
        default=None, description="Expected SHA-256 digest used to verify the download."
    )
    extract: bool = Field(
        default=True,
        description="Extract the downloaded archive before using the tool.",
    )
    bin: str | None = Field(
        default=None,
        description="Subdirectory containing executables inside the downloaded tool.",
    )  # sub folder with the executables


class ToolbaseSource(_Strict):
    package: str = Field(
        description="Toolbase package identifier.",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    version: str = Field(
        description="Toolbase package version to install.",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    environment: str = Field(
        description="Toolbase environment name used for this installation.",
        default="ptk",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    bin: list[str] = Field(
        description="Executable directories relative to the installed package. A dot means the package root.",
        default_factory=lambda: ["."],
        min_length=1,
    )


class ArtifactorySource(_Strict):
    url: str = Field(
        description="Artifactory base URL, including /artifactory when required by the server."
    )  # Artifactory base URL, including /artifactory when applicable
    repository: str = Field(
        description="Artifactory repository containing the tool.",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    path: str = Field(
        default=".",
        description="Directory or AQL directory pattern used to locate the tool archive.",
    )  # directory, or AQL directory pattern
    name: str = Field(
        description="Archive filename or AQL filename pattern."
    )  # file name or AQL pattern
    properties: dict[str, str] = Field(
        description="Artifact properties required when searching for the download.",
        default_factory=dict,
    )
    select: Literal["unique", "latest"] = Field(
        default="unique",
        description="Require exactly one matching artifact (unique), or choose the latest match (latest).",
    )
    token_env: str | None = Field(
        default=None,
        description="Name of the environment variable holding the bearer token. Do not put the token value in configuration.",
    )  # bearer token; never store the value in YAML
    sha256: str | None = Field(
        description="Expected 64-character SHA-256 digest used to verify the download.",
        default=None,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    extract: bool = Field(default=True, description="Extract the downloaded archive.")
    bin: str | None = Field(
        default=None,
        description="Subdirectory containing executables inside the installed tool.",
    )


class ToolSpec(_Strict):
    description: str = Field(
        default="", description="Short explanation of the tool and why it is needed."
    )
    docker: bool = Field(
        default=False,
        description="Allow installation inside Docker. When false, installation is skipped in containers but version checks still run.",
    )  # false: disable installation inside Docker, keep checks
    installers: dict[str, dict[str, Any]] = Field(
        description="Custom installer definitions keyed by installer or platform.",
        default_factory=dict,
    )
    version: str | None = Field(
        default=None, description="Accepted tool version range, for example >=3.28,<4."
    )  # PEP 440 style range: ">=3.28,<4"
    check: str | None = Field(
        default=None, description="Command that prints the installed tool version."
    )  # command printing the version
    version_regex: str = Field(
        default=r"(\d+\.\d+(?:\.\d+)?)",
        description="Regular expression used to extract a version from the check command output.",
    )
    choco: str | ChocoSource | None = Field(
        default=None,
        description="Windows installation through Chocolatey, using a package ID or package/version settings.",
    )  # Windows
    toolbase: ToolbaseSource | None = Field(
        default=None, description="Install the tool through Toolbase."
    )
    artifactory: (
        ArtifactorySource | dict[Literal["windows", "linux"], ArtifactorySource] | None
    ) = Field(
        default=None,
        description="Download from Artifactory. Use one source or separate windows and linux sources.",
    )
    uv_tool: str | None = Field(
        default=None, description="Python tool requirement to install through uv tool."
    )  # Windows + Linux
    download: (
        DownloadSource | dict[Literal["windows", "linux"], DownloadSource] | None
    ) = Field(
        default=None,
        description="Download an archive or executable. Use one source or separate windows and linux sources.",
    )
    apt: str | None = Field(
        default=None,
        description="APT package name for opt-in installation on Linux. Installation may require sudo.",
    )  # opt-in, needs sudo
    dnf: str | None = Field(
        default=None,
        description="DNF package name for opt-in installation on Linux. Installation may require sudo.",
    )


ProviderName = Literal["env", "keyring", "gopass", "vault", "prompt"]


class GopassSpec(_Strict):
    path: str = Field(description="Entry path in the gopass password store.")


class CredentialSpec(_Strict):
    namespace: str | None = Field(
        default=None,
        description="Credential storage scope. A VMR provides a default scope when this is omitted.",
    )  # explicit storage scope; VMR supplies one by default
    description: str = Field(
        default="", description="Explanation of what the credential is used for."
    )
    fields: list[str] = Field(
        description="Named values belonging to this credential, for example token, username or password.",
        default_factory=lambda: ["token"],
    )
    providers: list[str] = Field(
        description="Credential providers to try, in order: env, keyring, gopass, vault or prompt.",
        default_factory=lambda: ["env", "keyring", "gopass", "vault", "prompt"],
    )
    env: dict[str, str] = Field(
        description="Map credential field names to environment variable names. Store names, not secret values.",
        default_factory=dict,
    )  # field: ENV_VAR
    gopass: GopassSpec | None = Field(
        default=None, description="Location of this credential in the gopass store."
    )
    test: str | None = Field(
        default=None, description="Command used to verify that the credential works."
    )  # command to verify the credential

    @model_validator(mode="after")
    def _check(self) -> CredentialSpec:
        unknown = set(self.env) - set(self.fields)
        if unknown:
            raise ValueError(
                f"env maps unknown field(s) {sorted(unknown)}; fields are {self.fields}"
            )
        return self


# --------------------------------------------------------------------------- shared configs, logging, reporting


SharedConfigName = Literal["pre-commit", "ruff", "clang-format", "clang-tidy", "clangd"]


class SharedConfigSpec(_Strict):
    enabled: bool = Field(
        default=True, description="Enable this shared tool configuration."
    )
    overlay: str | None = Field(
        default=None,
        description="Project overlay file merged into the shared configuration.",
    )
    output: str | None = Field(
        default=None,
        description="Destination path for the generated tool configuration.",
    )


class LayoutSpec(_Strict):
    """Workspace folders: <root>/_builds|_bin|_logs|_reports/<variant>/<job>/<step>."""

    root: str = Field(
        default=".",
        description="Base directory for generated output, relative to the repository root.",
    )
    builds: str = Field(
        default="_builds",
        description="Build directory name beneath the layout root, partitioned by variant, job and step.",
    )
    bin: str = Field(
        default="_bin",
        description="Binary/output directory name beneath the layout root.",
    )
    logs: str = Field(
        default="_logs", description="Log directory name beneath the layout root."
    )
    reports: str = Field(
        default="_reports", description="Report directory name beneath the layout root."
    )

    @field_validator("builds", "bin", "logs", "reports")
    @classmethod
    def _plain_name(cls, v: str) -> str:
        if not v or "/" in v or "\\" in v or v in (".", ".."):
            raise ValueError(f"{v!r} must be a plain folder name")
        return v


class LogMatchSpec(_Strict):
    step: str = Field(
        default="*", description="Case-sensitive glob matching the full step path."
    )
    severity: Literal["error", "warning"] | None = Field(
        default=None, description="Match only this severity; omit for both."
    )
    message_regex: str = Field(
        description="Regular expression matched against the diagnostic message, not the command line.",
        min_length=1,
    )

    @field_validator("message_regex")
    @classmethod
    def valid_pattern(cls, value):
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid diagnostic regular expression: {exc}") from None
        return value


class LogRuleSpec(_Strict):
    id: str = Field(
        description="Stable identifier recorded with matching findings.", min_length=1
    )
    match: LogMatchSpec = Field(
        description="Conditions that must all match a diagnostic."
    )
    action: Literal["ignore", "justify"] = Field(
        description="Ignore hides noise; justify records an accepted diagnostic. Both remain in reports."
    )
    reason: str = Field(
        description="Explanation retained with this run's findings.", min_length=1
    )

    @field_validator("id", "reason")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class LogAnalysisSpec(_Strict):
    enabled: bool = Field(
        default=True,
        description="Analyze captured step logs after execution without changing the job exit code.",
    )
    rules: list[LogRuleSpec] = Field(
        default_factory=list,
        description="Ordered suppression rules. The first matching rule wins; logs remain unchanged.",
    )

    @field_validator("rules")
    @classmethod
    def unique_rules(cls, rules):
        ids = [rule.id for rule in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("log analysis rule IDs must be unique")
        return rules


# --------------------------------------------------------------------------- root


class PtkConfig(_Strict):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "x-ptk-field-order": [
                "schema_version",
                "ptk_version",
                "virtual_monorepo",
                "repository",
                "members",
                "project",
                "variants",
                "jobs",
                "workflows",
                "vars",
                "param_defaults",
                "environment",
                "requires_tools",
                "tools",
                "credentials",
                "artifactory",
                "versioning",
                "layout",
                "configs",
                "logging_history_backups",
                "report_formats",
                "log_analysis",
                "plugins",
                "command_audience",
            ]
        },
    )
    artifactory: ArtifactoryStructure | None = Field(
        default=None,
        description="Artifact destination rules by event, branch/tag and job. Configure downloads for tools in tools instead.",
    )
    workflows: dict[str, WorkflowSpec] = Field(
        description="Named dependency graphs of job calls, including calls into other repositories.",
        default_factory=dict,
    )

    @field_validator("workflows")
    @classmethod
    def _workflow_names(cls, value):
        return WorkflowFile._names(value)

    repository: RepositorySpec | None = Field(
        default=None,
        description="Repository identity and conventional configuration directory.",
    )
    virtual_monorepo: StrictBool = Field(
        default=False,
        description="Entry-only discovery flag: omit for automatic Git membership, false for standalone, true for a workspace marker.",
    )
    schema_version: Literal[1] = Field(
        default=1, description="PTK configuration schema version."
    )
    ptk_version: str | None = Field(
        default=None,
        description="Required PTK package version range, for example >=0.7,<1.",
    )  # required ptk version range, e.g. ">=0.1,<0.2"
    project: ProjectSpec = Field(
        description="Project identity, default job and registered component directories."
    )
    vars: dict[str, Any] = Field(
        description="Reusable project values referenced with ${vars.name}.",
        default_factory=dict,
    )
    param_defaults: dict[str, Any] = Field(
        description="Shared default values for job parameters with matching names.",
        default_factory=dict,
    )
    requires_tools: dict[str, bool | ToolSpec] = Field(
        description="Tools required at project level. Use registered names or inline definitions.",
        default_factory=dict,
    )
    environment: EnvironmentSpec = Field(
        description="Default environment isolation and PATH settings for job execution.",
        default_factory=EnvironmentSpec,
    )
    tools: dict[str, ToolSpec] = Field(
        description="Named tool definitions, version checks and installation sources.",
        default_factory=dict,
    )
    credentials: dict[str, CredentialSpec] = Field(
        description="Named credential definitions and lookup providers. Keep secret values outside configuration.",
        default_factory=dict,
    )
    variants: ProductLineSpec | None = Field(
        default=None,
        description="Project variants, component features, inheritance and validation constraints.",
    )
    versioning: VersioningSpec | None = Field(
        default=None,
        description="Project and component version sources, per-variant overrides and repository dependencies.",
    )
    jobs: dict[str, JobSpec] = Field(
        description="Named executable jobs, including their steps, parameters and required tools.",
        default_factory=dict,
    )
    configs: dict[SharedConfigName, SharedConfigSpec] = Field(
        description="Shared tool configuration settings, such as pre-commit, Ruff and clang-format.",
        default_factory=dict,
    )
    layout: LayoutSpec = Field(
        description="Directory names for generated builds, binaries, logs and reports.",
        default_factory=LayoutSpec,
    )
    logging_history_backups: int = Field(
        default=3,
        ge=0,
        description="Previous run logs retained per variant and job, in addition to the current run. Zero disables backups.",
    )
    report_formats: list[str] = Field(
        default_factory=lambda: ["html"],
        description="Report exporters: html, json, junit, markdown, github, or installed plugin exporters. An empty list disables automatic export unless open_report requires HTML.",
    )
    log_analysis: LogAnalysisSpec = Field(
        default_factory=LogAnalysisSpec,
        description="Analyze step diagnostics and retain ignored or justified findings with their reasons.",
    )
    plugins: list[str] = Field(
        description="Installed distribution names selected for PTK plugin loading.",
        default_factory=list,
    )
    command_audience: dict[
        Literal[
            "self-service",
            "self-service.tools",
            "self-service.creds",
            "self-service.doctor",
            "self-service.hooks",
            "self-service.hooks.install",
            "self-service.hooks.uninstall",
            "self-service.hooks.status",
            "maintainer",
            "maintainer.config",
            "maintainer.sync",
            "maintainer.version",
            "maintainer.artifacts",
            "variant",
            "report",
            "workflow",
            "pre-commit",
            "clean-all",
        ],
        Literal["all", "maintainer"],
    ] = Field(
        description="Control which built-in commands are available to all users or only maintainers.",
        default_factory=dict,
    )

    @model_validator(mode="before")
    @classmethod
    def _shared_defaults(cls, value: Any) -> Any:
        if isinstance(value, dict):
            from .defaults import apply_defaults
            from .tree import from_plain, to_plain

            return to_plain(apply_defaults(from_plain(value)))
        return value

    @model_validator(mode="after")
    def _workflow_job_targets(self):
        for name, workflow in self.workflows.items():
            try:
                workflow.validate_job_targets(
                    self.repository.alias if self.repository else None
                )
            except ValueError as exc:
                raise ValueError(f"workflow {name!r}: {exc}") from exc
        return self

    @field_validator("param_defaults")
    @classmethod
    def _default_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        for name in value:
            if not PARAM_RE.match(name) or name in RESERVED_PARAMS:
                raise ValueError(f"invalid shared parameter name {name!r}")
        return value

    @field_validator("jobs")
    @classmethod
    def _job_names(cls, v: dict[str, JobSpec]) -> dict[str, JobSpec]:
        for name in v:
            if not JOB_RE.match(name):
                raise ValueError(
                    f"job name {name!r} must start with a lowercase letter (letters, digits, '_', '-')"
                )
            if name in RESERVED_JOBS:
                raise ValueError(f"job name {name!r} is reserved by ptk")
        return v

    @field_validator("tools", "credentials")
    @classmethod
    def _names(cls, v: dict[str, Any]) -> dict[str, Any]:
        for name in v:
            if not NAME_RE.match(name):
                raise ValueError(
                    f"name {name!r} may only contain letters, digits, '_' and '-'"
                )
        return v


# --------------------------------------------------------------------------- maintainers.ptk.yml


class MaintainersSpec(_Strict):
    maintainers: list[StrictStr] = Field(
        description="Login names allowed to use maintainer-only commands and jobs."
    )

    @field_validator("maintainers")
    @classmethod
    def _user_ids(cls, value: list[str]) -> list[str]:
        seen = set()
        for user in value:
            if (
                not user.strip()
                or user != user.strip()
                or any(ord(c) < 32 for c in user)
            ):
                raise ValueError(
                    "maintainer IDs must be non-empty login names without surrounding whitespace or control characters"
                )
            if user.casefold() in seen:
                raise ValueError(f"duplicate maintainer ID {user!r}")
            seen.add(user.casefold())
        return value
