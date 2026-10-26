"""Read-only version discovery commands and explicit snapshot generation."""

from pathlib import Path
from uuid import uuid4

import rich_click as click
import yaml

from ...domain.errors import PtkError
from .access import AccessGroup
from .state import guarded, state_of


@click.group("version", cls=AccessGroup)
def version_group():
    """Discover versions, validate sources and generate snapshots (never bump/tag)."""


def discover(ctx, variant, job):
    from ...application.use_cases.variants import VariantService

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
    if job and job not in project.config.jobs:
        raise PtkError(f"unknown job {job!r}")
    snapshot = state.app.versions().resolve(project, variant, job)
    if not snapshot:
        raise PtkError("this project has no versioning configuration")
    return state, project, variant, snapshot


@version_group.command("show")
@click.option("--job", help="Include the job's explicit version dependencies.")
@click.pass_context
@guarded
def show(ctx, job):
    """Show effective versions, inheritance and provenance as YAML."""
    *_, snapshot = discover(ctx, state_of(ctx).variant, job)
    click.echo(yaml.safe_dump(snapshot, sort_keys=False))


@version_group.command("check")
@click.option("--job")
@click.pass_context
@guarded
def check(ctx, job):
    """Discover and validate versions without writing files."""
    discover(ctx, state_of(ctx).variant, job)
    click.echo("Version sources and resolved names are valid.")


@version_group.command("generate")
@click.option("--job")
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Snapshot destination; filename must be .gen.version.ptk.yml.",
)
@click.pass_context
@guarded
def generate(ctx, job, output):
    """Write a resolved .gen.version.ptk.yml snapshot."""
    state, project, variant, snapshot = discover(ctx, state_of(ctx).variant, job)
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
