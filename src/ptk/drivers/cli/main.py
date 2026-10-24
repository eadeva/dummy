"""ptk command line (driver).

Thin layer: parse options, call use cases, present results. Action commands
generated from the configuration are added in a later milestone.
"""
from __future__ import annotations

import functools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rich_click as click
import yaml
from rich.console import Console
from rich.table import Table

from ... import __version__
from ...application.use_cases.project import Project
from ...bootstrap import App, create_app
from ...domain.errors import ConfigError, PtkError

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
            self._project = self.app.load_project.execute(config_file=self.config, overrides=self.overrides,
                                                          ci=self.ci)
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
                err_console.print(f"  {problem}", markup=False, highlight=False, soft_wrap=True)
            sys.exit(2)
        except PtkError as exc:
            err_console.print(f"[bold red]error:[/] {exc}", highlight=False, soft_wrap=True)
            sys.exit(2)
    return wrapper


def _state(ctx: click.Context) -> CliState:
    return ctx.find_object(CliState)


# --------------------------------------------------------------------------- root


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-c", "--config", type=click.Path(path_type=Path, dir_okay=False, exists=True),
              help="Path to main.ptk.yml (default: search upwards from the current directory).")
@click.option("-s", "--set", "overrides", multiple=True, metavar="PATH=VALUE",
              help="Override a configuration value, e.g. --set actions.build.params.jobs.default=4")
@click.option("--ci/--no-ci", default=None, help="Force CI mode on/off (default: detected).")
@click.option("-v", "--verbose", count=True, help="More output (-v, -vv).")
@click.version_option(__version__, prog_name="ptk")
@click.pass_context
def cli(ctx: click.Context, config: Path | None, overrides: tuple[str, ...], ci: bool | None, verbose: int) -> None:
    """[bold]ptk[/] - project tool kit."""
    ctx.obj = CliState(app=create_app(), config=config, overrides=overrides, ci=ci, verbose=verbose)


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
    console.print(f"[green]configuration is valid[/] ({len(project.files)} file(s), "
                  f"layers: {', '.join(project.layers)})")


@config_group.command("show")
@click.argument("path", required=False)
@click.option("--sources", is_flag=True, help="Show the file and line every value comes from.")
@click.option("--format", "fmt", type=click.Choice(["yaml", "json"]), default="yaml", show_default=True)
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
        console.print(yaml.safe_dump(result.value, sort_keys=False, allow_unicode=True).rstrip(),
                      markup=False, highlight=False)


@config_group.command("schema")
@click.option("-o", "--output", type=click.Path(path_type=Path, dir_okay=False),
              help="Write to a file (e.g. .ptk/schema.json) instead of stdout.")
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
@click.option("--names", is_flag=True, help="Print buildable variant names only (for CI matrices).")
@click.pass_context
@guarded
def variant_list(ctx: click.Context, names: bool) -> None:
    """List variants."""
    service = _state(ctx).app.variants(_state(ctx).project())
    items = service.list(include_abstract=not names)
    if names:
        click.echo("\n".join(v.name for v in items))
        return
    table = Table("variant", "aliases", "extends", "description", box=None, pad_edge=False)
    for v in items:
        label = v.name + (" [dim](abstract)[/]" if v.abstract else "") + (" [green]*[/]" if v.default else "")
        table.add_row(label, ", ".join(v.aliases) or "-", ", ".join(v.extends) or "-", v.description)
    console.print(table)


@variant_group.command("show")
@click.argument("name", required=False)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option("--all", "show_all", is_flag=True, help="Include features of inactive components.")
@click.pass_context
@guarded
def variant_show(ctx: click.Context, name: str | None, as_json: bool, show_all: bool) -> None:
    """Show the resolved values of a variant (default variant if NAME is omitted)."""
    service = _state(ctx).app.variants(_state(ctx).project())
    resolved = service.resolve(name)
    if as_json:
        console.print_json(resolved.model_dump_json())
        sys.exit(0 if resolved.ok else 1)
    console.print(f"[bold]{resolved.name}[/]" + (f" - {resolved.description}" if resolved.description else ""))
    console.print(f"inherits   : {' -> '.join(resolved.chain)}")
    console.print(f"components : {', '.join(resolved.components) or '-'}")
    table = Table("feature", "component", "value", "source", box=None, pad_edge=False)
    for f in resolved.features.values():
        if not f.active and not show_all:
            continue
        source = {"variant": f"set in {f.set_by}", "depends_on": "off (depends_on)"}.get(f.source, f.source)
        table.add_row(f.name, f.component, _value(f.value), source)
    console.print(table)
    _print_issues(resolved)
    sys.exit(0 if resolved.ok else 1)


def _print_issues(resolved) -> None:
    if not resolved.issues:
        console.print("[green]OK[/]")
    for issue in resolved.issues:
        colour = "red" if issue.severity.value == "error" else "yellow"
        console.print(f"[{colour}]{issue.severity.value}[/]: {issue.message}", highlight=False)


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


def main() -> None:
    cli(prog_name="ptk")


if __name__ == "__main__":  # pragma: no cover
    main()
