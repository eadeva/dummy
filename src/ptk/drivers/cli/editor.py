"""Stable JSON inventory for the VS Code extension and other local clients."""

import json
from pathlib import Path

import rich_click as click

from ...application.use_cases.role import visible
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .state import CliState, guarded, state_of


@click.command("describe")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Versioned, machine-readable editor inventory.",
)
@click.pass_context
@guarded
def describe(ctx, as_json):
    """List accessible projects, jobs, workflows and variants without running them."""
    from ...application.use_cases.editor import describe_project

    parent = state_of(ctx)
    current = ctx
    boundary = False
    while current is not None:
        boundary |= getattr(current.command, "repository_boundary", False)
        current = current.parent
    entries = None if boundary else ctx.find_root().meta.get("vmr_repositories")
    workspace = entries is not None
    projects = []
    workflows = []
    if workspace:
        from ...adapters.workflow_files import read_workflows

        root = parent.app.workspace.root(Path.cwd())
        role = parent.app.workspace_role(root)
        path = root / "workflow.ptk.yml"
        if path.is_file():
            workflows = [
                {"name": name, "help": spec.help}
                for name, spec in read_workflows(path).workflows.items()
                if visible(spec.audience, role)
            ]
        for alias, entry in sorted(entries.items()):
            state = CliState(
                create_app(host=parent.app.host, workspace=parent.app.workspace),
                config=entry,
                ci=parent.ci,
                overrides=parent.overrides,
            )
            try:
                projects.append(describe_project(state.project(), state.role()))
            except PtkError as exc:
                projects.append(
                    {
                        "alias": alias,
                        "root": str(entry.parent),
                        "entry_file": str(entry),
                        "error": str(exc),
                    }
                )
    else:
        project = parent.project()
        root, role = project.root, parent.role()
        projects.append(describe_project(project, role))
    result = {
        "schema_version": 1,
        "ptk_version": parent.app.version,
        "mode": "workspace" if workspace else "repository",
        "root": str(root),
        "role": role,
        "ci": parent.app.host.is_ci() if parent.ci is None else parent.ci,
        "projects": projects,
        "workflows": workflows,
    }
    if as_json:
        click.echo(json.dumps(result, indent=2))
        return
    for project in projects:
        click.echo(f"{project['alias']}: {project['root']}")
        if "error" in project:
            click.echo(f"  error: {project['error']}")
            continue
        for key in ("jobs", "workflows", "variants"):
            click.echo(
                f"  {key}: {', '.join(item['name'] for item in project[key]) or '-'}"
            )
    for workflow in workflows:
        click.echo(f"workspace workflow: {workflow['name']}")
