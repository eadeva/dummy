"""Commands generated from the configured jobs (driver).

Every job becomes a command with real, typed options for its parameters::

    ptk -V b_us build --jobs 4 --build-type Debug --from compile -- extra args
    ptk build --dry-run --jobs 4            # same options, nothing is executed

Option values are only passed on when given; defaults are resolved by the
use case (so per-variant defaults and sources work the same everywhere).
Maintainer-only jobs are hidden from users and refused when invoked.
"""

from __future__ import annotations

import dataclasses
import shlex
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rich_click as click
import yaml
from rich.markup import escape

from ...domain.config.model import JobSpec, ParamSpec
from ...domain.errors import PtkError
from ...domain.suggest import did_you_mean
from .access import AccessGroup, denied_command, in_maintainer
from .completion import features as complete_features
from .completion import passthrough_steps as complete_passthrough
from .completion import steps as complete_steps
from .options import SuggestedCommand, SuggestedOption
from .report_links import print_report
from .state import console, err_console, guarded, report_error, state_of

if TYPE_CHECKING:
    from ...application.use_cases.run import RunRequest

PARAM_PREFIX = "param__"  # keeps job parameters apart from the common options


# --------------------------------------------------------------------------- helpers


def pairs(values: tuple[str, ...], option: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise PtkError(f"{option} expects NAME=VALUE, got {item!r}")
        key = key.strip()
        result[key.replace("-", "_") if option == "--param" else key] = value
    return result


def params_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PtkError(f"{path}: a params file must be a mapping of names to values")
    return data


def option_name(param: str) -> str:
    return "--" + param.replace("_", "-")


def param_option(name: str, spec: ParamSpec) -> click.Option:
    hints = []
    if spec.required:
        hints.append("required")
    if spec.default is not None and spec.type != "secret":
        default = (
            spec.default
            if not isinstance(spec.default, list)
            else ",".join(spec.default)
        )
        hints.append(f"default: {default}")
    if spec.env:
        hints.append(f"env: {spec.env}")
    help_text = spec.help + (
        f" [dim]\\[{escape(', '.join(hints))}][/]" if hints else ""
    )
    dest = PARAM_PREFIX + name
    if spec.type == "secret":
        return click.Option(
            [option_name(name), dest],
            is_flag=True,
            default=None,
            help=help_text + " Prompt for a hidden value (or configure env:).",
        )
    if spec.type == "bool":
        flag = option_name(name)
        return click.Option(
            [f"{flag}/--no-{flag[2:]}", dest], default=None, help=help_text
        )
    kinds: dict[str, Any] = {
        "str": click.STRING,
        "path": click.Path(),
        "int": click.INT,
        "float": click.FLOAT,
        "list": click.STRING,
    }
    kind = (
        click.Choice(spec.choices or []) if spec.type == "choice" else kinds[spec.type]
    )
    metavar = "A,B,..." if spec.type == "list" else None
    return click.Option(
        [option_name(name), dest],
        type=kind,
        default=None,
        help=help_text,
        metavar=metavar,
    )


def common_options() -> list[click.Parameter]:
    params: list[click.Parameter] = [
        click.Option(
            ["--all-variants"], is_flag=True, help="Run all concrete variants."
        ),
        SuggestedOption(
            ["--feature", "features"],
            multiple=True,
            metavar="FEATURE=VALUE",
            help="Override a variant feature for this invocation.",
            shell_complete=complete_features,
        ),
        SuggestedOption(
            ["--from", "start"],
            metavar="STEP",
            help="Start at this top-level step.",
            shell_complete=complete_steps,
        ),
        SuggestedOption(
            ["--to", "end"],
            metavar="STEP",
            help="Stop after this top-level step.",
            shell_complete=complete_steps,
        ),
        click.Option(
            ["--params", "params_path"],
            type=click.Path(path_type=Path, dir_okay=False, exists=True),
            help="YAML file with parameter values.",
        ),
        SuggestedOption(
            ["--args-for"],
            multiple=True,
            metavar='STEP="ARGS"',
            help="Extra arguments for one step with passthrough: true (STEP is a/b).",
            shell_complete=complete_passthrough,
        ),
    ]
    params.extend(
        [
            click.Option(
                ["--dry-run"],
                is_flag=True,
                help="Preview execution without running steps or installing tools.",
            ),
            click.Option(
                ["--env", "show_env"],
                is_flag=True,
                help="Include generated PTK_/VH_ variables in a dry run.",
            ),
            click.Option(
                ["-q", "--quiet"],
                is_flag=True,
                help="Only warnings and errors; command output is still logged.",
            ),
            click.Option(
                ["--setup"],
                is_flag=True,
                help="Install required tools before running (self-service tools).",
            ),
        ]
    )
    params.append(
        click.Argument(
            ["extra"], nargs=-1, type=click.UNPROCESSED, metavar="[-- ARGS]..."
        )
    )
    return params


# --------------------------------------------------------------------------- execution


def build_request(
    ctx: click.Context,
    job: str | None,
    *,
    params: dict[str, Any] | None = None,
    extra: tuple[str, ...] = (),
    all_variants: bool = False,
    features: tuple[str, ...] = (),
    start: str | None = None,
    end: str | None = None,
    params_path: Path | None = None,
    args_for: tuple[str, ...] = (),
    dry_run: bool = False,
) -> RunRequest:
    from ...application.use_cases.run import RunRequest

    project = state_of(ctx).project()
    name = job or project.config.project.default_job
    spec = project.config.jobs.get(name)
    if spec is not None and (spec.audience == "maintainer") != in_maintainer(ctx):
        if spec.audience == "maintainer":
            raise PtkError(
                f"{name!r} is a maintainer-only job; use 'ptk maintainer run {name}'"
            )
        raise PtkError(f"{name!r} is an everyday job; use 'ptk {name}'")
    return RunRequest(
        job=job,
        variant=state_of(ctx).variant,
        all_variants=all_variants,
        feature_overrides={
            **pairs(
                tuple(
                    v[3:]
                    for v in ctx.find_root().params.get("overrides", ())
                    if v.startswith("vh.")
                ),
                "--set vh",
            ),
            **pairs(features, "--feature"),
        },
        params=params or {},
        params_file=params_file(params_path),
        start=start,
        end=end,
        passthrough=list(extra),
        args_for={k: shlex.split(v) for k, v in pairs(args_for, "--args-for").items()},
        dry_run=dry_run,
        role=state_of(ctx).role(),
    )


def execute(
    ctx: click.Context,
    request: RunRequest,
    *,
    quiet: bool = False,
    show_env: bool = False,
    setup: bool = False,
) -> None:
    state = state_of(ctx)
    project = state.project()
    if request.all_variants and request.variant:
        raise PtkError("use --all-variants or --variant, not both")
    service = state.app.variants(project)
    if request.all_variants:
        names = service.line.buildable()
        if not names:
            raise PtkError("no concrete variants configured")
    elif request.variant:
        names = list(
            dict.fromkeys(
                service.name_of(n.strip()) for n in request.variant.split(",")
            )
        )
    else:
        names = [None]
    from .cleanup import clean_selected, mode

    cleaning = mode(state)
    if show_env and not request.dry_run:
        raise PtkError("--env requires --dry-run")
    if setup and not state.clean and not request.dry_run:
        job = request.job or project.config.project.default_job
        if job:
            install_tools(state, project, [job])
    if state.clean:
        from ...application.use_cases.cleanup import prepare_cleanup

        prepared = [
            prepare_cleanup(project, request.job, name, state.role()) for name in names
        ]
        clean_selected(prepared, dry_run=request.dry_run)
        return
    # Preflight the whole selection before executing the first variant.
    prepared = [
        state.app.prepare_run(project).execute(
            project, dataclasses.replace(request, variant=name, all_variants=False)
        )
        for name in names
    ]
    if cleaning:
        clean_selected(prepared, dry_run=request.dry_run)
        if state.clean:
            return
    if not request.dry_run:
        state.app.hooks.execute(project, click.echo)
    codes = []
    for item in prepared:
        code = _execute_one(ctx, request, prepared=item, quiet=quiet, show_env=show_env)
        codes.append(code)
        if code == 130:
            break
    if not request.dry_run:
        sys.exit(130 if 130 in codes else max(codes, default=0))


def _execute_one(ctx, request, *, quiet=False, show_env=False, prepared=None):
    if request.dry_run:
        return _execute_one_unlocked(
            ctx, request, quiet=quiet, show_env=show_env, prepared=prepared
        )
    from ...adapters.locking import job_lock

    with job_lock(prepared.project.root, prepared.plan.variant, prepared.plan.job):
        return _execute_one_unlocked(
            ctx, request, quiet=quiet, show_env=show_env, prepared=prepared
        )


def _execute_one_unlocked(
    ctx: click.Context,
    request: RunRequest,
    *,
    quiet: bool = False,
    show_env: bool = False,
    prepared=None,
) -> int:
    """Prepare the request; show it (dry run) or run it and exit with its status."""
    from ...application.use_cases.run import Cancelled
    from ...domain.execution.model import Status
    from ...domain.logging import console_level
    from . import console as present

    state = state_of(ctx)
    project = prepared.project
    runner = state.app.run_job(project)
    if request.dry_run:
        present.dry_run(console, prepared, runner, show_env=show_env)
        return 0
    level = console_level(
        project.config.logging.level, verbose=state.verbose, quiet=quiet
    )
    observers = [
        present.ConsoleObserver(console, quiet=quiet, level=level),
        *state.app.log_observers(prepared),
    ]
    cancel = Cancelled()
    holder: dict[str, Any] = {}

    def work() -> None:
        try:
            holder["result"] = runner.execute(prepared, observers, cancel)
        except BaseException as exc:  # noqa: BLE001 - re-raised in the main thread
            holder["error"] = exc

    worker = threading.Thread(target=work, name="ptk-run")
    worker.start()
    try:
        while worker.is_alive():
            worker.join(0.2)
    except KeyboardInterrupt:
        err_console.print("[yellow]cancelling - terminating running processes ...[/]")
        cancel.set()
        worker.join()
    if "error" in holder:
        raise holder["error"]
    result = holder["result"]
    present.summary(console, result)
    write_reports(state, project, prepared.plan, result)
    codes = {Status.PASSED: 0, Status.SKIPPED: 0, Status.CANCELLED: 130}
    return codes.get(result.status, 1)


def install_tools(
    state: Any,
    project: Any,
    jobs: list[str] | None,
    *,
    dry_run: bool = False,
    allow_system: bool = False,
) -> bool:
    """Check and install tools; prints a line per tool. True when all are fine."""
    from ...application.use_cases.tools import tools_for_jobs

    project = tools_for_jobs(project, jobs)
    service = state.app.tools
    names = service.required(project, jobs)
    if not names:
        console.print("[dim]no tools required[/]")
        return True
    results = service.setup(
        project,
        names,
        dry_run=dry_run,
        allow_system=allow_system,
        out=lambda line: console.print(f"  [dim]{escape(line)}[/]", highlight=False),
    )
    for result in results:
        status = result.after or result.before
        colour = "green" if result.ok else "red"
        version = f" {status.version}" if status.version else ""
        console.print(
            f"[{colour}]{'✔' if result.ok else '✘'} {escape(result.name)}{version}[/] "
            f"[dim]{escape(result.outcome)}[/]",
            highlight=False,
        )
    return all(r.ok for r in results)


def write_reports(
    state: Any, project: Any, plan: Any, result: Any, *, open_browser=True
) -> Path | None:
    """Reports after every run; a reporting problem never changes the run's result."""
    from ...domain.reporting.summary import run_summary

    policy = None if project.ci else project.config.jobs[plan.job].open_report
    formats = list(project.config.reporting.formats)
    if policy and "html" not in formats:
        formats.append("html")
    if not formats:
        return
    try:
        report, files = state.app.reports.write(
            project, run_summary(plan, result), formats
        )
    except (PtkError, OSError, ValueError) as exc:
        err_console.print(f"[yellow]report not written: {escape(str(exc))}[/]")
        return
    html = next((f for f in files if f.suffix == ".html"), None)
    shown = html or (files[0] if files else None)
    if shown is not None:
        print_report(shown)
    for problem in report.problems:
        err_console.print(f"[yellow]report: {escape(problem)}[/]")
    if html is not None and (
        policy == "always" or (policy == "on_errors" and report.has_errors)
    ):
        if not open_browser:
            return html
        try:
            opened = state.app.open_in_browser(html)
        except (OSError, ValueError):
            opened = False
        if not opened:
            console.print(
                "[dim]no browser available here - open the report file above[/]"
            )
        return html
    return None


# --------------------------------------------------------------------------- commands


def job_command(name: str, spec: JobSpec, *, hidden: bool) -> click.Command:
    def callback(**options: Any) -> None:
        ctx = click.get_current_context()
        dry_run = options.pop("dry_run", False)
        given = {
            key[len(PARAM_PREFIX) :]: value
            for key, value in options.items()
            if key.startswith(PARAM_PREFIX) and value is not None
        }
        for param in list(given):
            if spec.params[param].type == "secret":
                given[param] = (
                    "********"
                    if dry_run or state_of(ctx).clean
                    else click.prompt(param, hide_input=True)
                )
        quiet = options.pop("quiet", False)
        show_env = options.pop("show_env", False)
        setup = options.pop("setup", False)
        common = {k: v for k, v in options.items() if not k.startswith(PARAM_PREFIX)}
        request = build_request(ctx, name, params=given, dry_run=dry_run, **common)
        execute(ctx, request, quiet=quiet, show_env=show_env, setup=setup)

    help_text = spec.help or f"Run the '{name}' job."
    if spec.audience == "maintainer":
        help_text += " [dim](maintainers only)[/]"
    command = SuggestedCommand(
        name,
        callback=guarded(callback),
        params=[
            *(param_option(p, s) for p, s in spec.params.items()),
            *common_options(),
        ],
        help=help_text,
        short_help=spec.help.splitlines()[0] if spec.help else None,
        hidden=hidden,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    command.ptk_job = name  # type: ignore[attr-defined]  # marker for the HTML help
    return command


def _broken(name: str, exc: PtkError) -> click.Command:
    def callback() -> None:
        report_error(exc)
        sys.exit(2)

    return click.RichCommand(name, callback=callback, help="(configuration error)")


class ProjectGroup(AccessGroup):
    """A group whose commands include the jobs of the current project.

    The audience selects everyday or maintainer commands.
    """

    def __init__(self, *args: Any, audience: str = "all", **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.audience = audience

    def _jobs(self, ctx: click.Context) -> dict[str, JobSpec]:
        project = state_of(ctx).try_project()
        return (
            {
                name: spec
                for name, spec in project.config.jobs.items()
                if not spec.only_cx or project.ci
            }
            if project
            else {}
        )

    def _workflows(self, ctx):
        if ctx.find_root().meta.get("vmr_repositories") is not None and not any(
            getattr(c.command, "repository_boundary", False) for c in ancestors(ctx)
        ):
            from .workflows import can_view, catalog, matches_namespace

            parent, _, owners, available = catalog(ctx)
            return {
                name: spec
                for name, (owner, spec, _) in available.items()
                if can_view(parent, owners, owner, spec)
                and matches_namespace(ctx, owners, owner, spec)
            }
        state = state_of(ctx)
        project = state.try_project()
        if project is None:
            return {}
        return {
            name: spec
            for name, spec in project.config.workflows.items()
            if (
                "maintainer"
                if project.config.command_audience.get("workflow") == "maintainer"
                else spec.audience
            )
            == self.audience
            and (self.audience == "all" or state.role() == "maintainer")
        }

    def list_commands(self, ctx: click.Context) -> list[str]:
        builtins = super().list_commands(ctx)
        role = state_of(ctx).role()
        jobs = [
            n
            for n, spec in self._jobs(ctx).items()
            if spec.audience == self.audience
            and (self.audience == "all" or role == "maintainer")
        ]
        return [
            *sorted(set(jobs) - set(self.commands)),
            *sorted(self._workflows(ctx).keys() - set(jobs) - set(self.commands)),
            *builtins,
        ]

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        builtin = super().get_command(ctx, cmd_name)
        if builtin is not None:
            return builtin
        if ctx.find_root().meta.get("vmr_repositories") is not None and not any(
            getattr(c.command, "repository_boundary", False) for c in ancestors(ctx)
        ):
            from .workflows import workflow_command

            spec = self._workflows(ctx).get(cmd_name)
            return workflow_command(cmd_name, spec) if spec else None
        state = state_of(ctx)
        try:
            project = state.project()
        except PtkError as exc:
            return _broken(cmd_name, exc)
        spec = project.config.jobs.get(cmd_name)
        if spec is not None and spec.only_cx and not project.ci:
            return None
        workflow = self._workflows(ctx).get(cmd_name)
        if workflow is not None and (
            spec is None or (spec.audience != self.audience and not project.ci)
        ):
            from .workflows import workflow_command

            return workflow_command(cmd_name, workflow)
        if spec is None:
            return None
        hidden = spec.audience != self.audience or (
            spec.audience == "maintainer" and state.role() != "maintainer"
        )
        if hidden:
            return denied_command(cmd_name, "job")
        command = job_command(cmd_name, spec, hidden=hidden)
        if workflow is not None:
            command.short_help = f"{spec.help or cmd_name} (job / workflow)"
            command.help += f"\n\nAlso a local workflow. Choose explicitly with 'ptk {'maintainer ' if self.audience == 'maintainer' else ''}run {cmd_name}' or 'ptk {'maintainer ' if self.audience == 'maintainer' else ''}workflow run {cmd_name}'. CX always runs the job."
        return command

    def format_help(self, ctx: click.Context, formatter: Any) -> None:
        """Show jobs, then workflows, above ptk's built-in commands."""
        all_builtins = super().list_commands(ctx)
        builtins = [n for n in all_builtins if not self.commands[n].hidden]
        shortcuts = [n for n in self.list_commands(ctx) if n not in self.commands]
        job_specs = self._jobs(ctx)
        jobs = [
            n
            for n in shortcuts
            if n in job_specs and job_specs[n].audience == self.audience
        ]
        workflow_specs = self._workflows(ctx)
        workflows = [n for n in shortcuts if n in workflow_specs]
        groups = []
        if jobs:
            groups.append(
                {
                    "name": "Jobs (from the project configuration)",
                    "commands": jobs,
                }
            )
        if workflows:
            groups.append(
                {
                    "name": "Workflows (from the project configuration)",
                    "commands": workflows,
                    # A job and workflow may share a name; show both categories.
                    "deduplicate": False,
                }
            )
        for title, names in (
            (
                "Commands",
                [n for n in builtins if n not in {"self-service", "maintainer"}],
            ),
            ("Self-service", [n for n in builtins if n == "self-service"]),
            ("Maintenance", [n for n in builtins if n == "maintainer"]),
        ):
            if names:
                groups.append({"name": title, "commands": names})
        config = getattr(formatter, "config", None)
        if config is not None and groups:
            config.command_groups = {ctx.command_path: groups}
        super().format_help(ctx, formatter)

    def resolve_command(self, ctx: click.Context, args: list[str]) -> Any:
        name = args[0] if args else None
        if (
            name not in self.commands
            and name in self._workflows(ctx)
            and name in self._jobs(ctx)
        ):
            state = state_of(ctx)
            job = self._jobs(ctx)[name]
            if (
                not ctx.resilient_parsing
                and not state.project().ci
                and job.audience == self.audience
                and not any(arg in ("-h", "--help") for arg in args[1:])
            ):
                if not sys.stdin.isatty():
                    ctx.fail(
                        f"'{name}' names both a job and a workflow; use 'ptk {'maintainer ' if self.audience == 'maintainer' else ''}run {name}' or 'ptk {'maintainer ' if self.audience == 'maintainer' else ''}workflow run {name}' in non-interactive calls."
                    )
                choice = click.prompt(
                    f"'{name}' is both a job and a workflow. Run which",
                    type=click.Choice(["job", "workflow"], case_sensitive=False),
                )
                if choice == "workflow":
                    from .workflows import workflow_command

                    return (
                        name,
                        workflow_command(name, self._workflows(ctx)[name]),
                        args[1:],
                    )
        if (
            not ctx.resilient_parsing
            and name
            and not name.startswith("-")
            and self.get_command(ctx, name) is None
        ):
            ctx.fail(
                f"No such command '{name}'{did_you_mean(name, self.list_commands(ctx))}."
            )
        return super().resolve_command(ctx, args)


def ancestors(ctx):
    while ctx is not None:
        yield ctx
        ctx = ctx.parent
