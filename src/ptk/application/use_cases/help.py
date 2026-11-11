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

from ...domain.config.model import CredentialSpec, ParamSpec, StepSpec
from ...domain.config.substitution import to_text
from ...domain.credentials import convention_variable
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
    detail: str  # command or built-in operation
    when: str | None
    flags: list[str]
    needs: list[str] = field(default_factory=list)


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
    gui: bool = False


@dataclass
class HelpWorkflow:
    name: str
    help: str
    audience: str
    jobs: list[tuple[str, list[str]]]  # (job key, needs)
    usage: str = ""


@dataclass
class HelpSkill:
    name: str
    description: str


@dataclass
class HelpAssistant:
    skills: list[HelpSkill]
    installed_version: str | None = None  # None: not installed in the repository
    installed_repositories: list[str] = field(default_factory=list)  # VMR page


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
    workflows: list[HelpWorkflow] = field(default_factory=list)
    hidden_workflows: int = 0
    assistant: HelpAssistant | None = None
    alias: str = ""
    prefix: str = ""  # command prefix, e.g. the repository alias in a VMR


@dataclass
class HelpWorkspace:
    version: str
    generated: str
    role: Role
    root: str
    commands: list[HelpCommand]
    workflows: list[HelpWorkflow] = field(default_factory=list)
    repositories: list[HelpDocument] = field(default_factory=list)
    assistant: HelpAssistant | None = None


def assistant_info(bundle: dict[str, bytes], root: Any = None) -> HelpAssistant:
    """Skills shipped with this PTk and whether a repository has them installed."""
    import json

    import yaml

    skills = []
    for name, content in sorted(bundle.items()):
        parts = name.split("/")
        if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
            continue
        text = content.decode("utf-8", "replace")
        meta = {}
        if text.startswith("---"):
            try:
                meta = yaml.safe_load(text.split("---", 2)[1]) or {}
            except yaml.YAMLError:
                meta = {}
        skills.append(HelpSkill(parts[1], str(meta.get("description", ""))))
    installed = None
    if root is not None:
        manifest = root / ".github" / "ptk" / "manifest.json"
        if (root / ".github" / "agents" / "ptk-expert.agent.md").is_file():
            try:
                installed = json.loads(manifest.read_text(encoding="utf-8")).get(
                    "ptk_version", "unknown"
                )
            except (OSError, ValueError):
                installed = "unknown"
    return HelpAssistant(skills, installed)


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
                    gui=job.gui,
                )
            )
        workflow_restricted = config.command_audience.get("workflow") == "maintainer"
        for name, spec in config.workflows.items():
            audience = "maintainer" if workflow_restricted else spec.audience
            if not visible(audience, role):
                doc.hidden_workflows += 1
                continue
            doc.workflows.append(workflow_help(name, spec, audience))
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
                    _cred_env(name, cred, config.project.name),
                    list(cred.providers),
                )
            )
        for name, tool in config.tools.items():
            sources = [
                k
                for k in (
                    "toolbase",
                    "artifactory",
                    "choco",
                    "uv_tool",
                    "download",
                    "apt",
                    "dnf",
                )
                if getattr(tool, k)
            ]
            doc.tools.append(
                HelpTool(name, tool.description, tool.version or "", sources)
            )
        return doc


def workflow_help(name: str, spec: Any, audience: str) -> HelpWorkflow:
    return HelpWorkflow(
        name,
        spec.help,
        audience,
        [(key, list(call.needs)) for key, call in spec.jobs.items()],
        f"ptk {'maintainer ' if audience == 'maintainer' else ''}workflow run {name}",
    )


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
            + (f" (Python {p.version})" if p.version else "")
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
        list(step.needs),
    )


def _walk(steps: dict[str, StepSpec]):
    for name, step in steps.items():
        yield (name,), step


def _cred_env(name: str, cred: CredentialSpec, project: str) -> dict[str, str]:
    return {
        f: cred.env.get(f)
        or convention_variable(project, "USERID", name, f).replace(
            "_USERID_", "_<USER>_", 1
        )
        for f in cred.fields
    }
