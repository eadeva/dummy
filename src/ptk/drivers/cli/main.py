"""ptk command line (driver).

Thin layer: parse options, call use cases, present results. ``ptk run ACTION``
is the generic entry point; per-action commands with typed options are
generated from the configuration in a later milestone.
"""

from __future__ import annotations

import functools
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rich_click as click
import yaml
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ... import __version__
from ...application.use_cases.help import HelpCommand, HelpOption
from ...application.use_cases.project import Project
from ...application.use_cases.run import Cancelled, RunRequest
from ...bootstrap import App, create_app
from ...domain.errors import ConfigError, PtkError
from ...domain.execution.model import Status
from ...domain.logging import console_level
from . import console as present

console = Console()
err_console = Console(stderr=True)

if hasattr(click.rich_click, "TEXT_MARKUP"):
    click.rich_click.TEXT_MARKUP = "rich"
else:  # pragma: no cover - older rich-click
    click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True


@dataclass
class CliState:
    app: App
    config: Path | None = None
    overrides: tuple[str, ...] = ()
    ci: bool | None = None
    verbose: int = 0
    _project: Project | None = field(default=None, repr=False)

    def project(self) -> Project:
        if self._project is None:
            self._project = self.app.load_project.execute(
                config_file=self.config, overrides=self.overrides, ci=self.ci
            )
        return self._project


def guarded(fn):
    """Turn expected errors into clean messages and exit code 2."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ConfigError as exc:
            err_console.print("[bold red]error:[/] invalid configuration")
            for problem in exc.problems:
                err_console.print(
                    f"  {problem}", markup=False, highlight=False, soft_wrap=True
                )
            sys.exit(2)
        except PtkError as exc:
            err_console.print(
                f"[bold red]error:[/] {exc}", highlight=False, soft_wrap=True
            )
            sys.exit(2)

    return wrapper


def _state(ctx: click.Context) -> CliState:
    return ctx.find_object(CliState)


# --------------------------------------------------------------------------- root


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.option(
    "-c",
    "--config",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    help="Path to main.ptk.yml (default: search upwards from the current directory).",
)
@click.option(
    "-s",
    "--set",
    "overrides",
    multiple=True,
    metavar="PATH=VALUE",
    help="Override a configuration value, e.g. --set actions.build.params.jobs.default=4",
)
@click.option(
    "--ci/--no-ci", default=None, help="Force CI mode on/off (default: detected)."
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="More ptk messages: -v debug, -vv trace (default: logging.level).",
)
@click.version_option(__version__, prog_name="ptk")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Path | None,
    overrides: tuple[str, ...],
    ci: bool | None,
    verbose: int,
) -> None:
    """[bold]ptk[/] - project tool kit.

    Without a command, ptk runs the project's default action
    ([italic]project.default_action[/]).
    """
    ctx.obj = CliState(
        app=create_app(), config=config, overrides=overrides, ci=ci, verbose=verbose
    )
    if ctx.invoked_subcommand is not None:
        return
    try:
        default = ctx.obj.project().config.project.default_action
    except PtkError:
        default = None  # not in a project (or broken config): just show the help
    if default is None:
        click.echo(ctx.get_help())
        return
    err_console.print(
        f"[dim]running the default action '{escape(default)}' "
        "(project.default_action) - 'ptk --help' lists all commands[/]",
        highlight=False,
    )
    ctx.invoke(run_command)


# --------------------------------------------------------------------------- config


@cli.group("config")
def config_group() -> None:
    """Inspect and validate the configuration."""


@config_group.command("validate")
@click.pass_context
@guarded
def config_validate(ctx: click.Context) -> None:
    """Validate main.ptk.yml and everything it includes."""
    project = _state(ctx).project()
    console.print(
        f"[green]configuration is valid[/] ({len(project.files)} file(s), "
        f"layers: {', '.join(project.layers)})"
    )


@config_group.command("show")
@click.argument("path", required=False)
@click.option(
    "--sources", is_flag=True, help="Show the file and line every value comes from."
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    show_default=True,
)
@click.pass_context
@guarded
def config_show(ctx: click.Context, path: str | None, sources: bool, fmt: str) -> None:
    """Show the merged configuration (or the value at PATH, e.g. actions.build)."""
    state = _state(ctx)
    result = state.app.show_config.execute(state.project(), path)
    if sources:
        table = Table("path", "source", box=None, pad_edge=False)
        for value_path, location in result.sources:
            table.add_row(value_path, location)
        console.print(table)
        return
    if fmt == "json":
        console.print_json(json.dumps(result.value, default=str))
    else:
        console.print(
            yaml.safe_dump(result.value, sort_keys=False, allow_unicode=True).rstrip(),
            markup=False,
            highlight=False,
        )


@config_group.command("schema")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Write to a file (e.g. .ptk/schema.json) instead of stdout.",
)
@click.pass_context
@guarded
def config_schema(ctx: click.Context, output: Path | None) -> None:
    """Print the JSON Schema of *.ptk.yml files (for editor autocompletion)."""
    schema = _state(ctx).app.export_schema.execute()
    text = json.dumps(schema, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        console.print(f"schema written to {output}")
    else:
        click.echo(text)


# --------------------------------------------------------------------------- variant


@cli.group("variant")
def variant_group() -> None:
    """Inspect variants: list, show, explain, check."""


def _value(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "-" if value is None else str(value)


@variant_group.command("list")
@click.option(
    "--names",
    is_flag=True,
    help="Print buildable variant names only (for CI matrices).",
)
@click.pass_context
@guarded
def variant_list(ctx: click.Context, names: bool) -> None:
    """List variants."""
    service = _state(ctx).app.variants(_state(ctx).project())
    items = service.list(include_abstract=not names)
    if names:
        click.echo("\n".join(v.name for v in items))
        return
    table = Table(
        "variant", "aliases", "extends", "description", box=None, pad_edge=False
    )
    for v in items:
        label = (
            v.name
            + (" [dim](abstract)[/]" if v.abstract else "")
            + (" [green]*[/]" if v.default else "")
        )
        table.add_row(
            label,
            ", ".join(v.aliases) or "-",
            ", ".join(v.extends) or "-",
            v.description,
        )
    console.print(table)


@variant_group.command("show")
@click.argument("name", required=False)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option(
    "--all", "show_all", is_flag=True, help="Include features of inactive components."
)
@click.pass_context
@guarded
def variant_show(
    ctx: click.Context, name: str | None, as_json: bool, show_all: bool
) -> None:
    """Show the resolved values of a variant (default variant if NAME is omitted)."""
    service = _state(ctx).app.variants(_state(ctx).project())
    resolved = service.resolve(name)
    if as_json:
        console.print_json(resolved.model_dump_json())
        sys.exit(0 if resolved.ok else 1)
    console.print(
        f"[bold]{resolved.name}[/]"
        + (f" - {resolved.description}" if resolved.description else "")
    )
    console.print(f"inherits   : {' -> '.join(resolved.chain)}")
    console.print(f"components : {', '.join(resolved.components) or '-'}")
    table = Table("feature", "component", "value", "source", box=None, pad_edge=False)
    for f in resolved.features.values():
        if not f.active and not show_all:
            continue
        source = {
            "variant": f"set in {f.set_by}",
            "depends_on": "off (depends_on)",
        }.get(f.source, f.source)
        table.add_row(f.name, f.component, _value(f.value), source)
    console.print(table)
    _print_issues(resolved)
    sys.exit(0 if resolved.ok else 1)


def _print_issues(resolved) -> None:
    if not resolved.issues:
        console.print("[green]OK[/]")
    for issue in resolved.issues:
        colour = "red" if issue.severity.value == "error" else "yellow"
        console.print(
            f"[{colour}]{issue.severity.value}[/]: {issue.message}", highlight=False
        )


@variant_group.command("explain")
@click.argument("name")
@click.argument("feature")
@click.pass_context
@guarded
def variant_explain(ctx: click.Context, name: str, feature: str) -> None:
    """Explain why FEATURE has its value in variant NAME."""
    service = _state(ctx).app.variants(_state(ctx).project())
    click.echo("\n".join(service.explain(name, feature)))


@variant_group.command("check")
@click.argument("names", nargs=-1)
@click.option("--strict", is_flag=True, help="Treat warnings as errors.")
@click.pass_context
@guarded
def variant_check(ctx: click.Context, names: tuple[str, ...], strict: bool) -> None:
    """Validate variants (default: all buildable). Exit code 1 on errors."""
    service = _state(ctx).app.variants(_state(ctx).project())
    results = service.check(list(names) or None)
    failed = False
    for name, resolved in results.items():
        bad = not resolved.ok or (strict and resolved.warnings)
        failed |= bool(bad)
        status = "[red]FAILED[/]" if bad else "[green]OK[/]"
        console.print(f"{name:<30} {status}")
        for issue in resolved.issues:
            console.print(f"    {issue}", highlight=False)
    sys.exit(1 if failed else 0)


# --------------------------------------------------------------------------- run


def _pairs(values: tuple[str, ...], option: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise PtkError(f"{option} expects NAME=VALUE, got {item!r}")
        result[
            key.strip().replace("-", "_") if option == "--param" else key.strip()
        ] = value
    return result


def _params_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PtkError(
            f"{path}: a params file must be a mapping of parameter names to values"
        )
    return data


def _action_options(fn):
    """Options shared by ``ptk run`` and ``ptk dry-run``."""
    decorators = [
        click.argument("action", required=False),
        click.argument(
            "extra", nargs=-1, type=click.UNPROCESSED, metavar="[-- ARGS]..."
        ),
        click.option(
            "-V",
            "--variant",
            help="Variant (name or alias); default: the configured default variant.",
        ),
        click.option(
            "--from", "start", metavar="STEP", help="Start at this top-level step."
        ),
        click.option(
            "--to", "end", metavar="STEP", help="Stop after this top-level step."
        ),
        click.option(
            "-p",
            "--param",
            "params",
            multiple=True,
            metavar="NAME=VALUE",
            help="Set an action parameter (default values come from the configuration).",
        ),
        click.option(
            "--params",
            "params_file",
            type=click.Path(path_type=Path, dir_okay=False, exists=True),
            help="YAML file with parameter values.",
        ),
        click.option(
            "--args-for",
            multiple=True,
            metavar='STEP="ARGS"',
            help="Extra arguments for one step with passthrough: true (STEP is a/b).",
        ),
    ]
    for decorator in reversed(decorators):
        fn = decorator(fn)
    return fn


def _prepare(
    ctx: click.Context,
    action: str | None,
    extra: tuple[str, ...],
    variant: str | None,
    start: str | None,
    end: str | None,
    params: tuple[str, ...],
    params_file: Path | None,
    args_for: tuple[str, ...],
    *,
    dry_run: bool,
):
    import shlex

    state = _state(ctx)
    project = state.project()
    if action is not None and action.startswith("-"):
        # "ptk run -- -k x": click put the first pass-through word into ACTION
        extra, action = (action, *extra), None
    request = RunRequest(
        action=action,
        variant=variant,
        params=_pairs(params, "--param"),
        params_file=_params_file(params_file),
        start=start,
        end=end,
        passthrough=list(extra),
        args_for={k: shlex.split(v) for k, v in _pairs(args_for, "--args-for").items()},
        dry_run=dry_run,
    )
    prepared = state.app.prepare_run(project).execute(project, request)
    return prepared, state.app.run_action(project)


@cli.command("dry-run")
@_action_options
@click.option(
    "--env",
    "show_env",
    is_flag=True,
    help="Also show the generated PTK_/VH_ variables.",
)
@click.pass_context
@guarded
def dry_run_command(ctx: click.Context, show_env: bool, **options: Any) -> None:
    """Show what ACTION would do, without running anything.

    Prints the steps with conditions evaluated, the final command of every step,
    Python runtimes, step environment (secrets masked) and where every parameter
    value comes from. ACTION defaults to [italic]project.default_action[/].
    """
    prepared, runner = _prepare(ctx, dry_run=True, **options)
    present.dry_run(console, prepared, runner, show_env=show_env)


@cli.command("run")
@_action_options
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Only warnings and errors; command output is still logged.",
)
@click.pass_context
@guarded
def run_command(ctx: click.Context, quiet: bool = False, **options: Any) -> None:
    """Run ACTION (default: [italic]project.default_action[/]).

    Arguments after [bold]--[/] go to the step with [italic]passthrough: true[/].
    Preview first with [bold]ptk dry-run ACTION[/].

    Exit code: 0 passed, 1 failed, 2 usage/configuration error, 130 cancelled.
    """
    prepared, runner = _prepare(ctx, dry_run=False, **options)
    observers = [
        present.ConsoleObserver(
            console,
            quiet=quiet,
            level=console_level(
                _state(ctx).project().config.logging.level,
                verbose=_state(ctx).verbose,
                quiet=quiet,
            ),
        ),
        *_state(ctx).app.log_observers(prepared),
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
    codes = {Status.PASSED: 0, Status.SKIPPED: 0, Status.CANCELLED: 130}
    sys.exit(codes.get(result.status, 1))


# --------------------------------------------------------------------------- help


def _collect_commands(
    group: click.Group, ctx: click.Context, role: str
) -> list[HelpCommand]:
    """All commands of the click tree as plain data for the HTML help."""
    result: list[HelpCommand] = []

    def visit(
        command: click.Command, parent: click.Context | None, path: list[str]
    ) -> None:
        name = path[-1] if path else "ptk"
        sub = click.Context(command, info_name=name, parent=parent)
        options = []
        for param in command.get_params(sub):
            if not isinstance(param, click.Option) or param.hidden:
                continue
            names = ", ".join(param.opts + param.secondary_opts)
            if not param.is_flag and not param.count:
                names += f" {param.metavar or param.make_metavar(sub) if hasattr(param, 'make_metavar') else ''}".rstrip()
            default = ""
            if param.show_default and param.default not in (None, False, ()):
                default = str(param.default)
            options.append(
                HelpOption(
                    names,
                    (param.help or "")
                    .replace("[bold]", "")
                    .replace("[/]", "")
                    .replace("[italic]", ""),
                    default,
                )
            )
        usage = (
            " ".join(sub.command_path.split())
            + " "
            + " ".join(command.collect_usage_pieces(sub))
        )
        text = (
            (command.help or "")
            .replace("[bold]", "")
            .replace("[/]", "")
            .replace("[italic]", "")
        )
        result.append(
            HelpCommand(
                " ".join(path),
                usage.strip(),
                command.get_short_help_str(80),
                text.strip(),
                options,
            )
        )
        if isinstance(command, click.Group):
            for child_name in command.list_commands(sub):
                child = command.get_command(sub, child_name)
                if child is not None and not child.hidden:
                    visit(child, sub, [*path, child_name])

    visit(group, None, [])
    return result


@cli.command("help")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Where to write the page (default: .ptk/help.html in the project).",
)
@click.option(
    "--no-open", is_flag=True, help="Only write the file, do not open the browser."
)
@click.pass_context
def help_command(ctx: click.Context, output: Path | None, no_open: bool) -> None:
    """Open the full help as a web page: every action with its parameters and steps, variants, credentials,
    tools and all commands. Works offline."""
    import tempfile

    state = _state(ctx)
    project, error = None, None
    try:
        project = state.project()
    except ConfigError as exc:
        error = "; ".join(str(p) for p in exc.problems[:5])
    except PtkError as exc:
        error = str(exc)
    role = state.app.role(project)
    doc = state.app.build_help.execute(
        project, _collect_commands(cli, ctx, role), role, error
    )
    if output is None:
        base = project.root / ".ptk" if project else Path(tempfile.gettempdir()) / "ptk"
        output = base / "help.html"
    path = state.app.write_help(doc, output)
    console.print(
        f"help written to [bold]{escape(str(path))}[/]", highlight=False, soft_wrap=True
    )
    if not no_open and not state.app.open_in_browser(path):
        console.print(
            "[dim]no browser available here - open the file above on a machine with a desktop[/]"
        )


def main() -> None:
    cli(prog_name="ptk")


if __name__ == "__main__":  # pragma: no cover
    main()
