"""Commands generated from the configured actions (driver).

Every action becomes a command with real, typed options for its parameters::

    ptk build --jobs 4 --build-type Debug -V b_us --from compile -- extra args
    ptk dry-run build --jobs 4            # same options, nothing is executed

Option values are only passed on when given; defaults are resolved by the
use case (so per-variant defaults and sources work the same everywhere).
Maintainer-only actions are hidden from users and refused when invoked.
"""

from __future__ import annotations

import dataclasses
import shlex
import sys
import threading
from pathlib import Path
from typing import Any

import rich_click as click
import yaml
from rich.markup import escape

from ...application.use_cases.run import Cancelled, RunRequest
from ...application.use_cases.tools import tools_for_actions
from ...domain.config.model import ActionSpec, ParamSpec
from ...domain.errors import PtkError
from ...domain.execution.model import Status
from ...domain.logging import console_level
from ...domain.reporting.summary import run_summary
from ...domain.suggest import did_you_mean
from . import console as present
from .access import AccessGroup
from .report_links import print_report
from .state import console, err_console, guarded, report_error, state_of

PARAM_PREFIX = "param__"  # keeps action parameters apart from the common options


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


def common_options(*, dry_run: bool) -> list[click.Parameter]:
    params: list[click.Parameter] = [
        click.Option(
            ["--all-variants"], is_flag=True, help="Run all concrete variants."
        ),
        click.Option(
            ["--feature", "-bo", "features"],
            multiple=True,
            metavar="FEATURE=VALUE",
            help="Override a variant feature for this invocation.",
        ),
        click.Option(
            ["-mp", "legacy_params"],
            multiple=True,
            metavar="NAME=VALUE",
            help="Compatibility alias for declared action parameter values.",
        ),
        click.Option(
            ["-V", "--variant"],
            help="Variant (name or alias); default: the configured default variant.",
        ),
        click.Option(
            ["--from", "start"], metavar="STEP", help="Start at this top-level step."
        ),
        click.Option(
            ["--to", "end"], metavar="STEP", help="Stop after this top-level step."
        ),
        click.Option(
            ["--params", "params_path"],
            type=click.Path(path_type=Path, dir_okay=False, exists=True),
            help="YAML file with parameter values.",
        ),
        click.Option(
            ["--args-for"],
            multiple=True,
            metavar='STEP="ARGS"',
            help="Extra arguments for one step with passthrough: true (STEP is a/b).",
        ),
    ]
    if dry_run:
        params.append(
            click.Option(
                ["--env", "show_env"],
                is_flag=True,
                help="Also show the generated PTK_/VH_ variables.",
            )
        )
    else:
        params.append(
            click.Option(
                ["-q", "--quiet"],
                is_flag=True,
                help="Only warnings and errors; command output is still logged.",
            )
        )
        params.append(
            click.Option(
                ["--setup"],
                is_flag=True,
                help="Install missing or outdated tools of the action first (ptk setup install).",
            )
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
    action: str | None,
    *,
    params: dict[str, Any] | None = None,
    extra: tuple[str, ...] = (),
    variant: str | None = None,
    all_variants: bool = False,
    features: tuple[str, ...] = (),
    legacy_params: tuple[str, ...] = (),
    start: str | None = None,
    end: str | None = None,
    params_path: Path | None = None,
    args_for: tuple[str, ...] = (),
    dry_run: bool = False,
) -> RunRequest:
    return RunRequest(
        action=action,
        variant=variant,
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
        params={**pairs(legacy_params, "--param"), **(params or {})},
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
    if setup:
        action = request.action or project.config.project.default_action
        if action:
            install_tools(state, project, [action])
    # Preflight the whole selection before executing the first variant.
    prepared = [
        state.app.prepare_run(project).execute(
            project, dataclasses.replace(request, variant=name, all_variants=False)
        )
        for name in names
    ]
    codes = []
    for item in prepared:
        code = _execute_one(ctx, request, prepared=item, quiet=quiet, show_env=show_env)
        codes.append(code)
        if code == 130:
            break
    if not request.dry_run:
        sys.exit(130 if 130 in codes else max(codes, default=0))


def _execute_one(ctx, request, *, quiet=False, show_env=False, prepared=None):
    from ...adapters.locking import file_lock

    if request.dry_run:
        return _execute_one_unlocked(
            ctx, request, quiet=quiet, show_env=show_env, prepared=prepared
        )
    # Keep logs, report inputs and exports from concurrent CLI runs separate.
    lock = (
        prepared.project.root
        / ".ptk"
        / "locks"
        / (prepared.plan.variant or "default")
        / (prepared.plan.action + ".lock")
    )
    with file_lock(lock):
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
    state = state_of(ctx)
    project = prepared.project
    runner = state.app.run_action(project)
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
    actions: list[str] | None,
    *,
    dry_run: bool = False,
    allow_system: bool = False,
) -> bool:
    """Check and install tools; prints a line per tool. True when all are fine."""
    project = tools_for_actions(project, actions)
    service = state.app.tools
    names = service.required(project, actions)
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
    policy = None if project.ci else project.config.actions[plan.action].open_report
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
        print_report(
            state.app,
            shown,
            root=project.root,
            ci=project.ci,
            logs=[step.log_file for step in report.steps],
        )
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


def action_command(
    name: str, spec: ActionSpec, *, dry_run: bool, hidden: bool
) -> click.Command:
    def callback(**options: Any) -> None:
        ctx = click.get_current_context()
        given = {
            key[len(PARAM_PREFIX) :]: value
            for key, value in options.items()
            if key.startswith(PARAM_PREFIX) and value is not None
        }
        for param in list(given):
            if spec.params[param].type == "secret":
                given[param] = (
                    "********" if dry_run else click.prompt(param, hide_input=True)
                )
        quiet = options.pop("quiet", False)
        show_env = options.pop("show_env", False)
        setup = options.pop("setup", False)
        common = {k: v for k, v in options.items() if not k.startswith(PARAM_PREFIX)}
        request = build_request(ctx, name, params=given, dry_run=dry_run, **common)
        execute(ctx, request, quiet=quiet, show_env=show_env, setup=setup)

    help_text = spec.help or f"Run the '{name}' action."
    if spec.audience == "maintainer":
        help_text += " [dim](maintainers only)[/]"
    if dry_run:
        help_text = f"Show what '{name}' would do, without running anything."
    command = click.RichCommand(
        name,
        callback=guarded(callback),
        params=[
            *(param_option(p, s) for p, s in spec.params.items()),
            *common_options(dry_run=dry_run),
        ],
        help=help_text,
        short_help=spec.help.splitlines()[0] if spec.help else None,
        hidden=hidden,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    command.ptk_action = name  # type: ignore[attr-defined]  # marker for the HTML help
    return command


def _broken(name: str, exc: PtkError) -> click.Command:
    def callback() -> None:
        report_error(exc)
        sys.exit(2)

    return click.RichCommand(name, callback=callback, help="(configuration error)")


class ProjectGroup(AccessGroup):
    """A group whose commands include the actions of the current project.

    ``dry_run=True`` makes the action commands preview instead of run.
    """

    def __init__(self, *args: Any, dry_run: bool = False, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.dry_run = dry_run

    def _actions(self, ctx: click.Context) -> dict[str, ActionSpec]:
        project = state_of(ctx).try_project()
        return dict(project.config.actions) if project else {}

    def _workflows(self, ctx):
        if self.dry_run:
            return {}
        state = state_of(ctx)
        project = state.try_project()
        if project is None:
            return {}
        return {
            name: spec
            for name, spec in project.config.workflows.items()
            if state.role() == "maintainer"
            or (
                spec.audience == "all"
                and project.config.command_audience.get("workflow") != "maintainer"
            )
        }

    def list_commands(self, ctx: click.Context) -> list[str]:
        builtins = super().list_commands(ctx)
        role = state_of(ctx).role()
        actions = [
            n
            for n, spec in self._actions(ctx).items()
            if spec.audience == "all" or role == "maintainer"
        ]
        return [
            *builtins,
            *sorted((set(actions) | self._workflows(ctx).keys()) - set(self.commands)),
        ]

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        builtin = super().get_command(ctx, cmd_name)
        if builtin is not None:
            return builtin
        state = state_of(ctx)
        try:
            project = state.project()
        except PtkError as exc:
            return _broken(cmd_name, exc)
        spec = project.config.actions.get(cmd_name)
        workflow = self._workflows(ctx).get(cmd_name)
        if workflow is not None and (
            spec is None
            or (
                spec.audience == "maintainer"
                and state.role() != "maintainer"
                and not project.ci
            )
        ):
            from .workflows import workflow_command

            return workflow_command(cmd_name, workflow)
        if spec is None:
            return None
        hidden = spec.audience == "maintainer" and state.role() != "maintainer"
        command = action_command(cmd_name, spec, dry_run=self.dry_run, hidden=hidden)
        if workflow is not None:
            command.short_help = f"{spec.help or cmd_name} (action / workflow)"
            command.help += f"\n\nAlso a local workflow. Choose explicitly with 'ptk run {cmd_name}' or 'ptk workflow run {cmd_name}'. CX always runs the action."
        return command

    def format_help(self, ctx: click.Context, formatter: Any) -> None:
        """Project actions in their own panel, above ptk's built-in commands."""
        all_builtins = super().list_commands(ctx)
        builtins = [n for n in all_builtins if not self.commands[n].hidden]
        actions = [n for n in self.list_commands(ctx) if n not in all_builtins]
        groups = []
        if actions:
            groups.append(
                {
                    "name": "Actions and workflows (from the project configuration)"
                    if self._workflows(ctx)
                    else "Actions (from the project configuration)",
                    "commands": actions,
                }
            )
        if builtins:
            groups.append({"name": "Commands", "commands": builtins})
        config = getattr(formatter, "config", None)
        if config is not None and groups:
            config.command_groups = {ctx.command_path: groups}
        super().format_help(ctx, formatter)

    def resolve_command(self, ctx: click.Context, args: list[str]) -> Any:
        name = args[0] if args else None
        if (
            name in self._workflows(ctx)
            and name in self._actions(ctx)
            and name not in self.commands
        ):
            state = state_of(ctx)
            action = self._actions(ctx)[name]
            if (
                not state.project().ci
                and (action.audience == "all" or state.role() == "maintainer")
                and not any(arg in ("-h", "--help") for arg in args[1:])
            ):
                if not sys.stdin.isatty():
                    ctx.fail(
                        f"'{name}' names both an action and a workflow; use 'ptk run {name}' or 'ptk workflow run {name}' in non-interactive calls."
                    )
                choice = click.prompt(
                    f"'{name}' is both an action and a workflow. Run which",
                    type=click.Choice(["action", "workflow"], case_sensitive=False),
                )
                if choice == "workflow":
                    from .workflows import workflow_command

                    return (
                        name,
                        workflow_command(name, self._workflows(ctx)[name]),
                        args[1:],
                    )
        if name and not name.startswith("-") and self.get_command(ctx, name) is None:
            ctx.fail(
                f"No such command '{name}'{did_you_mean(name, self.list_commands(ctx))}."
            )
        return super().resolve_command(ctx, args)
