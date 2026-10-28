"""Stable JSON inventory for the VS Code extension and other local clients."""

import json
from pathlib import Path

import rich_click as click

from ...application.use_cases.role import visible
from ...bootstrap import create_app
from ...domain.errors import ConfigError, PtkError
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
@click.option(
    "--configuration",
    is_flag=True,
    help="Include the authored configuration, source map and installed schema for local editors.",
)
def describe(ctx, as_json, configuration):
    """List accessible projects, jobs, workflows and variants without running them."""
    from ...application.use_cases.editor import describe_configuration, describe_project

    def failed_project(state, exc, entry=None, alias=None):
        loader = state.app.load_project
        entry = entry or loader.editor_main
        if entry is None:
            return None
        return {
            "alias": alias or entry.parent.name,
            "root": str(entry.parent),
            "entry_file": str(entry),
            "error": str(exc),
            "config_files": [str(file) for file in loader.editor_files],
            **(
                {
                    "configuration": describe_configuration(
                        loader.editor_tree,
                        entry.parent,
                        loader.editor_files,
                        str(exc),
                        loader.fingerprints,
                    )
                }
                if configuration
                else {}
            ),
            "diagnostics": [
                {
                    "message": problem.message,
                    "path": problem.path,
                    "file": str((entry.parent / problem.location.file).resolve())
                    if problem.location
                    else str(entry),
                    "line": problem.location.line if problem.location else 1,
                }
                for problem in exc.problems
            ]
            if isinstance(exc, ConfigError)
            else [{"message": str(exc), "file": str(entry), "line": 1}],
        }

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
        path = root / "workflows"
        if path.is_dir():
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
                project = describe_project(
                    state.project(), state.role(), configuration=configuration
                )
                group = command_ctx.command.get_command(command_ctx, alias)
                with click.Context(
                    group, info_name=alias, parent=command_ctx, obj=state
                ) as member_ctx:
                    project["commands"] = describe_commands(member_ctx)
                projects.append(project)
            except PtkError as exc:
                projects.append(failed_project(state, exc, entry, alias))
        from .workspace_commands import build_commands

        commands = describe_commands(command_ctx, build_commands(command_ctx, entries))
    else:
        try:
            project = parent.project()
            root, role = project.root, parent.role()
            item = describe_project(project, role, configuration=configuration)
            item["commands"] = describe_commands(command_ctx)
            projects.append(item)
        except PtkError as exc:
            root, role = Path.cwd(), "user"
            item = failed_project(parent, exc)
            if item:
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
