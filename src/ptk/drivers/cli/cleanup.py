"""Explicit repository and VMR cleanup commands."""

import rich_click as click

from ...adapters.cleanup import delete_directory, validate_directory
from ...adapters.locking import output_cleanup_lock
from ...application.use_cases.cleanup import CleanOutputs, targets
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .state import CliState, guarded, state_of


def mode(state):
    if state.clean and state.re_run:
        raise PtkError("use --clean or --re-run, not both")
    return state.clean or state.re_run


def clean_selected(prepared, *, dry_run=False):
    selected = []
    seen = set()
    for item in prepared:
        key = (item.project.root, item.plan.variant, item.plan.job)
        if key not in seen:
            selected.extend(targets(item.project, [(item.plan.variant, item.plan.job)]))
            seen.add(key)
    service = CleanOutputs(validate_directory, delete_directory)
    service.preflight(selected)
    if dry_run:
        for target in selected:
            click.echo(f"would remove {target.path}")
        return
    with output_cleanup_lock([item.project.root for item in prepared]):
        service.execute(selected, click.echo)


def clean_projects(projects, yes, dry_run):
    selected = [target for project in projects for target in targets(project)]
    service = CleanOutputs(validate_directory, delete_directory)
    service.preflight(selected)
    for target in selected:
        click.echo(f"would remove {target.path}")
    if dry_run:
        return
    if not yes:
        click.confirm("Delete these output folders for ALL variants?", abort=True)
    with output_cleanup_lock([project.root for project in projects]):
        service.execute(selected, click.echo)


@click.command("clean-all")
@click.option("--yes", "-y", is_flag=True, help="Confirm deletion without prompting.")
@click.option("--dry-run", is_flag=True, help="Show folders without deleting anything.")
@click.pass_context
@guarded
def clean_all(ctx, yes, dry_run):
    """Delete all repository output folders, for every job and variant."""
    clean_projects([state_of(ctx).project()], yes, dry_run)


@click.command("vmr-clean-all")
@click.option("--yes", "-y", is_flag=True, help="Confirm deletion without prompting.")
@click.option("--dry-run", is_flag=True, help="Show folders without deleting anything.")
@click.pass_context
@guarded
def vmr_clean_all(ctx, yes, dry_run):
    """Delete all output folders in every configured VMR member repository."""
    parent = state_of(ctx)
    entries = ctx.find_root().meta.get("vmr_repositories")
    if entries is None:
        raise PtkError("vmr-clean-all must be invoked at the VMR root")
    projects = []
    for entry in entries.values():
        state = CliState(
            create_app(host=parent.app.host, workspace=parent.app.workspace),
            config=entry,
            overrides=parent.overrides,
            ci=parent.ci,
        )
        project = state.project()
        from ...application.use_cases.role import command_allowed

        if not command_allowed(
            "clean-all", state.role(), project.config.command_audience
        ):
            raise PtkError(
                f"{project.config.repository.alias}: clean-all is maintainer-only"
            )
        projects.append(project)
    # Workspace-owned workflows also produce summaries at the VMR root.
    from pathlib import Path
    from types import SimpleNamespace

    from ...domain.config.model import LayoutSpec

    root = parent.app.workspace.root(Path.cwd())
    projects.append(
        SimpleNamespace(
            root=root,
            config=SimpleNamespace(
                layout=LayoutSpec(), reporting=SimpleNamespace(dir=None)
            ),
            files=[
                root / ".main.ptk.yml",
                root / "workflows",
                *entries.values(),
            ],
        )
    )
    clean_projects(projects, yes, dry_run)
