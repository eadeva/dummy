"""ptk command line (driver).

Thin layer: parse options, call use cases, present results. The configured
actions are generated commands (see :mod:`.actions`); ``ptk run ACTION`` is
the generic form and ``ptk dry-run ACTION`` previews either.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import rich_click as click
import yaml
from rich.markup import escape
from rich.table import Table

from ... import __version__
from ...application.use_cases.help import HelpCommand, HelpOption
from ...domain.errors import ConfigError, PtkError
from .access import AccessGroup
from .actions import (
    ProjectGroup,
    build_request,
    common_options,
    execute,
    install_tools,
    pairs,
)
from .state import console, err_console, guarded, state_of
from .versioning import version_group
from .workspace import WorkspaceGroup

_state = state_of

if hasattr(click.rich_click, "TEXT_MARKUP"):
    click.rich_click.TEXT_MARKUP = "rich"
else:  # pragma: no cover - older rich-click
    click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True


# --------------------------------------------------------------------------- root


@click.group(
    cls=WorkspaceGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.option(
    "-c",
    "--config",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    is_eager=True,  # known before --help lists the project's actions
    help="Path to .main.ptk.yml (default: search upwards from the current directory).",
)
@click.option(
    "-s",
    "--set",
    "overrides",
    multiple=True,
    is_eager=True,
    metavar="PATH=VALUE",
    help="Override a configuration value, e.g. --set actions.build.params.jobs.default=4",
)
@click.option(
    "--ci/--no-ci",
    default=None,
    is_eager=True,
    help="Force CI mode on/off (default: detected).",
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

    The project's actions are commands too ([bold]ptk build --help[/]). Without a
    command, ptk runs the default action ([italic]project.default_action[/]).
    """
    state = state_of(ctx)
    if ctx.invoked_subcommand is not None:
        return
    if (
        isinstance(ctx.command, WorkspaceGroup)
        and ctx.command._repositories(ctx) is not None
    ):
        click.echo(ctx.get_help())
        return
    project = state.try_project()  # outside a project / broken config: show the help
    default = project.config.project.default_action if project else None
    if default is None:
        click.echo(ctx.get_help())
        return
    err_console.print(
        f"[dim]running the default action '{escape(default)}' "
        "(project.default_action) - 'ptk --help' lists all commands[/]",
        highlight=False,
    )
    guarded(execute)(ctx, guarded(build_request)(ctx, None))


# --------------------------------------------------------------------------- config


@cli.group("config", cls=AccessGroup)
def config_group() -> None:
    """Inspect and validate the configuration."""


@config_group.command("validate")
@click.pass_context
@guarded
def config_validate(ctx: click.Context) -> None:
    """Validate .main.ptk.yml and everything it includes."""
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


@cli.group("variant", cls=AccessGroup)
def variant_group() -> None:
    """Inspect and edit variants: list, show, explain, check, set, new, gui."""


def _value(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "-" if value is None else str(value)


def _write_variant_change(ctx, name, features, output, dry_run, **options):
    from ...adapters.config.edits import write_overlay
    from ...application.use_cases.variant_changes import variant_patch

    state = _state(ctx)
    if ctx.find_root().params.get("overrides"):
        raise PtkError(
            "Do not combine persistent variant edits with global --set overrides"
        )
    project = state.project()
    patch = variant_patch(project, name, pairs(features, "--feature"), **options)
    target = output or project.config_root / "local.ptk.yml"
    text = write_overlay(target, patch, dry_run=dry_run)
    click.echo(
        text if dry_run else f"Updated {target}. YAML comments are not retained."
    )
    if output and not dry_run:
        click.echo("Include this overlay in your project to activate it.")


@variant_group.command("set")
@click.argument("name")
@click.argument("features", nargs=-1)
@click.option("-o", "--output", type=click.Path(path_type=Path, dir_okay=False))
@click.option("--dry-run", is_flag=True)
@click.pass_context
@guarded
def variant_set(ctx, name, features, output, dry_run):
    """Select the default variant and optionally set FEATURE=VALUE in local.ptk.yml."""
    _write_variant_change(ctx, name, features, output, dry_run)


@variant_group.command("new")
@click.argument("name")
@click.option("--extends", help="Base variant or alias.")
@click.option("--feature", "features", multiple=True, metavar="FEATURE=VALUE")
@click.option("--component", "components", multiple=True)
@click.option("-o", "--output", type=click.Path(path_type=Path, dir_okay=False))
@click.option("--dry-run", is_flag=True)
@click.pass_context
@guarded
def variant_new(ctx, name, extends, features, components, output, dry_run):
    """Create a validated variant in local.ptk.yml (or an explicit overlay)."""
    _write_variant_change(
        ctx,
        name,
        features,
        output,
        dry_run,
        create=True,
        extends=extends,
        components=components,
    )


@variant_group.command("gui")
@click.option(
    "--plugin",
    default="tkinter",
    show_default=True,
    help="Installed ptk.variant_gui plugin name.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default="main.variants-edited.ptk.yml",
    show_default=True,
)
@click.pass_context
@guarded
def variant_gui(ctx: click.Context, plugin: str, output: Path) -> None:
    """Edit variants in a desktop window and export a validated project copy."""
    from ...adapters.variant_editor import launch_editor
    from ...application.use_cases.variant_editor import VariantEditorSession

    project = _state(ctx).project()
    session = VariantEditorSession(project.config)
    session.initial_text()  # report absent variants before loading any GUI
    launch_editor(session, output.resolve(), plugin)


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


@cli.command("run")
@click.argument("action", required=False)
@click.option(
    "-p",
    "--param",
    "params",
    multiple=True,
    metavar="NAME=VALUE",
    help="Set an action parameter (unset ones use their configured default).",
)
@click.pass_context
@guarded
def run_command(
    ctx: click.Context, action: str | None, params: tuple[str, ...], **options: Any
) -> None:
    """Run ACTION by name - the generic form for scripts and CI.

    Same as [bold]ptk ACTION[/], but parameters are given as [bold]-p NAME=VALUE[/].
    ACTION defaults to [italic]project.default_action[/]. Arguments after [bold]--[/] go
    to the step with [italic]passthrough: true[/].

    Exit code: 0 passed, 1 failed, 2 usage/configuration error, 130 cancelled.
    """
    quiet = options.pop("quiet", False)
    setup = options.pop("setup", False)
    extra = options.pop("extra", ())
    if action is not None and action.startswith("-"):
        # "ptk run -- -k x": click put the first pass-through word into ACTION
        extra, action = (action, *extra), None
    request = build_request(
        ctx, action, params=pairs(params, "--param"), extra=extra, **options
    )
    execute(ctx, request, quiet=quiet, setup=setup)


# the same options as the generated action commands (incl. the trailing [-- ARGS])
run_command.params.extend(common_options(dry_run=False))


@cli.group("dry-run", cls=ProjectGroup, dry_run=True, invoke_without_command=True)
@click.pass_context
@guarded
def dry_run_group(ctx: click.Context, **options: Any) -> None:
    """Show what an action would do, without running anything.

    [bold]ptk dry-run ACTION [OPTIONS][/] takes exactly the options of
    [bold]ptk ACTION[/] and prints the steps with conditions evaluated, the final
    command of every step, Python runtimes, the step environment (secrets masked)
    and where every parameter value comes from. Without ACTION: the default action.
    """
    if ctx.invoked_subcommand is None:
        show_env = options.pop("show_env", False)
        options.pop("extra", None)
        execute(
            ctx, build_request(ctx, None, dry_run=True, **options), show_env=show_env
        )


# without ACTION, "ptk dry-run -V x" previews the default action with these options
dry_run_group.params.extend(
    p for p in common_options(dry_run=True) if p.name not in ("extra", "args_for")
)


# --------------------------------------------------------------------------- creds


@cli.group("creds", cls=AccessGroup)
def creds_group() -> None:
    """Credentials: env -> keyring -> gopass -> vault -> prompt. Values are never shown."""


def _read_secret(ctx: click.Context, question: str) -> str:
    prompter = _state(ctx).app.prompter
    if prompter.interactive():
        return prompter.secret(question)
    if not sys.stdin.isatty():
        return sys.stdin.read().rstrip("\r\n")  # e.g. piped from a secret manager
    raise PtkError(
        "no terminal: pipe the value in, e.g. 'gopass show -o x | ptk setup creds set NAME'"
    )


@creds_group.command("list")
@click.argument("name", required=False)
@click.pass_context
@guarded
def creds_list(ctx: click.Context, name: str | None) -> None:
    """Show which provider supplies each credential (never the values)."""
    service = _state(ctx).app.credentials(_state(ctx).project())
    rows = service.status(name)
    if not rows:
        console.print("no credentials configured")
        return
    table = Table(
        "credential", "provider", "env variable", "details", box=None, pad_edge=False
    )
    missing = False
    for row in rows:
        supplier = f"[green]{row.provider}[/]" if row.provider else "[red]missing[/]"
        missing |= row.provider is None
        details = "; ".join(row.notes)
        table.add_row(row.key.ref, supplier, row.key.env_var, escape(details))
    console.print(table)
    if missing:
        console.print("[dim]store a value with: ptk setup creds set NAME [FIELD][/]")


@creds_group.command("set")
@click.argument("name")
@click.argument("field", required=False)
@click.option(
    "--store",
    type=str,
    help="Where to store it (default: first available of the credential's providers).",
)
@click.pass_context
@guarded
def creds_set(
    ctx: click.Context, name: str, field: str | None, store: str | None
) -> None:
    """Store a credential. The value is typed hidden (or piped in) - never an argument."""
    service = _state(ctx).app.credentials(_state(ctx).project())
    field = field or service.spec(name).fields[0]
    [key] = service.keys(name, field)
    value = _read_secret(ctx, f"value for {key.ref}")
    target = service.store(name, field, value, store)
    console.print(f"[green]stored[/] {key.ref} in {target}")


@creds_group.command("remove")
@click.argument("name")
@click.argument("field", required=False)
@click.option(
    "--store",
    type=str,
    help="Only remove it from this store.",
)
@click.pass_context
@guarded
def creds_remove(
    ctx: click.Context, name: str, field: str | None, store: str | None
) -> None:
    """Remove a stored credential (from every store unless --store)."""
    service = _state(ctx).app.credentials(_state(ctx).project())
    removed = service.remove(name, field, store)
    console.print("removed " + ", ".join(removed) if removed else "nothing stored")


@creds_group.command("test")
@click.argument("name")
@click.pass_context
@guarded
def creds_test(ctx: click.Context, name: str) -> None:
    """Run the credential's 'test' command with its values as environment variables."""
    service = _state(ctx).app.credentials(_state(ctx).project())
    ok, lines = service.test(name)
    for line in lines:
        console.print(f"  {escape(line)}", highlight=False)
    console.print(f"[green]{name}: OK[/]" if ok else f"[red]{name}: FAILED[/]")
    sys.exit(0 if ok else 1)


@creds_group.command("setup")
@click.option(
    "--vault",
    "create_vault",
    is_flag=True,
    help="Create the built-in encrypted vault (asks for a master password).",
)
@click.pass_context
@guarded
def creds_setup(ctx: click.Context, create_vault: bool) -> None:
    """Check the credential providers on this machine and how to set them up."""
    app = _state(ctx).app
    providers = app.secret_providers
    if create_vault:
        vault = providers["vault"].vault  # type: ignore[attr-defined]
        vault.create()
        console.print(f"[green]vault created[/] at {escape(str(vault.path))}")
    table = Table("provider", "status", "notes", box=None, pad_edge=False)
    hints = {
        "env": "CI: set the variables shown by 'ptk setup creds list'",
        "keyring": "OS keyring: Windows Credential Manager, macOS Keychain, Linux desktop",
        "gopass": "recommended for teams: gopass setup --crypto age (no gpg needed)",
        "vault": "built-in encrypted file: ptk setup creds setup --vault",
        "prompt": "asks in the terminal, never stored",
    }
    for name, provider in providers.items():
        ok, reason = provider.available()
        status = "[green]ready[/]" if ok else "[yellow]not available[/]"
        table.add_row(name, status, escape(reason or hints.get(name, "")))
    console.print(table)


# --------------------------------------------------------------------------- setup


@click.command("install")
@click.option(
    "-a",
    "--action",
    "actions",
    multiple=True,
    metavar="ACTION",
    help="Only the tools of these actions (default: all configured tools).",
)
@click.option(
    "--dry-run", "dry_run", is_flag=True, help="Only show what would be installed."
)
@click.option("--allow-system", is_flag=True, help="Allow apt/dnf (needs sudo rights).")
@click.option(
    "--bootstrap-choco",
    is_flag=True,
    help="Install Chocolatey first (Windows, administrator terminal).",
)
@click.pass_context
@guarded
def setup_command(
    ctx: click.Context,
    actions: tuple[str, ...],
    dry_run: bool,
    allow_system: bool,
    bootstrap_choco: bool,
) -> None:
    """Check the configured tools and install missing or outdated ones."""
    state = _state(ctx)
    project = state.project()
    if bootstrap_choco and not dry_run:
        state.app.installer.bootstrap_choco(
            lambda line: console.print(f"  {escape(line)}")
        )
    ok = install_tools(
        state,
        project,
        list(actions) or None,
        dry_run=dry_run,
        allow_system=allow_system,
    )
    sys.exit(0 if ok else 1)


def _print_checks(checks: list[Any]) -> bool:
    icons = {"ok": "[green]✔[/]", "warning": "[yellow]![/]", "problem": "[red]✘[/]"}
    table = Table(box=None, pad_edge=False, show_header=False)
    for check in checks:
        fix = f" [dim]→ {escape(check.fix)}[/]" if check.fix else ""
        table.add_row(
            icons[check.status], escape(check.area), escape(check.detail) + fix
        )
    console.print(table)
    return not any(c.status == "problem" for c in checks)


@cli.command("doctor")
@click.pass_context
def doctor_command(ctx: click.Context) -> None:
    """Diagnose this machine and project: uv, git, configuration, tools, credentials, configs."""
    state = _state(ctx)
    project, error = None, None
    try:
        project = state.project()
    except ConfigError as exc:
        error = "invalid configuration: " + "; ".join(str(p) for p in exc.problems[:3])
    except PtkError as exc:
        error = str(exc)
    credentials = state.app.credentials(project) if project else None
    checks = state.app.doctor.run(project, error, credentials, state.app.role(project))
    sys.exit(0 if _print_checks(checks) else 1)


@cli.command("self-setup")
@click.option(
    "--tools/--no-tools",
    default=False,
    show_default=True,
    help="Also install the configured tools.",
)
@click.option(
    "--allow-system", is_flag=True, help="Allow apt/dnf for tools (needs sudo rights)."
)
@click.pass_context
@guarded
def self_setup_command(ctx: click.Context, tools: bool, allow_system: bool) -> None:
    """Get this machine ready: check uv and git, sync shared configs, install the
    pre-commit hooks, report missing credentials (and install tools with --tools)."""
    state = _state(ctx)
    project = state.project()
    checks = state.app.self_setup.run(
        project,
        state.app.credentials(project),
        install_tools=tools,
        allow_system=allow_system,
        out=lambda line: console.print(f"  [dim]{escape(line)}[/]", highlight=False),
    )
    sys.exit(0 if _print_checks(checks) else 1)


# --------------------------------------------------------------------------- configs


@cli.group("configs", cls=AccessGroup)
def configs_group() -> None:
    """Shared base configs (pre-commit, ruff, clang-format, clang-tidy, clangd) + overlays."""


def _show_config_results(items: list[Any], root: Path) -> None:
    for item in items:
        colour = {"up to date": "green", "new": "cyan"}.get(item.status, "yellow")
        rel = (
            item.path.relative_to(root) if item.path.is_relative_to(root) else item.path
        )
        console.print(
            f"[{colour}]{item.status:<11}[/] {escape(str(rel))} [dim]({item.name})[/]",
            highlight=False,
        )
        for note in item.notes:
            console.print(f"            [yellow]{escape(note)}[/]", highlight=False)


@configs_group.command("sync")
@click.argument("names", nargs=-1)
@click.option(
    "--diff", is_flag=True, help="Only show what would change (unified diff)."
)
@click.pass_context
@guarded
def configs_sync(ctx: click.Context, names: tuple[str, ...], diff: bool) -> None:
    """Write the effective config files: ptk's base merged with your overlay."""
    project = _state(ctx).project()
    service = _state(ctx).app.shared_configs
    if diff:
        changed = False
        for item in service.plan(project, list(names) or None):
            if item.status != "up to date":
                changed = True
                click.echo(item.diff(project.root), nl=False)
        if not changed:
            console.print("[green]all configs are up to date[/]")
        return
    items = service.sync(project, list(names) or None)
    if not items:
        console.print(
            "no shared configs configured (add them under 'configs:' in .main.ptk.yml)"
        )
    _show_config_results(items, project.root)


@configs_group.command("check")
@click.argument("names", nargs=-1)
@click.pass_context
@guarded
def configs_check(ctx: click.Context, names: tuple[str, ...]) -> None:
    """Fail (exit code 1) if an effective config file is missing or out of date - for CI."""
    project = _state(ctx).project()
    items = _state(ctx).app.shared_configs.plan(project, list(names) or None)
    _show_config_results(items, project.root)
    if any(item.status != "up to date" for item in items):
        console.print("run 'ptk setup configs sync' and commit the result")
        sys.exit(1)


# --------------------------------------------------------------------------- report


@cli.group("report", cls=AccessGroup)
def report_group() -> None:
    """Reports of past runs: export them again or open them in the browser."""


def _report_target(ctx: click.Context, action: str | None) -> tuple[Any, str]:
    project = _state(ctx).project()
    name = action or project.config.project.default_action
    if not name:
        raise PtkError("which action? (no ACTION given and no project.default_action)")
    if name not in project.config.actions:
        raise PtkError(f"unknown action '{name}'")
    return project, name


@report_group.command("export")
@click.argument("action", required=False)
@click.option(
    "-V", "--variant", help="Variant (default: the configured default variant)."
)
@click.option(
    "--run", "run_id", metavar="RUN_ID", help="An older run kept in the log history."
)
@click.option(
    "-f",
    "--format",
    "formats",
    multiple=True,
    type=str,
    help="Formats (default: reporting.formats). Repeatable.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, file_okay=False),
    help="Target folder (default: _reports/<variant>/<action>).",
)
@click.pass_context
@guarded
def report_export(
    ctx: click.Context,
    action: str | None,
    variant: str | None,
    run_id: str | None,
    formats: tuple[str, ...],
    output: Path | None,
) -> None:
    """Write the report of the latest (or a given) run of ACTION again."""
    project, name = _report_target(ctx, action)
    service = _state(ctx).app.reports
    summary = service.latest(project, name, variant, run_id)
    report, files = service.write(project, summary, list(formats) or None, output)
    for file in files:
        console.print(f"written {escape(str(file))}", highlight=False, soft_wrap=True)
    for problem in report.problems:
        console.print(f"[yellow]{escape(problem)}[/]")


@report_group.command("open")
@click.argument("action", required=False)
@click.option(
    "-V", "--variant", help="Variant (default: the configured default variant)."
)
@click.option(
    "--run", "run_id", metavar="RUN_ID", help="An older run kept in the log history."
)
@click.pass_context
@guarded
def report_open(
    ctx: click.Context, action: str | None, variant: str | None, run_id: str | None
) -> None:
    """Open the HTML report of the latest (or a given) run of ACTION in the browser."""
    project, name = _report_target(ctx, action)
    service = _state(ctx).app.reports
    summary = service.latest(project, name, variant, run_id)
    target = None
    if run_id:  # older runs get their own folder so the latest report stays
        target = (
            service.output_dir(project, summary.get("variant"), name)
            / "_history"
            / run_id
        )
    _report, files = service.write(project, summary, ["html"], target)
    console.print(f"report: {escape(str(files[0]))}", highlight=False, soft_wrap=True)
    if not _state(ctx).app.open_in_browser(files[0]):
        console.print("[dim]no browser available here - open the file above[/]")


# --------------------------------------------------------------------------- vscode


@cli.group("vscode", cls=AccessGroup)
def vscode_group() -> None:
    """VS Code integration."""


@vscode_group.command("tasks")
@click.option(
    "--check",
    is_flag=True,
    help="Only check that tasks.json is up to date (exit code 1 if not) - for CI.",
)
@click.option(
    "--command",
    "command",
    default="ptk",
    show_default=True,
    help='How VS Code starts ptk, e.g. "uv run ptk".',
)
@click.option(
    "--users-only",
    is_flag=True,
    help="Leave out maintainer-only actions (for a tasks.json that is committed).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Target file (default: .vscode/tasks.json in the project).",
)
@click.pass_context
@guarded
def vscode_tasks(
    ctx: click.Context, check: bool, command: str, users_only: bool, output: Path | None
) -> None:
    """Add a task for every action to .vscode/tasks.json.

    Tasks labelled [bold]ptk: ...[/] and the variant picker input are managed by ptk;
    all other tasks and inputs in the file are kept. The default action becomes the
    default build task (Ctrl+Shift+B).
    """
    state = _state(ctx)
    parent = ctx
    while parent is not None:
        if getattr(parent.command, "repository_boundary", False):
            command = f"{command} {parent.info_name}"
            break
        parent = parent.parent
    result = state.app.vscode_tasks.execute(
        state.project(),
        state.role(),
        command=command,
        users_only=users_only,
        check=check,
        path=output,
    )
    if check:
        if result.up_to_date:
            console.print(
                f"[green]{escape(str(result.path))} is up to date[/]", highlight=False
            )
            return
        console.print(
            f"[red]{escape(str(result.path))} is out of date[/] - run 'ptk setup vscode tasks'",
            highlight=False,
        )
        sys.exit(1)
    if result.written:
        console.print(
            f"updated [bold]{escape(str(result.path))}[/]: "
            f"{', '.join(result.labels) or 'no actions'}",
            highlight=False,
        )
        if result.lost_comments:
            console.print("[yellow]note: comments in the file could not be kept[/]")
    else:
        console.print(
            f"{escape(str(result.path))} is already up to date", highlight=False
        )


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
        sub = click.Context(command, info_name=name, parent=parent, obj=state_of(ctx))
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
                # generated action commands have their own section in the help page
                is_action = hasattr(child, "ptk_action")
                if child is not None and not child.hidden and not is_action:
                    visit(child, sub, [*path, child_name])

    # Collect only the selected repository, even when the real root is a VMR.
    standalone = ProjectGroup(
        commands=group.commands, params=group.params, help=group.help
    )
    visit(standalone, None, [])
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
    parent = ctx
    while parent is not None:
        if getattr(parent.command, "repository_boundary", False):
            prefix = f"ptk {parent.info_name}"
            for item in [*doc.commands, *doc.actions]:
                if item.usage == "ptk" or item.usage.startswith("ptk "):
                    item.usage = prefix + item.usage[3:]
            break
        parent = parent.parent
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


@click.command("init")
@click.argument(
    "directory", default=".", type=click.Path(path_type=Path, file_okay=False)
)
@click.option("--name", help="Project name (default: destination directory name).")
@click.option(
    "--config-dir", help="Repository-relative configuration directory (default: ptk)."
)
@click.option("--yes", "-y", is_flag=True, help="Use defaults without prompting.")
@click.option("--dry-run", is_flag=True, help="Preview files without writing them.")
@click.pass_context
@guarded
def init_command(
    ctx: click.Context,
    directory: Path,
    name: str | None,
    dry_run: bool,
    config_dir: str | None,
    yes: bool,
) -> None:
    """Create a runnable project without overwriting existing configuration."""
    state = _state(ctx)
    if state.config is not None or state.overrides:
        raise click.UsageError(
            "init uses DIRECTORY; do not combine it with --config or --set"
        )
    target = directory.resolve()
    if config_dir is None:
        config_dir = (
            click.prompt(
                "PTK configuration directory (relative to repository root)",
                default="ptk",
            )
            if not yes and sys.stdin.isatty()
            else "ptk"
        )
    result = state.app.init_project.execute(
        target, name, config_path=config_dir, dry_run=dry_run
    )
    for file, content in result.files.items():
        console.print(
            f"{'would create' if dry_run else 'created'} {target / file}", markup=False
        )
        if dry_run:
            console.print(content, markup=False, highlight=False)
    if result.kept_gitignore:
        console.print(
            "Kept existing .gitignore content and appended missing PTK ignore rules."
        )
    if not dry_run:
        console.print(
            "Next: change to the project directory, then run 'ptk setup config validate', 'ptk hello' and 'ptk build'."
        )


@click.command("migrate")
@click.argument("source", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=".main.ptk.yml",
)
@click.option("--name", help="Project name when absent in the legacy file.")
@click.option(
    "--dry-run", is_flag=True, help="Validate and print converted YAML without writing."
)
@guarded
def migrate_command(
    source: Path, output: Path, name: str | None, dry_run: bool
) -> None:
    """Convert supported legacy configuration fields; refuse ambiguous input."""
    from ...adapters.migration import convert_file

    text = convert_file(source, output, name=name, dry_run=dry_run)
    if dry_run:
        click.echo(text)
    else:
        click.echo(
            f"Created {output}. Review it, then run 'ptk setup config validate'."
        )


@click.pass_context
def _setup_dispatch(ctx: click.Context, **options: Any) -> None:
    """Group configuration, installation and credential management."""
    supplied = any(
        ctx.get_parameter_source(name) == click.core.ParameterSource.COMMANDLINE
        for name in options
    )
    if ctx.invoked_subcommand is not None:
        if supplied:
            raise click.UsageError(
                "Put installation options after 'setup install', "
                "not before a setup subcommand.",
                ctx,
            )
        return
    if supplied:
        # Compatibility: ptk setup --action A --dry-run.
        ctx.invoke(setup_command, **options)
    else:
        click.echo(ctx.get_help())


def _group_setup_commands() -> None:
    setup = AccessGroup(
        "setup",
        callback=_setup_dispatch,
        help="Configure the project, install tools and manage credentials.",
        invoke_without_command=True,
        params=list(setup_command.params),
        epilog="Use 'ptk setup install' for tool installation. "
        "Legacy 'ptk setup --action A' remains supported.",
    )
    setup.add_command(setup_command, "install")
    setup.add_command(migrate_command, "migrate")
    migrate_alias = copy.copy(migrate_command)
    migrate_alias.hidden = True
    cli.add_command(migrate_alias, "migrate")
    setup.add_command(init_command, "init")
    alias = copy.copy(init_command)
    alias.hidden = True
    cli.add_command(alias, "init")
    for old, new in (
        ("config", "config"),
        ("configs", "configs"),
        ("creds", "creds"),
        ("self-setup", "self"),
        ("doctor", "doctor"),
        ("vscode", "vscode"),
    ):
        command = cli.commands[old]
        setup.add_command(command, new)
        # Separate object: hiding the legacy alias must not hide the new command.
        alias = copy.copy(command)
        alias.hidden = True
        cli.add_command(alias, old)
    cli.add_command(setup)


_group_setup_commands()
cli.add_command(version_group)


def main() -> None:
    cli(prog_name="ptk")


if __name__ == "__main__":  # pragma: no cover
    main()
