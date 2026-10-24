"""Run an action (use cases ``PrepareRun`` and ``RunAction``).

``PrepareRun`` turns configuration + request into an :class:`ActionPlan`
(parameters, variant, environment, substituted steps, skip reasons); it has no
side effects, so ``ptk dry-run`` is simply "prepare and show".
``RunAction`` executes a plan through the ports: sequential and parallel step
sets, retries, timeouts, ``continue_on_error`` and cancellation (Ctrl+C).
"""

from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain import layout as lay
from ...domain.config.model import ActionSpec
from ...domain.config.substitution import Scope, SubstitutionError, to_text
from ...domain.errors import PtkError
from ...domain.execution import environment as envs
from ...domain.execution.commands import PythonRuntime, build_command
from ...domain.execution.model import (
    ActionPlan,
    PlannedStep,
    RunResult,
    Status,
    StepResult,
)
from ...domain.execution.params import resolve_params
from ...domain.execution.planning import PlanContext, plan_action
from ...domain.logging import Level
from ...domain.suggest import did_you_mean
from ..ports import (
    HostEnvironment,
    ProcessRunner,
    PythonEnvManager,
    RunObserver,
    SecretResolver,
)
from .project import Project
from .role import Role, visible
from .variants import VariantService

MASK = "********"
MIN_MASK_LENGTH = 4  # shorter values would garble normal output; warned about


@dataclass
class RunRequest:
    action: str | None = None  # None: project.default_action
    variant: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)  # from the command line
    params_file: Mapping[str, Any] = field(default_factory=dict)  # from --params FILE
    start: str | None = None  # --from
    end: str | None = None  # --to
    passthrough: Sequence[str] = ()  # after "--"
    args_for: Mapping[str, list[str]] = field(default_factory=dict)
    dry_run: bool = False
    role: Role = "user"  # maintainer-only actions are refused for users


@dataclass
class PreparedRun:
    plan: ActionPlan
    project: Project
    layout: lay.Layout
    secret_values: set[str]  # values to mask in every output
    dry_run: bool = False
    step_secrets: dict[str, str] = field(default_factory=dict)  # ref -> value

    def mask(self, text: str) -> str:
        for value in sorted(self.secret_values, key=len, reverse=True):
            if len(value) >= MIN_MASK_LENGTH:
                text = text.replace(value, MASK)
        return text


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
    ):
        self._host = host
        self._secrets = secrets
        self._clock = clock

    def execute(self, project: Project, request: RunRequest) -> PreparedRun:
        config = project.config
        if request.action is None:
            if config.project.default_action is None:
                names = ", ".join(config.actions) or "none configured"
                raise PtkError(
                    "no action given and no project.default_action configured "
                    f"(actions: {names})"
                )
            request = dataclasses.replace(request, action=config.project.default_action)
        assert request.action is not None
        action = self._action(project, request.action)
        if not visible(action.audience, request.role):
            raise PtkError(
                f"'{request.action}' is a maintainer-only action "
                "(maintainers are listed in maintainers.ptk.yml; "
                "PTK_ROLE=maintainer overrides the detection)"
            )
        host_env = self._host.variables
        os_name = self._host.os_name()

        variants = VariantService(project)
        variant_name: str | None = None
        vh_ns: dict[str, Any] = {}
        vh_env: dict[str, str] = {}
        symbols: dict[str, Any] = {}
        if variants.has_variants:
            resolved = variants.resolve(request.variant)
            variant_name = resolved.name
            vh_ns = variants.namespace(resolved)
            vh_env = variants.environment(resolved)
            symbols = dict(variants.symbols(resolved))
        elif request.variant:
            raise PtkError(f"--variant {request.variant}: this project has no variants")

        project_ns = {
            "root": str(project.root),
            "name": config.project.name,
            "description": config.project.description,
        }

        def resolve_default(template: str) -> Any:
            # defaults may use env, vars, vh and project - not other parameters
            return Scope(
                env=host_env,
                vars=config.vars,
                namespaces={"vh": vh_ns, "project": project_ns},
            )(template)

        params, sources = resolve_params(
            action.params,
            cli=request.params,
            file_values=request.params_file,
            environ=host_env,
            resolve_default=resolve_default,
        )

        layout = layout_of(project)
        run_id = self._clock().strftime("%Y%m%d-%H%M%S")
        dirs = {
            "bin_dir": str(layout.bin_dir(variant_name)),
            "log_dir": str(layout.action_log_dir(variant_name, request.action)),
            "reports_dir": str(layout.reports_dir(variant_name, request.action)),
            "build_dir": str(layout.build_dir(variant_name, request.action)),
        }
        secret_values: set[str] = set()

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
                "action": request.action,
                "variant": variant_name or lay.NO_VARIANT,
                "step": "/".join(step_path),
                **dirs,
            }
            if step_path:
                run_ns["build_dir"] = str(
                    layout.build_dir(variant_name, request.action, step_path)
                )
                run_ns["reports_dir"] = str(
                    layout.reports_dir(variant_name, request.action, step_path)
                )
                run_ns["log_file"] = str(
                    layout.step_log(variant_name, request.action, step_path)
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
                },
            )

        # environment of every command of this run (steps add their own layer)
        try:
            env_spec = config.environment
            pre = scope(host_env)
            base = envs.base_environment(
                host_env,
                os_name=os_name,
                isolate=env_spec.isolate,
                keep=env_spec.keep,
                set_={k: to_text(pre(v)) for k, v in env_spec.set.items()},
                unset=env_spec.unset,
                path_prepend=[to_text(pre(p)) for p in env_spec.path_prepend],
                path_append=[to_text(pre(p)) for p in env_spec.path_append],
            )
            base.update(
                {
                    "PTK_PROJECT": config.project.name,
                    "PTK_PROJECT_ROOT": str(project.root),
                    "PTK_ACTION": request.action,
                    "PTK_RUN_ID": run_id,
                    "PTK_VARIANT": variant_name or lay.NO_VARIANT,
                    "PTK_BIN_DIR": dirs["bin_dir"],
                    "PTK_LOG_DIR": dirs["log_dir"],
                    "PTK_REPORTS_DIR": dirs["reports_dir"],
                }
            )
            base.update(envs.param_variables(params))
            base.update(vh_env)
            action_scope = scope(base)
            base.update({k: to_text(action_scope(v)) for k, v in action.env.items()})
            resolved_vars = {
                name: action_scope.resolve(f"vars.{name}") for name in config.vars
            }
        except SubstitutionError as exc:
            raise PtkError(f"action '{request.action}': {exc}") from None

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
        steps = plan_action(action.steps, ctx, start=request.start, end=request.end)
        plan = ActionPlan(
            project=config.project.name,
            action=request.action,
            variant=variant_name,
            run_id=run_id,
            params=params,
            param_sources=sources,
            steps=steps,
            base_env=base,
            dirs=dirs,
        )
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
            plan, project, layout, secret_values, request.dry_run, step_secrets
        )

    @staticmethod
    def _action(project: Project, name: str) -> ActionSpec:
        actions = project.config.actions
        if name not in actions:
            hint = did_you_mean(name, actions)
            listing = (
                f" (actions: {', '.join(actions)})"
                if actions
                else " - no actions are configured"
            )
            raise PtkError(f"unknown action '{name}'{hint}{listing}")
        return actions[name]


# --------------------------------------------------------------------------- execution


class Cancelled(threading.Event):
    """Set on Ctrl+C: running processes are terminated, nothing new starts."""


BuiltinStep = Callable[[PlannedStep, Callable[[str], None]], int]


def _builtin_echo(step: PlannedStep, out: Callable[[str], None]) -> int:
    message = step.with_.get("message", "")
    for line in to_text(message).splitlines() or [""]:
        out(line)
    return 0


def _builtin_wait(step: PlannedStep, out: Callable[[str], None]) -> int:
    seconds = float(step.with_.get("seconds", 1))
    out(f"waiting {seconds:g}s")
    time.sleep(seconds)
    return 0


BUILTINS: dict[str, BuiltinStep] = {"echo": _builtin_echo, "wait": _builtin_wait}


class RunAction:
    """Executes prepared runs; one ``execute`` at a time per instance."""

    def __init__(
        self,
        host: HostEnvironment,
        runner: ProcessRunner,
        python_envs: PythonEnvManager,
        builtins: Mapping[str, BuiltinStep] | None = None,
        max_parallel: int | None = None,
    ):
        self._host = host
        self._runner = runner
        self._python = python_envs
        self._builtins = dict(BUILTINS if builtins is None else builtins)
        self._max_parallel = max_parallel
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
        cancel = cancel or Cancelled()
        self._prepared = prepared
        self._observers = list(observers)
        self._cancel = cancel
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        start = time.monotonic()
        Path(plan.dirs["bin_dir"]).mkdir(parents=True, exist_ok=True)
        self._emit("run_started", plan)
        results = self._run_sequence(plan.steps)
        status = _combine(results)
        if cancel.is_set():
            status = Status.CANCELLED
        result = RunResult(
            project=plan.project,
            action=plan.action,
            variant=plan.variant,
            run_id=plan.run_id,
            status=status,
            started_at=started_at,
            duration=time.monotonic() - start,
            params=plan.params,
            param_sources=plan.param_sources,
            steps=results,
            log_file=str(prepared.layout.run_log(plan.variant, plan.action)),
        )
        self._emit("run_finished", result)
        return result

    def describe(
        self, prepared: PreparedRun, step: PlannedStep
    ) -> tuple[str, str | None]:
        """(command line, python runtime description) without side effects - for ptk dry-run."""
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

    # -- tree --------------------------------------------------------------------------

    def _run_sequence(self, steps: list[PlannedStep]) -> list[StepResult]:
        results: list[StepResult] = []
        failed = False
        for step in steps:
            if failed or self._cancel.is_set():
                reason = (
                    "cancelled"
                    if self._cancel.is_set()
                    else "not run: an earlier step failed"
                )
                results.append(
                    self._not_run(
                        step,
                        Status.CANCELLED if self._cancel.is_set() else Status.SKIPPED,
                        reason,
                    )
                )
                continue
            result = self._run_step(step)
            results.append(result)
            failed = result.blocking_failure
        return results

    def _run_parallel(self, steps: list[PlannedStep]) -> list[StepResult]:
        workers = max(1, min(len(steps), self._max_parallel or len(steps)))
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="ptk-step"
        ) as pool:
            return list(pool.map(self._run_step, steps))

    def _not_run(self, step: PlannedStep, status: Status, message: str) -> StepResult:
        result = StepResult(
            step.path, step.name, step.kind, status=status, message=message
        )
        self._emit(
            "step_finished",
            step,
            result
            if not step.children
            else StepResult(
                step.path,
                step.name,
                step.kind,
                status=status,
                message=message,
                children=[
                    StepResult(c.path, c.name, c.kind, status=status)
                    for c in step.children
                ],
            ),
        )
        result.children = [self._not_run(c, status, message) for c in step.children]
        return result

    def _run_step(self, step: PlannedStep) -> StepResult:
        if step.skip_reason:
            return self._not_run(step, Status.SKIPPED, step.skip_reason)
        if self._cancel.is_set():
            return self._not_run(step, Status.CANCELLED, "cancelled")
        if step.kind == "set":
            self._emit("step_started", step, None)
            start = time.monotonic()
            children = (
                self._run_parallel(step.children)
                if step.spec.parallel
                else self._run_sequence(step.children)
            )
            result = StepResult(
                step.path,
                step.name,
                step.kind,
                status=_combine(children),
                duration=time.monotonic() - start,
                children=children,
            )
            if result.status is Status.FAILED and step.spec.continue_on_error:
                result.allowed_failure = True
            self._emit("step_finished", step, result)
            return result
        return self._run_leaf(step)

    # -- leaves ------------------------------------------------------------------------

    def _run_leaf(self, step: PlannedStep) -> StepResult:
        prepared = self._prepared
        plan = prepared.plan
        layout = prepared.layout
        result = StepResult(step.path, step.name, step.kind)
        result.log_file = str(layout.step_log(plan.variant, plan.action, step.path))
        for folder in (
            layout.build_dir(plan.variant, plan.action, step.path),
            layout.reports_dir(plan.variant, plan.action, step.path),
        ):
            Path(folder).mkdir(parents=True, exist_ok=True)

        def out(line: str) -> None:
            self._emit("output", step, prepared.mask(line))

        start = time.monotonic()
        try:
            if step.kind == "uses":
                result.command = f"uses {step.spec.uses}"
                self._emit("step_started", step, result.command)
                exit_code, message = self._run_builtin(step, out)
                result.attempts = 1
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
                    outcome = self._runner.run(command, out, self._cancel)
                    exit_code = outcome.exit_code
                    message = outcome.error or ""
                    if outcome.timed_out:
                        message = f"timed out after {step.spec.timeout:g}s"
                    if outcome.cancelled or exit_code == 0:
                        break
                if self._cancel.is_set():
                    result.status = Status.CANCELLED
                    message = message or "cancelled"
        except (PtkError, SubstitutionError, ValueError, OSError) as exc:
            exit_code, message = 1, str(exc)
            self._log(Level.ERROR, message, step)
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

    def _run_builtin(
        self, step: PlannedStep, out: Callable[[str], None]
    ) -> tuple[int, str]:
        name = step.spec.uses or ""
        handler = self._builtins.get(name)
        if handler is None:
            return (
                1,
                f"built-in step '{name}' is not available{did_you_mean(name, self._builtins)}",
            )
        return handler(step, out), ""

    def _command(
        self, prepared: PreparedRun, step: PlannedStep, runtime: PythonRuntime | None
    ):
        os_name = self._host.os_name()
        plan = prepared.plan
        env = dict(plan.base_env)
        env.update(
            {
                "PTK_STEP": step.label,
                "PTK_BUILD_DIR": str(
                    prepared.layout.build_dir(plan.variant, plan.action, step.path)
                ),
                "PTK_STEP_REPORTS_DIR": str(
                    prepared.layout.reports_dir(plan.variant, plan.action, step.path)
                ),
            }
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
            self._powershell = "pwsh" if self._runner.which("pwsh") else "powershell"
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
