"""Run a job (use cases ``PrepareRun`` and ``RunJob``).

``PrepareRun`` turns configuration + request into an :class:`JobPlan`
(parameters, variant, environment, substituted steps, skip reasons); it has no
side effects, so ``ptk JOB --dry-run`` is simply "prepare and show".
``RunJob`` executes a dependency graph through the ports: bounded concurrency, retries, timeouts, ``continue_on_error`` and cancellation (Ctrl+C).
"""

from __future__ import annotations

import dataclasses
import shutil
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain import layout as lay
from ...domain.config.dates import date_values
from ...domain.config.model import JobSpec
from ...domain.config.substitution import (
    LazyNamespace,
    Scope,
    SubstitutionError,
    to_text,
)
from ...domain.errors import PtkError
from ...domain.execution import environment as envs
from ...domain.execution.commands import PythonRuntime, build_command
from ...domain.execution.model import (
    JobPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)
from ...domain.execution.params import resolve_params
from ...domain.execution.planning import PlanContext, plan_job
from ...domain.graphs import ancestors
from ...domain.logging import Level
from ...domain.suggest import did_you_mean
from ...domain.variants.model import ResolvedVariant
from ...domain.versioning import variables as version_variables
from ..ports import (
    CancelToken,
    GitMetadata,
    HostEnvironment,
    ProcessRunner,
    PythonEnvManager,
    RunObserver,
    SecretResolver,
)
from .project import Project
from .role import Role, visible
from .tools import ToolService, tools_for_jobs
from .variants import VariantService

MASK = "********"
MIN_MASK_LENGTH = 4  # shorter values would garble normal output; warned about


@dataclass
class RunRequest:
    job: str | None = None  # None: project.default_job
    variant: str | None = None
    all_variants: bool = False
    feature_overrides: Mapping[str, str] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)  # from the command line
    params_file: Mapping[str, Any] = field(default_factory=dict)  # from --params FILE
    only_step: str | None = None  # explicitly bypass prerequisites
    end: str | None = None  # --to
    passthrough: Sequence[str] = ()  # after "--"
    args_for: Mapping[str, list[str]] = field(default_factory=dict)
    dry_run: bool = False
    graph: bool = False
    role: Role = "user"  # maintainer-only jobs are refused for users


@dataclass
class PreparedRun:
    plan: JobPlan
    project: Project
    layout: lay.Layout
    secret_values: set[str]  # values to mask in every output
    dry_run: bool = False
    step_secrets: dict[str, str] = field(default_factory=dict)  # ref -> value

    versions: dict = field(default_factory=dict)
    version_file: str | None = None
    resolved_variant: ResolvedVariant | None = None

    def mask(self, text: str) -> str:
        for value in sorted(self.secret_values, key=len, reverse=True):
            if len(value) >= MIN_MASK_LENGTH:
                text = text.replace(value, MASK)
        return text

    def mask_context(self, value):
        if isinstance(value, str):
            return self.mask(value)
        if isinstance(value, dict):
            return {
                self.mask_context(k): self.mask_context(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.mask_context(v) for v in value]
        return value


def layout_of(project: Project) -> lay.Layout:
    spec = project.config.layout
    root = (project.root / spec.root).resolve()
    return lay.Layout(root, spec.builds, spec.bin, spec.logs, spec.reports)


class PrepareRun:
    def __init__(
        self,
        host: HostEnvironment,
        secrets: SecretResolver | None = None,
        clock: Callable[[], datetime] = datetime.now,
        tools: ToolService | None = None,
        versions=None,
        ptk_version: str = "",
        git: GitMetadata | None = None,
    ):
        self._host = host
        self._secrets = secrets
        self._clock = clock
        self._tools = tools
        self._versions = versions
        self._ptk_version = ptk_version
        self._git = git

    def execute(self, project: Project, request: RunRequest) -> PreparedRun:
        config = project.config
        instant = self._clock()
        if instant.tzinfo is None:
            instant = instant.astimezone()
        dates = date_values(instant)

        def read_git():
            if self._git is None:
                raise PtkError(
                    "Git metadata is not available in this execution context."
                )
            return self._git.discover(project.root)

        git = LazyNamespace(read_git)
        if request.job is None:
            if config.project.default_job is None:
                names = ", ".join(config.jobs) or "none configured"
                raise PtkError(
                    "no job given and no project.default_job configured "
                    f"(jobs: {names})"
                )
            request = dataclasses.replace(request, job=config.project.default_job)
        assert request.job is not None
        job = self._job(project, request.job)
        project = tools_for_jobs(project, [request.job])
        config = project.config
        if not visible(job.audience, request.role):
            raise PtkError(
                f"'{request.job}' is a maintainer-only job "
                "(login IDs are listed in maintainers.ptk.yml)"
            )
        if job.only_cx and not project.ci:
            raise PtkError(f"job {request.job!r} is only available in CX/CI")
        host_env = self._host.variables
        os_name = self._host.os_name()

        variants = VariantService(project)
        resolved = None
        variant_name: str | None = None
        vh_ns: dict[str, Any] = {}
        vh_env: dict[str, str] = {}
        symbols: dict[str, Any] = {}
        if variants.has_variants:
            if request.feature_overrides:
                selected = variants.name_of(request.variant)
                edited = config.model_copy(deep=True)
                for name, value in request.feature_overrides.items():
                    if name not in variants.line.feature_index:
                        raise PtkError(f"unknown feature '{name}'")
                    try:
                        typed = variants.line.feature(name).parse_text(value)
                    except ValueError as exc:
                        raise PtkError(f"{name}: {exc}") from None
                    edited.variants.variants[selected].features[name] = typed
                project = dataclasses.replace(project, config=edited)
                config = edited
                variants = VariantService(project)
            resolved = variants.resolve(request.variant)
            if resolved.errors:
                raise PtkError(
                    "invalid variant: " + "; ".join(map(str, resolved.errors))
                )
            variant_name = resolved.name
            vh_ns = variants.namespace(resolved)
            vh_env = variants.environment(resolved)
            symbols = dict(variants.symbols(resolved))
        elif request.feature_overrides:
            raise PtkError("feature overrides require variants")
        elif request.variant:
            raise PtkError(f"--variant {request.variant}: this project has no variants")

        from ...domain.execution.planning import variant_restriction

        reason = variant_restriction(job, variant_name)
        if reason:
            raise PtkError(f"job {request.job!r}: {reason}")

        version_snapshot = (
            self._versions.resolve(project, variant_name, request.job)
            if self._versions
            else {}
        )
        project_ns = {
            "root": str(project.root),
            "name": config.project.name,
            "description": config.project.description,
            "alias": config.repository.alias
            if config.repository
            else config.project.name,
        }
        version_scope = {
            **version_snapshot,
            "current": version_snapshot.get("projects", {}).get(
                project_ns["alias"], {}
            ),
        }

        def resolve_default(template: str) -> Any:
            # defaults may use env, vars, vh and project - not other parameters
            return Scope(
                env=host_env,
                vars=config.vars,
                namespaces={
                    "vh": vh_ns,
                    "project": project_ns,
                    "version": version_scope,
                    "date": dates,
                    "git": git,
                },
            )(template)

        params, sources = resolve_params(
            job.params,
            cli=request.params,
            file_values=request.params_file,
            environ=host_env,
            resolve_default=resolve_default,
        )

        layout = layout_of(project)
        run_id = instant.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        version_file = (
            str(
                project.root
                / ".ptk"
                / "versions"
                / (variant_name or "default")
                / request.job
                / run_id
                / ".gen.version.ptk.yml"
            )
            if version_snapshot
            else None
        )
        dirs = {
            "bin_dir": str(layout.bin_dir(variant_name, request.job)),
            "log_dir": str(layout.job_log_dir(variant_name, request.job)),
            "reports_dir": str(layout.reports_dir(variant_name, request.job)),
            "build_dir": str(layout.build_dir(variant_name, request.job)),
        }
        secret_params = {n for n, spec in job.params.items() if spec.type == "secret"}
        secret_values: set[str] = {
            str(params[n]) for n in secret_params if params.get(n)
        }

        def secret(ref: str) -> str:
            if request.dry_run:
                return MASK
            if self._secrets is None:
                raise SubstitutionError(
                    f"secret '{ref}' requested but no credential provider is configured"
                )
            value = self._secrets(ref)
            secret_values.add(value)
            return value

        def scope(env: Mapping[str, str], step_path: tuple[str, ...] = ()) -> Scope:
            run_ns = {
                "id": run_id,
                "job": request.job,
                "variant": variant_name or lay.NO_VARIANT,
                "step": "/".join(step_path),
                **dirs,
            }
            if step_path:
                run_ns["build_dir"] = str(
                    layout.build_dir(variant_name, request.job, step_path)
                )
                run_ns["reports_dir"] = str(
                    layout.reports_dir(variant_name, request.job, step_path)
                )
                run_ns["log_file"] = str(
                    layout.step_log(variant_name, request.job, step_path)
                )
            return Scope(
                env=env,
                vars=config.vars,
                secret=secret,
                namespaces={
                    "params": params,
                    "vh": vh_ns,
                    "project": project_ns,
                    "run": run_ns,
                    "version": version_scope,
                    "date": dates,
                    "git": git,
                    "steps": {
                        name: {
                            "build_dir": str(
                                layout.build_dir(variant_name, request.job, (name,))
                            ),
                            "reports_dir": str(
                                layout.reports_dir(variant_name, request.job, (name,))
                            ),
                            "log_file": str(
                                layout.step_log(variant_name, request.job, (name,))
                            ),
                        }
                        for name in job.steps
                    },
                },
            )

        # environment of every command of this run (steps add their own layer)
        try:
            env_spec = config.environment
            pre = scope(host_env)
            base = envs.base_environment(
                self._tools.clean_environment(host_env) if self._tools else host_env,
                os_name=os_name,
                inherit_path=env_spec.inherit_path,
                isolate=env_spec.isolate,
                keep=env_spec.keep,
                set_={k: to_text(pre(v)) for k, v in env_spec.set.items()},
                unset=env_spec.unset,
                path_prepend=[
                    *(
                        self._tools.paths(project) if self._tools else []
                    ),  # ptk-installed tools
                    *(to_text(pre(p)) for p in env_spec.path_prepend),
                ],
                path_append=[to_text(pre(p)) for p in env_spec.path_append],
            )
            base.update(
                {
                    "PTK_PROJECT": config.project.name,
                    "PTK_PROJECT_ROOT": str(project.root),
                    "PTK_JOB": request.job,
                    "PTK_RUN_ID": run_id,
                    "PTK_VARIANT": variant_name or lay.NO_VARIANT,
                    "PTK_BIN_DIR": dirs["bin_dir"],
                    "PTK_LOG_DIR": dirs["log_dir"],
                    "PTK_REPORTS_DIR": dirs["reports_dir"],
                }
            )
            base.update(
                envs.param_variables(
                    {n: v for n, v in params.items() if n not in secret_params}
                )
            )
            base.update(vh_env)
            base = {
                k: v
                for k, v in base.items()
                if not k.upper().startswith("PTK_VERSION_")
            }
            base.update(
                {k: str(v) for k, v in version_variables(version_snapshot).items()}
            )
            if version_file:
                base["PTK_VERSION_FILE"] = version_file
            job_scope = scope(base)
            if any(k.upper().startswith("PTK_VERSION_") for k in job.env):
                raise PtkError(
                    "PTK_VERSION_* variables are reserved for discovered versions"
                )
            base.update({k: to_text(job_scope(v)) for k, v in job.env.items()})
            resolved_vars = {
                name: job_scope.resolve(f"vars.{name}") for name in config.vars
            }
        except SubstitutionError as exc:
            raise PtkError(f"job '{request.job}': {exc}") from None

        tool_statuses = []
        if (
            self._tools is not None
            and job.required_tool_names
            and not request.dry_run
            and not any(s.uses == "tools.ensure" for s in job.walk_steps())
        ):
            tool_statuses = self._tools.status(
                project, job.required_tool_names, env=base
            )
            problems = [status for status in tool_statuses if not status.ok]
            if problems:
                lines = "\n".join(f"  - {s.name}: {s.problem}" for s in problems)
                raise PtkError(
                    f"'{request.job}' needs tools that are missing or too old:\n{lines}\n"
                    f"  install them with: ptk self-service tools --job {request.job} "
                    f"(or run the job with --setup)"
                )

        symbols.update(
            {
                "variant": variant_name,
                "os": os_name,
                "ci": project.ci,
                "params": params,
                "vars": resolved_vars,
                "env": base,
                "vh": vh_ns,
            }
        )
        ctx = PlanContext(
            symbols=symbols,
            scope_for=lambda path: scope(base, path),
            passthrough=list(request.passthrough),
            args_for=dict(request.args_for),
        )
        steps = plan_job(job.steps, ctx, only_step=request.only_step, end=request.end)
        for step in steps:
            if step.skip_reason or not step.spec.generators:
                continue
            if resolved is None:
                raise PtkError(
                    f"step '{step.label}': generators require a selected variant"
                )
        plan = JobPlan(
            project=config.project.name,
            job=request.job,
            variant=variant_name,
            run_id=run_id,
            params={n: MASK if n in secret_params else v for n, v in params.items()},
            param_sources=sources,
            steps=steps,
            base_env=base,
            dirs=dirs,
            log_analysis=config.log_analysis.model_dump(),
            report_context={
                "date": dates,
                "ptk_version": self._ptk_version,
                "repository_alias": config.repository.alias
                if config.repository
                else config.project.name,
                "versions": version_snapshot,
                "variant": (
                    {
                        "name": resolved.name,
                        "description": resolved.description,
                        "chain": resolved.chain,
                        "components": resolved.components,
                        "features": resolved.values,
                    }
                    if resolved
                    else {}
                ),
                "tools": [dataclasses.asdict(s) for s in tool_statuses],
                "required_tools": list(job.required_tool_names),
            },
            max_workers=job.max_workers,
            only_step=request.only_step,
            omitted_dependencies=sorted(ancestors(job.steps)[request.only_step])
            if request.only_step
            else [],
        )
        plan.report_context["selection"] = {
            "to": request.end,
            "only_step": request.only_step,
            "omitted_dependencies": plan.omitted_dependencies,
        }
        validate_step_resources(plan, project.root)
        # resolve every secret the selected steps need now: a missing credential
        # stops the run before anything starts, and prompts never happen in the
        # middle of parallel steps
        step_secrets: dict[str, str] = {}
        if not request.dry_run:
            for step in plan.walk():
                if step.skip_reason is None:
                    for ref in step.secrets.values():
                        if ref not in step_secrets:
                            try:
                                step_secrets[ref] = secret(ref)
                            except SubstitutionError as exc:
                                raise PtkError(str(exc)) from None
        return PreparedRun(
            plan,
            project,
            layout,
            secret_values,
            request.dry_run,
            step_secrets,
            version_snapshot,
            version_file,
            resolved,
        )

    @staticmethod
    def _job(project: Project, name: str) -> JobSpec:
        jobs = project.config.jobs
        if name not in jobs:
            hint = did_you_mean(name, jobs)
            listing = (
                f" (jobs: {', '.join(jobs)})" if jobs else " - no jobs are configured"
            )
            raise PtkError(f"unknown job '{name}'{hint}{listing}")
        return jobs[name]


# --------------------------------------------------------------------------- execution


class Cancelled(threading.Event):
    """Set on Ctrl+C: running processes are terminated, nothing new starts."""


class CancellationScope:
    """Local deadline combined with a parent's cancellation (safe in parallel)."""

    def __init__(self, parent, timeout: float | None = None):
        self.parent = parent
        self.deadline = time.monotonic() + timeout if timeout else None

    @property
    def expired(self) -> bool:
        return self.deadline is not None and time.monotonic() >= self.deadline

    def is_set(self) -> bool:
        return self.parent.is_set() or self.expired


@dataclass(frozen=True)
class BuiltinContext:
    """What a built-in step (``uses:``) may work with."""

    root: Path  # project root
    build_dir: Path  # the step's build folder
    reports_dir: Path  # the step's reports folder (picked up by the report)
    cancel: CancelToken | None = None  # cooperative cancellation: is_set()
    variant: ResolvedVariant | None = None  # resolved variant for generators
    versions: dict = field(default_factory=dict)


BuiltinStep = Callable[[PlannedStep, Callable[[str], None], BuiltinContext], int]


def _builtin_echo(
    step: PlannedStep, out: Callable[[str], None], ctx: BuiltinContext
) -> int:
    message = step.with_.get("message", "")
    for line in to_text(message).splitlines() or [""]:
        out(line)
    return 0


def _builtin_wait(
    step: PlannedStep, out: Callable[[str], None], ctx: BuiltinContext
) -> int:
    seconds = float(step.with_.get("seconds", 1))
    out(f"waiting {seconds:g}s")
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if ctx.cancel is not None and ctx.cancel.is_set():
            return 1
        time.sleep(min(0.05, max(0, end - time.monotonic())))
    return 0


BUILTINS: dict[str, BuiltinStep] = {"echo": _builtin_echo, "wait": _builtin_wait}


class RunJob:
    """Executes prepared runs; one ``execute`` at a time per instance."""

    def __init__(
        self,
        host: HostEnvironment,
        runner: ProcessRunner,
        python_envs: PythonEnvManager,
        builtins: Mapping[str, BuiltinStep] | None = None,
        max_parallel: int | None = None,
        path_provider: Callable[[], list[str]] | None = None,
        environment_check=None,
        version_writer=None,
        variant_writer=None,
    ):
        self._host = host
        self._runner = runner
        self._python = python_envs
        self._builtins = dict(BUILTINS if builtins is None else builtins)
        self._max_parallel = max_parallel
        self._path_provider = path_provider
        self._environment_check = environment_check
        self._version_writer = version_writer
        self._variant_writer = variant_writer
        self._powershell: str | None = None
        self._python_lock = threading.Lock()

    # -- public --------------------------------------------------------------------------

    def execute(
        self,
        prepared: PreparedRun,
        observers: Sequence[RunObserver] = (),
        cancel: Cancelled | None = None,
    ) -> RunResult:
        plan = prepared.plan
        if prepared.version_file and self._version_writer and not prepared.dry_run:
            self._version_writer(prepared.version_file, prepared.versions)
        cancel = cancel or Cancelled()
        self._prepared = prepared
        self._observers = list(observers)
        self._cancel = cancel
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        start = time.monotonic()
        self._run_start = start
        Path(plan.dirs["bin_dir"]).mkdir(parents=True, exist_ok=True)
        # Previous inputs are preserved with their log summary by the observer.
        reports = Path(plan.dirs["reports_dir"])
        if reports.is_dir():
            shutil.rmtree(reports)
        reports.mkdir(parents=True, exist_ok=True)
        plan.report_context = prepared.mask_context(plan.report_context)
        self._emit("run_started", plan)
        from ..scheduling import schedule

        results = schedule(
            {step.name: step for step in plan.steps},
            {
                step.name: [] if plan.only_step or step.skip_reason else step.spec.needs
                for step in plan.steps
            },
            self._run_step,
            self._not_run,
            cancel,
            min(plan.max_workers, self._max_parallel or plan.max_workers),
        )
        status = _combine(results)
        if cancel.is_set():
            status = Status.CANCELLED
        result = RunResult(
            project=plan.project,
            job=plan.job,
            variant=plan.variant,
            run_id=plan.run_id,
            status=status,
            started_at=started_at,
            duration=time.monotonic() - start,
            params=plan.params,
            param_sources=plan.param_sources,
            steps=results,
            log_file=str(prepared.layout.run_log(plan.variant, plan.job)),
        )
        self._emit("run_finished", result)
        return result

    def describe(
        self, prepared: PreparedRun, step: PlannedStep
    ) -> tuple[str, str | None]:
        """(command line, python runtime description) without side effects - for ptk JOB --dry-run."""
        if step.kind == "generate":
            return "generate " + ", ".join(step.spec.generators), None
        if step.kind == "uses":
            return f"uses {step.spec.uses} {step.with_ or ''}".rstrip(), None
        runtime = (
            self._python.runtime(step.python, prepared.project.root, create=False)
            if step.python is not None
            else None
        )
        command = self._command(prepared, step, runtime)
        return prepared.mask(
            command.display()
        ), runtime.description if runtime else None

    def _not_run(self, step: PlannedStep, status: Status, message: str) -> StepResult:
        result = StepResult(
            step.path,
            step.name,
            step.kind,
            status=status,
            message=message,
            needs=list(step.spec.needs),
        )
        self._emit("step_finished", step, result)
        return result

    def _run_step(self, step: PlannedStep, cancel=None) -> StepResult:
        cancel = cancel or self._cancel
        if cancel.is_set():
            return self._not_run(step, Status.CANCELLED, "cancelled")
        if step.skip_reason:
            return self._not_run(step, Status.SKIPPED, step.skip_reason)
        return self._run_leaf(step, cancel)

    def _run_leaf(self, step: PlannedStep, cancel) -> StepResult:
        prepared = self._prepared
        plan = prepared.plan
        layout = prepared.layout
        result = StepResult(
            step.path, step.name, step.kind, needs=list(step.spec.needs)
        )
        result.log_file = str(layout.step_log(plan.variant, plan.job, step.path))
        for folder in (
            layout.build_dir(plan.variant, plan.job, step.path),
            layout.reports_dir(plan.variant, plan.job, step.path),
        ):
            Path(folder).mkdir(parents=True, exist_ok=True)

        def out(line: str) -> None:
            self._emit("output", step, prepared.mask(line))

        start = time.monotonic()
        result.start = start - self._run_start
        try:
            if step.kind in ("uses", "generate"):
                result.command = (
                    f"uses {step.spec.uses}"
                    if step.kind == "uses"
                    else "generate " + ", ".join(step.spec.generators)
                )
                self._emit("step_started", step, result.command)
                for attempt in range(1, step.spec.retries + 2):
                    result.attempts = attempt
                    scope = CancellationScope(cancel, step.spec.timeout)
                    self._generate(step, out, scope)
                    exit_code, message = (
                        self._run_builtin(step, out, scope)
                        if step.kind == "uses" and not scope.is_set()
                        else (int(scope.is_set()), "")
                    )
                    if scope.expired:
                        exit_code, message = (
                            1,
                            f"timed out after {step.spec.timeout:g}s",
                        )
                    if exit_code == 0 or cancel.is_set():
                        break
            else:
                runtime = None
                if step.python is not None:
                    with self._python_lock:  # one venv creation at a time
                        runtime = self._python.runtime(
                            step.python,
                            prepared.project.root,
                            create=True,
                            on_output=out,
                        )
                command = self._command(prepared, step, runtime)
                if self._environment_check:
                    observed = self._environment_check(
                        plan.job, command.env, command.cwd
                    )
                    for status in observed or []:
                        record = prepared.mask_context(dataclasses.asdict(status))
                        if record not in plan.report_context.setdefault("tools", []):
                            plan.report_context["tools"].append(record)
                result.command = prepared.mask(command.display())
                self._emit("step_started", step, result.command)
                self._describe_command(step, command, runtime)
                exit_code, message = 1, ""
                for attempt in range(1, step.spec.retries + 2):
                    result.attempts = attempt
                    if attempt > 1:
                        self._log(
                            Level.WARNING,
                            f"exit code {exit_code} - retry {attempt - 1}/{step.spec.retries}",
                            step,
                        )
                    scope = CancellationScope(cancel, step.spec.timeout)
                    self._generate(step, out, scope)
                    if scope.is_set():
                        exit_code, message = (
                            1,
                            "cancelled"
                            if cancel.is_set()
                            else f"timed out after {step.spec.timeout:g}s",
                        )
                        break
                    command.timeout = (
                        max(0.001, scope.deadline - time.monotonic())
                        if scope.deadline
                        else None
                    )
                    outcome = self._runner.run(command, out, cancel)
                    exit_code = outcome.exit_code
                    message = outcome.error or ""
                    if outcome.timed_out or scope.expired:
                        exit_code = exit_code or 1
                        message = f"timed out after {step.spec.timeout:g}s"
                    if outcome.cancelled or exit_code == 0:
                        break
                if cancel.is_set():
                    result.status = Status.CANCELLED
                    message = message or "cancelled"
        except (PtkError, SubstitutionError, ValueError, OSError) as exc:
            exit_code, message = 1, str(exc)
            self._log(Level.ERROR, message, step)
        if cancel.is_set():
            result.status = Status.CANCELLED
            message = message or "cancelled"
        result.exit_code = exit_code
        result.message = prepared.mask(message)
        result.duration = time.monotonic() - start
        if result.status is not Status.CANCELLED:
            result.status = Status.PASSED if exit_code == 0 else Status.FAILED
        if result.status is Status.FAILED:
            if not result.message:
                result.message = f"exit code {exit_code}"
            result.allowed_failure = step.spec.continue_on_error
            if result.allowed_failure:
                self._log(Level.WARNING, "failure allowed by continue_on_error", step)
        self._emit("step_finished", step, result)
        return result

    def _generate(self, step, out, cancel):
        if not step.spec.generators or cancel.is_set():
            return
        if self._variant_writer is None:
            raise PtkError("variant generation is not available")
        prepared = self._prepared
        self._variant_writer(
            step.spec.generators,
            prepared.resolved_variant,
            Path(
                prepared.layout.build_dir(
                    prepared.plan.variant, prepared.plan.job, step.path
                )
            ),
            out,
            cancel,
        )

    def _run_builtin(
        self, step: PlannedStep, out: Callable[[str], None], cancel
    ) -> tuple[int, str]:
        name = step.spec.uses or ""
        handler = self._builtins.get(name)
        if handler is None:
            return (
                1,
                f"built-in step '{name}' is not available{did_you_mean(name, self._builtins)}",
            )
        prepared = self._prepared
        plan = prepared.plan
        ctx = BuiltinContext(
            cancel=cancel,
            versions=prepared.versions,
            variant=(
                prepared.resolved_variant.model_copy(deep=True)
                if prepared.resolved_variant is not None
                else None
            ),
            root=prepared.project.root,
            build_dir=Path(
                prepared.layout.build_dir(plan.variant, plan.job, step.path)
            ),
            reports_dir=Path(
                prepared.layout.reports_dir(plan.variant, plan.job, step.path)
            ),
        )
        try:
            return handler(step, out, ctx), ""
        except (PtkError, ValueError, OSError) as exc:
            return 1, str(exc)

    def _command(
        self, prepared: PreparedRun, step: PlannedStep, runtime: PythonRuntime | None
    ):
        os_name = self._host.os_name()
        plan = prepared.plan
        env = dict(plan.base_env)
        if self._path_provider:
            for folder in reversed(self._path_provider()):
                env = envs.prepend_path(env, folder, os_name=os_name)
        env.update(
            {
                "PTK_STEP": step.label,
                "PTK_BUILD_DIR": str(
                    prepared.layout.build_dir(plan.variant, plan.job, step.path)
                ),
                "PTK_STEP_REPORTS_DIR": str(
                    prepared.layout.reports_dir(plan.variant, plan.job, step.path)
                ),
            }
        )
        if any(
            k.upper().startswith("PTK_VERSION_") for k in (*step.env, *step.secrets)
        ):
            raise PtkError(
                "PTK_VERSION_* variables are reserved for discovered versions"
            )
        env.update(step.env)
        for variable, ref in step.secrets.items():
            if not prepared.dry_run:
                value = prepared.step_secrets[ref]
                if len(value) < MIN_MASK_LENGTH:
                    self._log(
                        Level.WARNING,
                        f"secret '{ref}' is shorter than {MIN_MASK_LENGTH} characters "
                        "and cannot be masked in output",
                        step,
                    )
                env[variable] = value
            else:
                env[variable] = MASK
        cwd = Path(step.cwd)
        if not cwd.is_absolute():
            cwd = prepared.project.root / cwd
        plain = self._python.runtime(None, prepared.project.root, create=False)
        return build_command(
            step,
            env=env,
            cwd=str(cwd),
            os_name=os_name,
            python=runtime,
            powershell=self._powershell_name(),
            plain_python=plain,
        )

    def _powershell_name(self) -> str:
        if self._powershell is None:
            self._powershell = (
                self._runner.which("pwsh")
                or self._runner.which("powershell")
                or "powershell"
            )
        return self._powershell

    def _describe_command(
        self, step: PlannedStep, command: Any, runtime: PythonRuntime | None
    ) -> None:
        mask = self._prepared.mask
        self._log(Level.DEBUG, f"cwd {command.cwd}", step)
        if runtime is not None:
            self._log(Level.DEBUG, f"python: {runtime.description}", step)
        if command.timeout:
            self._log(Level.DEBUG, f"timeout {command.timeout:g}s", step)
        if step.env:
            self._log(Level.DEBUG, "env: " + ", ".join(sorted(step.env)), step)
        if step.secrets:
            names = ", ".join(sorted(step.secrets))
            self._log(Level.DEBUG, f"secrets as env: {names} (values masked)", step)
        for key in sorted(command.env):
            self._log(Level.TRACE, f"env {key}={mask(command.env[key])}", step)

    def _log(self, level: Level, text: str, step: PlannedStep | None = None) -> None:
        self._emit("message", level, self._prepared.mask(text), step)

    def _emit(self, event: str, *args: Any) -> None:
        for observer in self._observers:
            handler = getattr(observer, event, None)  # observers may skip events
            if handler is not None:
                handler(*args)


def _combine(results: list[StepResult]) -> Status:
    if any(r.status is Status.CANCELLED and not r.allowed_failure for r in results):
        return Status.CANCELLED
    if any(r.blocking_failure for r in results):
        return Status.FAILED
    if results and all(r.status is Status.SKIPPED for r in results):
        return Status.SKIPPED
    return Status.PASSED


def validate_step_resources(plan: JobPlan, root: Path) -> None:
    """Reject unordered commands which can synchronize the same uv environment."""
    steps = {step.name: step for step in plan.steps if step.skip_reason is None}
    dependencies = ancestors({step.name: step.spec for step in plan.steps})
    resources = {}
    for name, step in steps.items():
        python = step.python
        if python is None or python.project is None:
            continue
        project = (root / python.project).resolve()
        environment = {**plan.base_env, **step.env}
        venv = Path(environment.get("UV_PROJECT_ENVIRONMENT") or ".venv")
        resources[name] = (project / venv).resolve()
    for index, (name, resource) in enumerate(resources.items()):
        for other in list(resources)[:index]:
            if (
                resource == resources[other]
                and other not in dependencies[name]
                and name not in dependencies[other]
            ):
                raise PtkError(
                    f"steps {other!r} and {name!r} can run concurrently and share uv project environment {resource}; "
                    "add a needs dependency or isolate their environments"
                )
