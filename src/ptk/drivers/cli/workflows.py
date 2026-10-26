"""Workflow CLI: resolve repository owners, preflight calls, then orchestrate."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import rich_click as click
import yaml
from rich.markup import escape

from ...adapters.locking import file_lock
from ...adapters.workflow_files import (
    read_workflows,
    snapshot_logs,
    write_workflow_report,
)
from ...application.use_cases.role import visible
from ...application.use_cases.run import Cancelled, RunRequest, layout_of
from ...application.use_cases.workflow import CallOutcome, PrepareWorkflow, RunWorkflow
from ...bootstrap import create_app
from ...domain.errors import PtkError
from ...domain.execution.model import Status
from ...domain.reporting.summary import run_summary
from . import console as present
from .access import AccessGroup
from .actions import write_reports
from .state import CliState, console, err_console, guarded, state_of


def catalog(ctx):
    parent = state_of(ctx)
    root_ctx = ctx.find_root()
    current = ctx
    boundary = False
    while current is not None:
        boundary |= getattr(current.command, "repository_boundary", False)
        current = current.parent
    entries = root_ctx.meta.get("vmr_repositories") if not boundary else None
    workspace_mode = entries is not None
    project = None if workspace_mode else parent.project()
    discovery = parent.app.workspace
    workspace = discovery.root(Path.cwd() if workspace_mode else project.root)
    if entries is None:
        entries = dict(discovery.repositories(workspace)) if workspace else {}
    if project is not None:
        entries = {**entries, project.config.repository.alias: project.main_file}
    owners = {}
    available = {}
    if workspace_mode:
        document = workspace / "workflow.ptk.yml"
        if document.is_file():
            for name, spec in read_workflows(document).workflows.items():
                available[name] = (None, spec, workspace)
        for alias, entry in entries.items():
            owner = CliState(
                create_app(host=parent.app.host, workspace=discovery),
                config=entry,
                overrides=parent.overrides,
                ci=parent.ci,
                verbose=parent.verbose,
            )
            owners[alias] = owner
            for name, spec in owner.project().config.workflows.items():
                available[f"{alias}/{name}"] = (alias, spec, entry.parent)
    else:
        alias = project.config.repository.alias
        owners[alias] = parent
        for name, spec in project.config.workflows.items():
            available[name] = (alias, spec, project.root)
    return parent, entries, owners, available


def can_view(parent, owners, owner, spec):
    state = owners[owner] if owner else parent
    role = state.role() if owner else parent.app.role(None)
    if (
        owner
        and state.project().config.command_audience.get("workflow") == "maintainer"
        and role != "maintainer"
    ):
        return False
    return visible(spec.audience, role)


def select(ctx, name):
    parent, entries, owners, available = catalog(ctx)
    if name not in available:
        raise PtkError(f"unknown workflow {name!r}; use 'ptk workflow list'")
    owner, spec, root = available[name]
    if not can_view(parent, owners, owner, spec):
        raise PtkError(f"workflow {name!r} is maintainer-only")
    return parent, entries, owner, spec, root


@click.group("workflow", cls=AccessGroup)
def workflow_group():
    """List, inspect and run sequential/parallel groups of repository actions."""


@workflow_group.command("list")
@click.pass_context
@guarded
def list_workflows(ctx):
    parent, _, owners, available = catalog(ctx)
    for name, (owner, spec, _) in sorted(available.items()):
        if can_view(parent, owners, owner, spec):
            click.echo(f"{name}: {spec.help}")
    if not available:
        click.echo("no workflows configured")


def authored(spec):
    data = spec.model_dump(exclude_defaults=True)

    def steps(nodes):
        return [
            {
                node.name: {
                    k: (steps(node.steps) if k == "steps" else v)
                    for k, v in node.model_dump(exclude_defaults=True).items()
                    if k != "name"
                }
            }
            for node in nodes
        ]

    data["steps"] = steps(spec.steps)
    return data


@workflow_group.command("show")
@click.argument("name")
@click.pass_context
@guarded
def show_workflow(ctx, name):
    _, _, _, spec, _ = select(ctx, name)
    click.echo(yaml.safe_dump({"workflows": {name: authored(spec)}}, sort_keys=False))


def execute_workflow(ctx, name, *, dry_run=False):
    parent, entries, owner, spec, root = select(ctx, name)
    is_ci = parent.app.host.is_ci() if parent.ci is None else parent.ci
    if is_ci and not dry_run:
        raise PtkError(
            "workflows run locally only; CX/CI execution uses individual actions (GitHub template generation is planned separately)"
        )
    bindings = {}

    def prepare(node, path):
        alias = node.repo or owner
        if alias is None:
            raise PtkError("workspace workflow calls require repo: ALIAS")
        if alias not in entries:
            raise PtkError(
                f"repository {alias!r} is not a configured member of this workspace"
            )
        state = CliState(
            create_app(host=parent.app.host, workspace=parent.app.workspace),
            config=entries[alias],
            overrides=parent.overrides,
            ci=parent.ci,
            verbose=parent.verbose,
        )
        project = state.project()
        action = project.config.actions.get(node.action)
        if action is not None and any(
            name in action.params and action.params[name].type == "secret"
            for name in node.params
        ):
            raise PtkError(
                "secret parameters must not be stored in workflow configuration; use action credentials"
            )
        request = RunRequest(
            action=node.action,
            variant=node.variant,
            params=node.params,
            dry_run=dry_run,
            role=state.role(),
        )
        prepared = state.app.prepare_run(project).execute(project, request)
        bindings[path] = state
        return alias, prepared

    plan = PrepareWorkflow().execute(name, spec, prepare)
    for node in plan.walk():
        indent = "  " * (len(node.path) - 1)
        if node.prepared is None:
            click.echo(
                f"{indent}{node.spec.name}: {'parallel' if node.spec.parallel else 'sequential'}"
            )
        else:
            p = node.prepared.plan
            click.echo(
                f"{indent}{node.spec.name}: {node.repo}/{p.action} [{p.variant or 'default'}]"
            )
    if dry_run:
        click.echo("workflow preview; no actions executed")
        return
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    report_root = root / "_reports"
    if owner is not None:
        owner_project = create_app(host=parent.app.host).load_project.execute(
            config_file=entries[owner], overrides=parent.overrides, ci=parent.ci
        )
        layout = layout_of(owner_project)
        report_root = (
            root / owner_project.config.reporting.dir
            if owner_project.config.reporting.dir
            else layout.root / layout.reports
        )
    target = report_root / "workflows" / name.split("/")[-1] / run_id

    def run(node, cancel):
        state, prepared = bindings[node.path], node.prepared
        p = prepared.plan
        lock = (
            prepared.project.root
            / ".ptk"
            / "locks"
            / (p.variant or "default")
            / (p.action + ".lock")
        )
        with file_lock(lock):
            console.print(
                f"[bold]{escape('/'.join(node.path))}: {escape(node.repo)}/{escape(p.action)}[/]"
            )
            runner = state.app.run_action(prepared.project)
            result = runner.execute(
                prepared,
                [present.ConsoleObserver(console), *state.app.log_observers(prepared)],
                cancel,
            )
            write_reports(state, prepared.project, p, result)
            files = []
            try:
                child_target = target / "actions" / Path(*node.path)
                summary = snapshot_logs(run_summary(p, result), child_target)
                _, files = state.app.reports.write(
                    prepared.project, summary, ["json", "html"], child_target
                )
            except (PtkError, OSError, ValueError) as exc:
                err_console.print(
                    f"[yellow]workflow child report not written: {escape(str(exc))}[/]"
                )
            return CallOutcome(result.status, [str(f) for f in files], p.run_id)

    cancel = Cancelled()
    holder = {}

    def work():
        try:
            holder["result"] = RunWorkflow().execute(plan, run, cancel)
        except BaseException as exc:  # noqa: BLE001 - propagate in the main thread
            holder["error"] = exc

    worker = threading.Thread(target=work, name="ptk-workflow")
    worker.start()
    try:
        while worker.is_alive():
            worker.join(0.2)
    except KeyboardInterrupt:
        cancel.set()
        worker.join()
    if "error" in holder:
        raise holder["error"]
    result = holder["result"]
    console.print(
        f"Workflow {escape(name)}: {result.status.value} ({result.duration:.1f}s)"
    )
    try:
        path = write_workflow_report(result, target)
        console.print(f"report: {escape(str(path))}", highlight=False)
    except OSError as exc:
        err_console.print(f"[yellow]workflow report not written: {escape(str(exc))}[/]")
    raise click.exceptions.Exit(
        130
        if result.status == Status.CANCELLED
        else 1
        if result.status == Status.FAILED
        else 0
    )


@workflow_group.command("run")
@click.argument("name")
@click.pass_context
@guarded
def run_workflow(ctx, name):
    execute_workflow(ctx, name)


@workflow_group.command("dry-run")
@click.argument("name")
@click.pass_context
@guarded
def preview_workflow(ctx, name):
    execute_workflow(ctx, name, dry_run=True)


def workspace_vscode_group(root_ctx, entries):
    from .workspace_commands import visit

    @click.group("vscode", invoke_without_command=True)
    @click.pass_context
    @guarded
    def group(ctx):
        """Install member tasks/skills and workspace workflow tasks."""
        if ctx.invoked_subcommand is None:
            visit(root_ctx, [(alias, ["setup", "vscode"]) for alias in sorted(entries)])
            write_tasks(ctx, False, "ptk", False, None)

    def write_tasks(ctx, check, command, users_only, output):
        parent, _, owners, available = catalog(ctx)
        workflows = []
        for name, (owner, spec, _) in sorted(available.items()):
            if not can_view(parent, owners, owner, spec):
                continue
            if users_only and (
                spec.audience != "all"
                or owner
                and owners[owner].project().config.command_audience.get("workflow")
                == "maintainer"
            ):
                continue
            workflows.append((name, spec.help))
        root = parent.app.workspace.root(Path.cwd())
        result = parent.app.vscode_tasks.workflows(
            workflows, root=root, command=command, path=output, check=check
        )
        click.echo(
            f"{result.path}: {'up to date' if result.up_to_date else 'out of date' if check else 'updated'}"
        )
        if check and not result.up_to_date:
            raise click.exceptions.Exit(1)

    @group.command("tasks")
    @click.option("--check", is_flag=True)
    @click.option("--command", default="ptk")
    @click.option("--users-only", is_flag=True)
    @click.option("-o", "--output", type=click.Path(path_type=Path))
    @click.pass_context
    @guarded
    def tasks(ctx, check, command, users_only, output):
        """Generate workspace tasks for local and repository-qualified workflows."""
        write_tasks(ctx, check, command, users_only, output)

    @group.command("skills")
    @click.option("--check", is_flag=True)
    @guarded
    def skills(check):
        """Install offline authoring skills in each configured repository."""
        args = ["setup", "vscode", "skills", *(["--check"] if check else [])]
        visit(root_ctx, [(alias, args) for alias in sorted(entries)])

    return group
