"""Read-only version discovery commands and explicit snapshot generation."""

from pathlib import Path
from uuid import uuid4

import rich_click as click
import yaml

from ...application.use_cases.variants import VariantService
from ...domain.errors import PtkError
from .access import AccessGroup
from .state import guarded, state_of


@click.group("version", cls=AccessGroup)
def version_group():
    """Discover versions, validate sources and generate snapshots (never bump/tag)."""


def discover(ctx, variant, action):
    state = state_of(ctx)
    project = state.project()
    variants = VariantService(project)
    if variants.has_variants:
        chosen = variants.resolve(variant)
        if chosen.errors:
            raise PtkError("; ".join(map(str, chosen.errors)))
        variant = chosen.name
    elif variant:
        raise PtkError("this project has no variants")
    if action and action not in project.config.actions:
        raise PtkError(f"unknown action {action!r}")
    snapshot = state.app.versions().resolve(project, variant, action)
    if not snapshot:
        raise PtkError("this project has no versioning configuration")
    return state, project, variant, snapshot


@version_group.command("show")
@click.option("--variant", "-V")
@click.option("--action", help="Include the action's explicit version dependencies.")
@click.pass_context
@guarded
def show(ctx, variant, action):
    """Show effective versions, inheritance and provenance as YAML."""
    *_, snapshot = discover(ctx, variant, action)
    click.echo(yaml.safe_dump(snapshot, sort_keys=False))


@version_group.command("check")
@click.option("--variant", "-V")
@click.option("--action")
@click.pass_context
@guarded
def check(ctx, variant, action):
    """Discover and validate versions without writing files."""
    discover(ctx, variant, action)
    click.echo("Version sources and resolved names are valid.")


@version_group.command("generate")
@click.option("--variant", "-V")
@click.option("--action")
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Snapshot destination; filename must be .gen.version.ptk.yml.",
)
@click.pass_context
@guarded
def generate(ctx, variant, action, output):
    """Write a resolved .gen.version.ptk.yml snapshot."""
    state, project, variant, snapshot = discover(ctx, variant, action)
    output = (
        output
        or project.root
        / ".ptk"
        / "versions"
        / (variant or "default")
        / uuid4().hex
        / ".gen.version.ptk.yml"
    )
    if output.name != ".gen.version.ptk.yml":
        raise PtkError("generated snapshot must be named .gen.version.ptk.yml")
    state.app.versions().write(output, snapshot)
    click.echo(str(output.resolve()))
