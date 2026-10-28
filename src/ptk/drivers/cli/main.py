"""ptk command line (driver).

Thin layer: parse options, call use cases, present results. The configured
jobs are generated commands (see :mod:`.jobs`); ``ptk run JOB`` is
the generic form and ``ptk dry-run JOB`` previews either.
"""

from __future__ import annotations

import copy
import json
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rich_click as click
import yaml
from rich.markup import escape
from rich.table import Table

from ... import __version__
from ...domain.errors import ConfigError, PtkError, RunNotFoundError
from .access import AccessGroup, MaintainerOption, can_switch_ci, require
from .artifacts import artifacts_group
from .editor import describe
from .hooks import pre_commit_group
from .jobs import (
    ProjectGroup,
    build_request,
    common_options,
    execute,
    install_tools,
    pairs,
)
from .report_links import print_report
from .state import console, err_console, guarded, state_of
from .versioning import version_group
from .workflows import workflow_group
from .workspace import WorkspaceGroup
from .workspace_commands import RESERVED as WORKSPACE_COMMANDS

if TYPE_CHECKING:
    from ...application.use_cases.help import HelpCommand
    from ...application.use_cases.init import InitResult

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
    "-C",
    "--config",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    is_eager=True,  # known before --help lists the project's jobs
    help="Path to .main.ptk.yml (default: search upwards from the current directory).",
)
@click.option(
    "-s",
    "--set",
    "overrides",
    multiple=True,
    is_eager=True,
    metavar="PATH=VALUE",
    help="Override a configuration value, e.g. --set jobs.build.params.jobs.default=4",
)
@click.option(
    "--ci/--no-ci",
    cls=MaintainerOption,
    default=None,
    is_eager=True,
    help="Maintainers only: force CI mode on/off (default: detected).",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="More ptk messages: -v debug, -vv trace (default: logging.level).",
)
@click.option(
    "-V",
    "--variant",
    help="Variant name/alias (comma-separated for jobs). Used by jobs, variant show, versions, reports and artifact destinations. Workflows map the owner variant to repository variants. Ignored by setup, config, pre-commit and help.",
)
@click.option(
    "--clean",
    "-c",
    is_flag=True,
    help="Delete selected job/variant output folders and stop (jobs/workflows only).",
)
@click.option(
    "--re-run",
    "-rr",
    is_flag=True,
    help="Delete selected job/variant output folders, then run (jobs/workflows only).",
)
@click.version_option(__version__, prog_name="ptk")
@click.pass_context
@guarded
def cli(
    ctx: click.Context,
    config: Path | None,
    overrides: tuple[str, ...],
    ci: bool | None,
    verbose: int,
    variant: str | None,
    clean: bool = False,
    re_run: bool = False,
) -> None:
    """[bold]ptk[/] - project tool kit.

    The project's jobs are commands too ([bold]ptk build --help[/]). Without a
    command, ptk runs the default job ([italic]project.default_job[/]).
    """
    state = state_of(ctx)
    entries = ctx.find_root().meta.get("vmr_repositories") or {}
    if (
        state.ci is not None
        and (
            getattr(ctx.command, "repository_boundary", False)
            or ctx.invoked_subcommand not in entries
        )
        and not can_switch_ci(ctx)
    ):
        raise PtkError("--ci/--no-ci is a maintainer-only option")
    from .cleanup import mode

    if mode(state) and ctx.invoked_subcommand is not None:
        name = ctx.invoked_subcommand
        if name in ctx.command.commands and name not in {"run", "dry-run", "workflow"}:
            raise PtkError("--clean and --re-run apply only to jobs and workflows")
    if ctx.invoked_subcommand is not None:
        return
    if (
        isinstance(ctx.command, WorkspaceGroup)
        and ctx.command._repositories(ctx) is not None
    ):
        click.echo(ctx.get_help())
        return
    project = state.try_project()  # outside a project / broken config: show the help
    default = project.config.project.default_job if project else None
    if default is None:
        click.echo(ctx.get_help())
        return
    err_console.print(
        f"[dim]running the default job '{escape(default)}' "
        "(project.default_job) - 'ptk --help' lists all commands[/]",
        highlight=False,
    )
    guarded(execute)(ctx, guarded(build_request)(ctx, None))


from .cleanup import clean_all

cli.add_command(clean_all)
cli.add_command(workflow_group)
cli.add_command(describe)
cli.add_command(pre_commit_group)


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
    """Show the merged configuration (or the value at PATH, e.g. jobs.build)."""
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
    """Inspect available variants and their configuration."""


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
    resolved = service.resolve(name or _state(ctx).variant)
    if as_json:
        console.print_json(resolved.model_dump_json())
        sys.exit(0 if resolved.ok else 1)
    console.print(
        f"[bold]{resolved.name}[/]"
        + (f" - {resolved.description}" if resolved.description else "")
    )
    console.print(f"inherits   : {' -> '.join(resolved.chain)}")
    if resolved.repo_variants:
        mappings = Table("repository", "variant", box=None, pad_edge=False)
        for alias, selected in resolved.repo_variants.items():
            mappings.add_row(alias, selected)
        console.print(mappings)
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
@click.argument("job", required=False)
@click.option(
    "-p",
    "--param",
    "params",
    multiple=True,
    metavar="NAME=VALUE",
    help="Set a job parameter (unset ones use their configured default).",
)
@click.pass_context
@guarded
def run_command(
    ctx: click.Context, job: str | None, params: tuple[str, ...], **options: Any
) -> None:
    """Run JOB by name - the generic form for scripts and CI.

    Same as [bold]ptk JOB[/], but parameters are given as [bold]-p NAME=VALUE[/].
    JOB defaults to [italic]project.default_job[/]. Arguments after [bold]--[/] go
    to the step with [italic]passthrough: true[/].

    Exit code: 0 passed, 1 failed, 2 usage/configuration error, 130 cancelled.
    """
    quiet = options.pop("quiet", False)
    setup = options.pop("setup", False)
    extra = options.pop("extra", ())
    if job is not None and job.startswith("-"):
        # "ptk run -- -k x": click put the first pass-through word into JOB
        extra, job = (job, *extra), None
    request = build_request(
        ctx, job, params=pairs(params, "--param"), extra=extra, **options
    )
    execute(ctx, request, quiet=quiet, setup=setup)


# the same options as the generated job commands (incl. the trailing [-- ARGS])
run_command.params.extend(common_options(dry_run=False))


@cli.group("dry-run", cls=ProjectGroup, dry_run=True, invoke_without_command=True)
@click.pass_context
@guarded
def dry_run_group(ctx: click.Context, **options: Any) -> None:
    """Show what a job would do, without running anything.

    [bold]ptk dry-run JOB [OPTIONS][/] takes exactly the options of
    [bold]ptk JOB[/] and prints the steps with conditions evaluated, the final
    command of every step, Python runtimes, the step environment (secrets masked)
    and where every parameter value comes from. Without JOB: the default job.
    """
    if ctx.invoked_subcommand is None:
        show_env = options.pop("show_env", False)
        options.pop("extra", None)
        execute(
            ctx, build_request(ctx, None, dry_run=True, **options), show_env=show_env
        )


# without JOB, "ptk -V x dry-run" previews the default job with these options
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
    "--job",
    "jobs",
    multiple=True,
    metavar="JOB",
    help="Only the tools of these jobs (default: all configured tools).",
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
    jobs: tuple[str, ...],
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
        list(jobs) or None,
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


def _report_target(ctx: click.Context, job: str | None) -> tuple[Any, str]:
    project = _state(ctx).project()
    name = job or project.config.project.default_job
    if not name:
        raise PtkError("which job? (no JOB given and no project.default_job)")
    if name not in project.config.jobs:
        raise PtkError(f"unknown job '{name}'")
    return project, name


@report_group.command("export")
@click.argument("job", required=False)
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
    help="Target folder (default: _reports/<variant>/<job>).",
)
@click.pass_context
@guarded
def report_export(
    ctx: click.Context,
    job: str | None,
    run_id: str | None,
    formats: tuple[str, ...],
    output: Path | None,
) -> None:
    """Write the report of the latest (or a given) run of JOB again."""
    project, name = _report_target(ctx, job)
    service = _state(ctx).app.reports
    summary = service.latest(project, name, _state(ctx).variant, run_id)
    report, files = service.write(project, summary, list(formats) or None, output)
    for file in files:
        console.print(f"written {escape(str(file))}", highlight=False, soft_wrap=True)
    for problem in report.problems:
        console.print(f"[yellow]{escape(problem)}[/]")


@report_group.command("open")
@click.argument("job", required=False)
@click.option(
    "--if-exists", is_flag=True, help="Print an informational message if no run exists."
)
@click.option(
    "--run", "run_id", metavar="RUN_ID", help="An older run kept in the log history."
)
@click.pass_context
@guarded
def report_open(
    ctx: click.Context, job: str | None, run_id: str | None, if_exists: bool = False
) -> None:
    """Open the HTML report of the latest (or a given) run of JOB in the browser."""
    project, name = _report_target(ctx, job)
    service = _state(ctx).app.reports
    try:
        summary = service.latest(project, name, _state(ctx).variant, run_id)
    except RunNotFoundError:
        if not if_exists:
            raise
        detail = (
            f"saved run {run_id!r} is unavailable"
            if run_id
            else "the job hasn't run yet for this variant, or its saved run was removed"
        )
        console.print(
            f"[cyan]Info:[/] No report for job {escape(name)!r}: {escape(detail)}.",
            highlight=False,
            soft_wrap=True,
        )
        return
    target = None
    if run_id:  # older runs get their own folder so the latest report stays
        target = (
            service.output_dir(project, summary.get("variant"), name)
            / "_history"
            / run_id
        )
    _report, files = service.write(project, summary, ["html"], target)
    print_report(files[0])
    if not _state(ctx).app.open_in_browser(files[0]):
        console.print("[dim]no browser available here - open the file above[/]")


# --------------------------------------------------------------------------- vscode


@cli.group("vscode", cls=AccessGroup, invoke_without_command=True)
@click.pass_context
@guarded
def vscode_group(ctx: click.Context) -> None:
    """Set up tasks and offline project skills; subcommands update either part."""
    if ctx.invoked_subcommand is None:
        # Preflight skills before changing tasks if managed files conflict.
        _state(ctx).app.setup_authoring.execute(_state(ctx).project().root, check=True)
        ctx.invoke(
            vscode_tasks, check=False, command="ptk", users_only=False, output=None
        )
        ctx.invoke(vscode_skills, check=False)


@vscode_group.command("skills")
@click.option(
    "--check",
    is_flag=True,
    help="Check installed skills/docs without writing; exit 1 if outdated.",
)
@click.pass_context
@guarded
def vscode_skills(ctx: click.Context, check: bool) -> None:
    """Install version-matched skills under .github/skills and docs under .github/ptk."""
    state = _state(ctx)
    result = state.app.setup_authoring.execute(state.project().root, check=check)
    if check:
        console.print(
            "PTK skills and docs are "
            + ("out of date" if result.paths else "up to date")
        )
        if result.paths:
            ctx.exit(1)
    else:
        console.print(
            f"PTK skills and docs: {result.skill_count} skills, {len(result.paths)} files updated."
        )


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
    help="Leave out maintainer-only jobs (for a tasks.json that is committed).",
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
    """Add a task for every job to .vscode/tasks.json.

    Tasks labelled [bold]ptk: ...[/] and the variant picker input are managed by ptk;
    all other tasks and inputs in the file are kept. The default job becomes the
    default build task (Ctrl+Shift+B).
    """
    state = _state(ctx)
    task_cwd = None
    repository_alias = None
    parent = ctx
    while parent is not None:
        if getattr(parent.command, "repository_boundary", False):
            repository_alias = parent.info_name
            task_cwd = state.app.workspace.root(state.project().root)
            break
        parent = parent.parent
    result = state.app.vscode_tasks.execute(
        state.project(),
        state.role(),
        command=command,
        users_only=users_only,
        check=check,
        path=output,
        cwd=task_cwd,
        repository_alias=repository_alias,
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
            f"{', '.join(result.labels) or 'no jobs'}",
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
    from ...application.use_cases.help import HelpCommand, HelpOption

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
                # generated job commands have their own section in the help page
                is_job = hasattr(child, "ptk_job")
                if child is not None and not child.hidden and not is_job:
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
    """Open the full help as a web page: every job with its parameters and steps, variants, credentials,
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
            for item in [*doc.commands, *doc.jobs]:
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
@click.option(
    "--name", help="Single-project name (default: destination directory name)."
)
@click.option(
    "--config-dir",
    help="Required configuration folder, relative to each repository root; prompted on a terminal.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Do not prompt; supply --config-dir when initializing.",
)
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
    """Initialize unconfigured VMR members, or create one project at DIRECTORY."""
    state = _state(ctx)
    if state.config is not None or state.overrides:
        raise click.UsageError(
            "init uses DIRECTORY; do not combine it with --config or --set"
        )
    target = directory.resolve()
    workspace = None
    if ctx.get_parameter_source("directory") != click.core.ParameterSource.COMMANDLINE:
        # A broken parent config must not prevent creating a new child project.
        # An existing entry in the target itself remains protected by preflight.
        with suppress(ConfigError):
            workspace = state.app.workspace.root(target)
    members = state.app.workspace.initialization_members(workspace) if workspace else []
    if workspace and name is not None:
        raise click.UsageError(
            "--name requires an explicit DIRECTORY when initializing in a VMR"
        )
    pending = any(member.skip_reason is None for member in members)
    if config_dir is None and (workspace is None or pending):
        if yes or not sys.stdin.isatty():
            raise click.UsageError(
                "Supply --config-dir PATH; the configuration folder is required "
                "and is relative to each repository root."
            )
        config_dir = click.prompt(
            "PTK configuration directory (relative to each repository root)"
        )
    if workspace is not None:
        results = (
            state.app.init_project.execute_workspace(
                workspace,
                members,
                config_path=config_dir,
                dry_run=dry_run,
                reserved=WORKSPACE_COMMANDS | {"init"},
            )
            if pending
            else {}
        )
        for member in members:
            label = member.root.relative_to(workspace).as_posix()
            if member.skip_reason:
                console.print(f"[{label}] skipped: {member.skip_reason}", markup=False)
            else:
                console.print(f"[{label}]", markup=False)
                _show_init_result(member.root, results[member.root])
        console.print(
            f"{'Would initialize' if dry_run else 'Initialized'} {len(results)} repositories; "
            f"skipped {len(members) - len(results)}."
        )
        if not dry_run and results:
            console.print(
                "Next: run 'ptk repos', then 'ptk ALIAS setup config validate' and 'ptk ALIAS hello'."
            )
        return
    result = state.app.init_project.execute(
        target, name, config_path=config_dir, dry_run=dry_run
    )
    _show_init_result(target, result)
    if not dry_run:
        console.print(
            "Next: change to the project directory, then run 'ptk setup config validate', 'ptk hello' and 'ptk build'."
        )


def _show_init_result(target: Path, result: InitResult) -> None:
    for file, content in result.files.items():
        console.print(
            f"{'would create' if result.dry_run else 'created'} {target / file}",
            markup=False,
        )
        if result.dry_run:
            console.print(content, markup=False, highlight=False)
    if result.kept_gitignore:
        console.print(
            "Would keep existing .gitignore content and append missing PTK ignore rules."
            if result.dry_run
            else "Kept existing .gitignore content and appended missing PTK ignore rules."
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
        # Compatibility: ptk setup --job A --dry-run.
        require(ctx, "install")
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
        "Legacy 'ptk setup --job A' remains supported.",
    )
    setup.add_command(setup_command, "install")
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
cli.add_command(artifacts_group)


def main() -> None:
    # Redirected Windows streams may use cp1252. Preserve the selected encoding,
    # but never let a status symbol or user output abort an otherwise valid run.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
    cli(prog_name="ptk")


if __name__ == "__main__":  # pragma: no cover
    main()
