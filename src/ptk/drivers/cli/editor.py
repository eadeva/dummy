"""Stable JSON inventory for the VS Code extension and other local clients."""

import json
from pathlib import Path

import rich_click as click

from ...application.use_cases.role import visible
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .access import allowed
from .state import CliState, guarded, state_of


def describe_commands(ctx, commands=None, path=()):
    """Read the declared Click tree without invoking callbacks or resolving defaults."""
    result = []
    if commands is None:
        commands = getattr(ctx.command, "commands", {})
    for name, command in sorted(commands.items()):
        if command.hidden or not allowed(ctx, name):
            continue
        params = []
        for param in command.params:
            if getattr(param, "hidden", False) or getattr(param, "hide_input", False):
                continue
            option = isinstance(param, click.Option)
            params.append(
                {
                    "name": param.name,
                    "kind": "option" if option else "argument",
                    "help": getattr(param, "help", None) or "",
                    "required": param.required,
                    "type": param.type.name,
                    "choices": list(param.type.choices)
                    if isinstance(param.type, click.Choice)
                    else [],
                    "nargs": param.nargs,
                    "multiple": getattr(param, "multiple", False),
                    "is_flag": getattr(param, "is_flag", False),
                    "option": next(
                        (opt for opt in param.opts if opt.startswith("--")),
                        param.opts[0],
                    )
                    if option
                    else None,
                    "secondary_option": next(iter(param.secondary_opts), None)
                    if option
                    else None,
                }
            )
        with click.Context(command, info_name=name, parent=ctx) as child:
            children = describe_commands(child, path=(*path, name))
        result.append(
            {
                "name": name,
                "path": [*path, name],
                "help": command.get_short_help_str(180),
                "runnable": not isinstance(command, click.Group)
                or command.invoke_without_command,
                "params": params,
                "children": children,
            }
        )
    return result


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
    commands = []
    command_ctx = ctx.parent
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
                project = describe_project(state.project(), state.role())
                group = command_ctx.command.get_command(command_ctx, alias)
                with click.Context(
                    group, info_name=alias, parent=command_ctx, obj=state
                ) as member_ctx:
                    project["commands"] = describe_commands(member_ctx)
                projects.append(project)
            except PtkError as exc:
                projects.append(
                    {
                        "alias": alias,
                        "root": str(entry.parent),
                        "entry_file": str(entry),
                        "error": str(exc),
                    }
                )
        from .workspace_commands import build_commands

        commands = describe_commands(command_ctx, build_commands(command_ctx, entries))
    else:
        project = parent.project()
        root, role = project.root, parent.role()
        item = describe_project(project, role)
        item["commands"] = describe_commands(command_ctx)
        projects.append(item)
    result = {
        "schema_version": 1,
        "ptk_version": parent.app.version,
        "mode": "workspace" if workspace else "repository",
        "root": str(root),
        "role": role,
        "ci": parent.app.host.is_ci() if parent.ci is None else parent.ci,
        "projects": projects,
        "workflows": workflows,
        "commands": commands,
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
