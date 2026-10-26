"""Meta-model of the ptk configuration (entities).

Entry point is ``.main.ptk.yml``; further ``*.ptk.yml`` files are pulled in
with ``include:``. Unknown keys are errors everywhere.

Steps are written as an ordered list of single-key mappings::

    steps:
      - configure: "cmake --preset ${vh.variant}"        # short form = run
      - compile: {run: [cmake, --build, .], timeout: 600}
      - checks:
          parallel: true
          steps:
            - lint: {run: tools/lint.py, python: {uvx: "ruff==0.6.9"}}
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from ..variants.model import ProductLineSpec
from ..versioning import VersionDependency, VersioningSpec
from ..workflows import WorkflowFile, WorkflowSpec

JOB_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PARAM_RE = re.compile(r"^[a-z][a-z0-9_]*$")
STEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

RESERVED_JOBS = {
    "workflow",
    "config",
    "variant",
    "creds",
    "configs",
    "setup",
    "self-setup",
    "doctor",
    "report",
    "run",
    "dry-run",
    "init",
    "help",
    "vscode",
    "version",
}
RESERVED_PARAMS = {
    "from",
    "to",
    "variant",
    "all_variants",
    "feature",
    "dry_run",
    "setup",
    "set",
    "params",
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
    alias: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    config_path: str = Field(min_length=1)


class WorkspaceSpec(_Strict):
    """A manual VMR entry file; paths are relative to its containing directory."""

    virtual_monorepo: StrictBool
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


class ProjectSpec(_Strict):
    name: str
    description: str = ""
    default_job: str | None = None


# --------------------------------------------------------------------------- params


ParamType = Literal["str", "int", "float", "bool", "choice", "path", "secret", "list"]


class ParamSpec(_Strict):
    """A job parameter.

    ``default`` may use ``${env:...}``, ``${vars.x}``, ``${vh.*}`` and
    ``${project.*}`` - e.g. a per-variant default ``${vh.data.build_type}``;
    such defaults are resolved and type-checked when the job runs.
    """

    type: ParamType = "str"
    default: Any = None
    choices: list[str] | None = None
    help: str = ""
    required: bool = False
    env: str | None = None  # read the value from this environment variable

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
    requirements: list[str] = Field(default_factory=list)  # requirement files
    packages: list[str] = Field(default_factory=list)  # extra packages
    python: str | None = None

    @field_validator("requirements", "packages", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> Any:
        return _listify(v)


class PythonSpec(_Strict):
    uvx: str | None = None  # "ruff==0.6.9"
    with_: list[str] = Field(
        default_factory=list, alias="with"
    )  # extra packages for uvx
    venv: VenvSpec | None = None
    project: str | None = None  # uv run --project <dir>
    groups: list[str] = Field(
        default_factory=list
    )  # dependency groups for project mode
    interpreter: Literal["cli"] | None = None  # ptk's own environment

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


def normalize_step_entry(raw: Any) -> Any:
    """``{name: body}`` -> ``{"name": name, **body}``; string body -> ``run``."""
    if isinstance(raw, dict) and "name" not in raw and len(raw) == 1:
        ((name, body),) = raw.items()
        if body is None:
            body = {}
        if isinstance(body, (str, list)):
            body = {"run": body}
        if isinstance(body, dict):
            return {"name": str(name), **body}
    return raw


class StepSpec(_Strict):
    name: str
    title: str | None = None
    run: str | list[str] | None = None
    uses: str | None = None
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    steps: list[StepSpec] | None = None
    parallel: bool = False
    background: bool = False
    when: str | None = None
    continue_on_error: bool = False
    timeout: float | None = Field(default=None, gt=0)
    retries: int = Field(default=0, ge=0)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # ENV_VAR: credential.field
    python: PythonSpec | None = None
    passthrough: bool = False
    report: bool = True

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, raw: Any) -> Any:
        return normalize_step_entry(raw)

    @field_validator("env", mode="before")
    @classmethod
    def _env_strings(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {str(k): "" if val is None else str(val) for k, val in v.items()}
        return v

    @model_validator(mode="after")
    def _check(self) -> StepSpec:
        if not STEP_RE.match(self.name):
            raise ValueError(
                f"step name {self.name!r} may only contain letters, digits, '_', '.', '-'"
            )
        kinds = [k for k in ("run", "uses", "steps") if getattr(self, k) is not None]
        if len(kinds) != 1:
            raise ValueError(
                f"step '{self.name}' needs exactly one of: run, uses, steps"
            )
        if self.background and self.run is None:
            raise ValueError("background is only allowed for run steps")
        if self.parallel and self.steps is None:
            raise ValueError("'parallel' is only allowed for step sets (steps:)")
        if self.python is not None and self.run is None:
            raise ValueError("'python' is only allowed together with run")
        if self.with_ and self.uses is None:
            raise ValueError("'with' is only allowed together with uses")
        if self.passthrough and self.run is None:
            raise ValueError("'passthrough' is only allowed together with run")
        if self.steps is not None:
            _unique([s.name for s in self.steps], f"step set '{self.name}'")
        return self

    @property
    def kind(self) -> str:
        return "set" if self.steps is not None else ("uses" if self.uses else "run")

    def walk(self):
        yield self
        for child in self.steps or []:
            yield from child.walk()


def _unique(names: list[str], where: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"duplicate step name '{name}' in {where}")
        seen.add(name)


# --------------------------------------------------------------------------- jobs


class JobSpec(_Strict):
    open_report: Literal["always", "on_errors"] | None = None
    version_dependencies: dict[str, VersionDependency] = Field(default_factory=dict)
    environment: EnvironmentSpec | None = None
    help: str = ""
    audience: Literal["all", "maintainer"] = "all"
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    requires_tools: dict[str, bool | ToolSpec] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    steps: list[StepSpec] = Field(min_length=1)

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
    def _steps_unique(self) -> JobSpec:
        _unique([s.name for s in self.steps], "job")
        return self

    def walk_steps(self):
        for step in self.steps:
            yield from step.walk()


# --------------------------------------------------------------------------- environment / tools / credentials


class EnvironmentSpec(_Strict):
    isolate: bool = True  # start from a minimal OS environment
    inherit_path: bool = False  # opt in to caller PATH
    keep: list[str] = Field(default_factory=list)
    set: dict[str, str] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    path_prepend: list[str] = Field(default_factory=list)
    path_append: list[str] = Field(default_factory=list)


class ChocoSource(_Strict):
    package: str
    version: str | None = None


class DownloadSource(_Strict):
    url: str
    sha256: str | None = None
    extract: bool = True
    bin: str | None = None  # sub folder with the executables


class ToolbaseSource(_Strict):
    package: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    environment: str = Field(default="ptk", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    bin: list[str] = Field(default_factory=lambda: ["."], min_length=1)


class ArtifactorySource(_Strict):
    url: str  # Artifactory base URL, including /artifactory when applicable
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    path: str = "."  # directory, or AQL directory pattern
    name: str  # file name or AQL pattern
    properties: dict[str, str] = Field(default_factory=dict)
    select: Literal["unique", "latest"] = "unique"
    token_env: str | None = None  # bearer token; never store the value in YAML
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    extract: bool = True
    bin: str | None = None


class ToolSpec(_Strict):
    description: str = ""
    docker: bool = False  # false: disable installation inside Docker, keep checks
    installers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    version: str | None = None  # PEP 440 style range: ">=3.28,<4"
    check: str | None = None  # command printing the version
    version_regex: str = r"(\d+\.\d+(?:\.\d+)?)"
    choco: str | ChocoSource | None = None  # Windows
    toolbase: ToolbaseSource | None = None
    artifactory: (
        ArtifactorySource | dict[Literal["windows", "linux"], ArtifactorySource] | None
    ) = None
    uv_tool: str | None = None  # Windows + Linux
    download: (
        DownloadSource | dict[Literal["windows", "linux"], DownloadSource] | None
    ) = None
    apt: str | None = None  # opt-in, needs sudo
    dnf: str | None = None


ProviderName = Literal["env", "keyring", "gopass", "vault", "prompt"]


class GopassSpec(_Strict):
    path: str


class CredentialSpec(_Strict):
    namespace: str | None = None  # explicit storage scope; VMR supplies one by default
    description: str = ""
    fields: list[str] = Field(default_factory=lambda: ["token"])
    providers: list[str] = Field(
        default_factory=lambda: ["env", "keyring", "gopass", "vault", "prompt"]
    )
    env: dict[str, str] = Field(default_factory=dict)  # field: ENV_VAR
    gopass: GopassSpec | None = None
    test: str | None = None  # command to verify the credential

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
    enabled: bool = True
    overlay: str | None = None
    output: str | None = None


class LayoutSpec(_Strict):
    """Workspace folders: <root>/_builds|_bin|_logs|_reports/<variant>/<job>/<step>."""

    root: str = "."
    builds: str = "_builds"
    bin: str = "_bin"
    logs: str = "_logs"
    reports: str = "_reports"

    @field_validator("builds", "bin", "logs", "reports")
    @classmethod
    def _plain_name(cls, v: str) -> str:
        if not v or "/" in v or "\\" in v or v in (".", ".."):
            raise ValueError(f"{v!r} must be a plain folder name")
        return v


class LoggingSpec(_Strict):
    level: Literal["trace", "debug", "info", "warning", "error"] = "info"
    keep_history: int = Field(default=10, ge=0)  # previous runs kept per variant/job


class ReportingSpec(_Strict):
    formats: list[str] = Field(default_factory=lambda: ["json", "html"])
    dir: str | None = None


# --------------------------------------------------------------------------- root


class PtkConfig(_Strict):
    workflows: dict[str, WorkflowSpec] = Field(default_factory=dict)

    @field_validator("workflows")
    @classmethod
    def _workflow_names(cls, value):
        return WorkflowFile._names(value)

    repository: RepositorySpec | None = None
    virtual_monorepo: StrictBool = Field(
        default=False,
        description="Entry-only discovery flag: omit for automatic Git membership, false for standalone, true for a workspace marker.",
    )
    schema_version: Literal[1] = 1
    ptk_version: str | None = None  # required ptk version range, e.g. ">=0.1,<0.2"
    project: ProjectSpec
    vars: dict[str, Any] = Field(default_factory=dict)
    param_defaults: dict[str, Any] = Field(default_factory=dict)
    requires_tools: dict[str, bool | ToolSpec] = Field(default_factory=dict)
    environment: EnvironmentSpec = Field(default_factory=EnvironmentSpec)
    tools: dict[str, ToolSpec] = Field(default_factory=dict)
    credentials: dict[str, CredentialSpec] = Field(default_factory=dict)
    variants: ProductLineSpec | None = None
    versioning: VersioningSpec | None = None
    jobs: dict[str, JobSpec] = Field(default_factory=dict)
    configs: dict[SharedConfigName, SharedConfigSpec] = Field(default_factory=dict)
    layout: LayoutSpec = Field(default_factory=LayoutSpec)
    logging: LoggingSpec = Field(default_factory=LoggingSpec)
    reporting: ReportingSpec = Field(default_factory=ReportingSpec)
    plugins: list[str] = Field(default_factory=list)
    command_audience: dict[
        Literal[
            "setup",
            "setup.config",
            "setup.configs",
            "setup.creds",
            "setup.vscode",
            "setup.install",
            "setup.self",
            "setup.doctor",
            "setup.init",
            "variant",
            "version",
            "report",
            "workflow",
        ],
        Literal["all", "maintainer"],
    ] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _shared_defaults(cls, value: Any) -> Any:
        if isinstance(value, dict):
            from .defaults import apply_defaults
            from .tree import from_plain, to_plain

            return to_plain(apply_defaults(from_plain(value)))
        return value

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
                    f"job name {name!r} must be lower-case (letters, digits, '-')"
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


class Maintainer(_Strict):
    name: str = ""
    email: str | None = None
    user: str | None = None

    @model_validator(mode="after")
    def _identity(self) -> Maintainer:
        if not self.email and not self.user:
            raise ValueError("a maintainer needs 'email' and/or 'user'")
        return self


class MaintainersSpec(_Strict):
    maintainers: list[Maintainer] = Field(default_factory=list)
