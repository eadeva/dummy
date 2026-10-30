"""Collect the full help of the CLI and the project (use case ``BuildHelp``).

The result is plain data; the HTML page is rendered by an adapter. Commands of
the CLI framework are passed in by the driver (the use case does not know
click); everything from the configuration is collected here. Maintainer-only
jobs are left out for users. Secrets are never part of the help - only
credential names, fields and the environment variables that can supply them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ...domain.config.model import ParamSpec, StepSpec
from ...domain.config.substitution import to_text
from ...domain.credentials import default_variable
from .project import Project
from .role import Role, visible


@dataclass
class HelpOption:
    names: str  # "-V, --variant NAME"
    help: str = ""
    default: str = ""


@dataclass
class HelpCommand:
    path: str  # "variant show"
    usage: str
    summary: str
    help: str
    options: list[HelpOption] = field(default_factory=list)


@dataclass
class HelpParam:
    name: str
    option: str  # how to pass it on the command line
    type: str
    default: str
    choices: list[str]
    required: bool
    env: str | None
    help: str


@dataclass
class HelpStep:
    name: str
    kind: str  # run | uses
    title: str
    detail: str  # command or plugin
    when: str | None
    flags: list[str]


@dataclass
class HelpJob:
    name: str
    help: str
    audience: str
    params: list[HelpParam]
    steps: list[HelpStep]
    requires_tools: list[str]
    phases: list[str]  # names usable with --only-step / --to
    passthrough: list[str]  # steps accepting "-- args"
    usage: str = ""
    is_default: bool = False


@dataclass
class HelpVariant:
    name: str
    description: str
    aliases: list[str]
    extends: list[str]
    abstract: bool
    default: bool


@dataclass
class HelpCredential:
    name: str
    description: str
    fields: list[str]
    env: dict[str, str]
    providers: list[str]


@dataclass
class HelpTool:
    name: str
    description: str
    version: str
    sources: list[str]


@dataclass
class HelpDocument:
    version: str
    generated: str
    role: Role
    commands: list[HelpCommand]
    project: str | None = None
    description: str = ""
    root: str = ""
    default_job: str | None = None
    files: list[str] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    jobs: list[HelpJob] = field(default_factory=list)
    hidden_jobs: int = 0
    variants: list[HelpVariant] = field(default_factory=list)
    credentials: list[HelpCredential] = field(default_factory=list)
    tools: list[HelpTool] = field(default_factory=list)
    error: str | None = None  # project could not be loaded


class BuildHelp:
    def __init__(self, version: str):
        self._version = version

    def execute(
        self,
        project: Project | None,
        commands: list[HelpCommand],
        role: Role,
        error: str | None = None,
    ) -> HelpDocument:
        doc = HelpDocument(
            version=self._version,
            generated=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            role=role,
            commands=commands,
            error=error,
        )
        if project is None:
            return doc
        config = project.config
        doc.project = config.project.name
        doc.description = config.project.description
        doc.root = str(project.root)
        doc.default_job = config.project.default_job
        doc.files = [_rel(project, f) for f in project.files]
        doc.layers = list(project.layers)
        for name, job in config.jobs.items():
            if not visible(job.audience, role):
                doc.hidden_jobs += 1
                continue
            doc.jobs.append(
                HelpJob(
                    name=name,
                    help=job.help,
                    audience=job.audience,
                    params=[_param(n, p) for n, p in job.params.items()],
                    steps=[_step(name, s) for name, s in job.steps.items()],
                    requires_tools=job.required_tool_names,
                    phases=list(job.steps),
                    passthrough=[
                        "/".join(path) for path, s in _walk(job.steps) if s.passthrough
                    ],
                    usage=f"ptk {'maintainer ' if job.audience == 'maintainer' else ''}{name} [OPTIONS]"
                    + (
                        " [-- ARGS]"
                        if any(s.passthrough for _, s in _walk(job.steps))
                        else ""
                    ),
                    is_default=name == config.project.default_job,
                )
            )
        if config.variants is not None:
            from .variants import VariantService

            for v in VariantService(project).list():
                doc.variants.append(
                    HelpVariant(
                        v.name,
                        v.description,
                        v.aliases,
                        v.extends,
                        v.abstract,
                        v.default,
                    )
                )
        for name, cred in config.credentials.items():
            doc.credentials.append(
                HelpCredential(
                    name,
                    cred.description,
                    list(cred.fields),
                    _cred_env(name, cred.fields, cred.env),
                    list(cred.providers),
                )
            )
        for name, tool in config.tools.items():
            sources = [
                k
                for k in ("choco", "uv_tool", "download", "apt", "dnf")
                if getattr(tool, k)
            ]
            doc.tools.append(
                HelpTool(name, tool.description, tool.version or "", sources)
            )
        return doc


def _rel(project: Project, path: Any) -> str:
    try:
        return str(path.relative_to(project.root))
    except ValueError:
        return str(path)


def _option(name: str, spec: ParamSpec) -> str:
    flag = "--" + name.replace("_", "-")
    if spec.type == "secret":
        return flag + " (hidden prompt)"
    if spec.type == "bool":
        return f"{flag} / --no-{flag[2:]}"
    metavar = {"int": "N", "float": "NUMBER", "list": "A,B,...", "choice": "CHOICE"}
    return f"{flag} {metavar.get(spec.type, 'TEXT')}"


def _param(name: str, spec: ParamSpec) -> HelpParam:
    default = "" if spec.default is None else to_text(spec.default)
    return HelpParam(
        name,
        _option(name, spec),
        spec.type,
        default,
        list(spec.choices or []),
        spec.required,
        spec.env,
        spec.help,
    )


def _step(name: str, step: StepSpec) -> HelpStep:
    if step.uses:
        detail = f"uses {step.uses}" + (f" {step.with_}" if step.with_ else "")
    else:
        detail = step.run if isinstance(step.run, str) else " ".join(step.run or [])
    flags = ["needs: " + ", ".join(step.needs)] if step.needs else ["ready"]
    if step.generators:
        flags.append("generators: " + ", ".join(step.generators))
    if step.python is not None:
        p = step.python
        flags.append(
            "python: "
            + (
                f"uvx {p.uvx}"
                if p.uvx
                else "venv"
                if p.venv
                else f"project {p.project}"
                if p.project
                else "ptk interpreter"
            )
        )
    if step.cwd:
        flags.append(f"cwd {step.cwd}")
    if step.timeout:
        flags.append(f"timeout {step.timeout:g}s")
    if step.retries:
        flags.append(f"retries {step.retries}")
    if step.continue_on_error:
        flags.append("continue on error")
    if step.passthrough:
        flags.append("accepts -- args")
    if step.secrets:
        flags.append("secrets: " + ", ".join(sorted(step.secrets)))
    return HelpStep(
        name,
        step.kind,
        step.title or "",
        detail,
        step.when,
        flags,
    )


def _walk(steps: dict[str, StepSpec]):
    for name, step in steps.items():
        yield (name,), step


def _cred_env(name: str, fields: list[str], mapping: dict[str, str]) -> dict[str, str]:
    return {f: mapping.get(f) or default_variable(name, f) for f in fields}
