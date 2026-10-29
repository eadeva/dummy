"""Workflow CLI: resolve repository owners, preflight calls, then orchestrate."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import rich_click as click
import yaml
from rich.markup import escape

from ...adapters.workflow_files import (
    read_workflows,
    snapshot_logs,
    write_workflow_report,
)
from ...application.use_cases.role import command_allowed, visible
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .access import AccessGroup, denied_command, in_maintainer
from .completion import workflows as complete_workflows
from .jobs import write_reports
from .report_links import print_report
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
        document = workspace / "workflows"
        if document.is_dir():
            for name, spec in read_workflows(document).workflows.items():
                available[name] = (None, spec, workspace)
        for alias, entry in entries.items():
            owner = CliState(
                create_app(host=parent.app.host, workspace=discovery),
                config=entry,
                overrides=parent.overrides,
                ci=parent.ci,
                verbose=parent.verbose,
                completion=parent.completion,
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
    role = (
        state.role()
        if owner
        else parent.app.workspace_role(parent.app.workspace.root(Path.cwd()))
    )
    if (
        owner
        and state.project().config.command_audience.get("workflow") == "maintainer"
        and role != "maintainer"
    ):
        return False
    return visible(spec.audience, role)


def matches_namespace(ctx, owners, owner, spec):
    audience = spec.audience
    if (
        owner
        and owners[owner].project().config.command_audience.get("workflow")
        == "maintainer"
    ):
        audience = "maintainer"
    return (audience == "maintainer") == in_maintainer(ctx)


def select(ctx, name, *, report=False):
    parent, entries, owners, available = catalog(ctx)
    if name not in available:
        raise PtkError(f"unknown workflow {name!r}; use 'ptk workflow list'")
    owner, spec, root = available[name]
    if not can_view(parent, owners, owner, spec):
        raise PtkError(f"workflow {name!r} is maintainer-only")
    if not report and not matches_namespace(ctx, owners, owner, spec):
        prefix = "maintainer " if not in_maintainer(ctx) else ""
        raise PtkError(
            f"workflow {name!r} belongs under 'ptk {prefix}workflow run {name}'"
        )
    return parent, entries, owner, spec, root


@click.group("workflow", cls=AccessGroup)
@click.pass_context
@guarded
def workflow_group(ctx):
    """List, inspect and run sequential/parallel groups of repository jobs."""
    from .cleanup import mode

    if mode(state_of(ctx)) and ctx.invoked_subcommand != "run":
        raise PtkError("--clean and --re-run require workflow run")


@workflow_group.command("list")
@click.pass_context
@guarded
def list_workflows(ctx):
    parent, _, owners, available = catalog(ctx)
    for name, (owner, spec, _) in sorted(available.items()):
        if can_view(parent, owners, owner, spec) and matches_namespace(
            ctx, owners, owner, spec
        ):
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
@click.argument("name", shell_complete=complete_workflows)
@click.pass_context
@guarded
def show_workflow(ctx, name):
    _, _, _, spec, _ = select(ctx, name)
    click.echo(yaml.safe_dump({"workflows": {name: authored(spec)}}, sort_keys=False))


def report_directory(root, name, project=None):
    """Use the same report location for workflow execution and explicit opening."""
    from ...application.use_cases.run import layout_of

    report_root = root / "_reports"
    if project is not None:
        layout = layout_of(project)
        report_root = layout.root / layout.reports
    return report_root / "workflows" / name.split("/")[-1]


def open_workflow_report(ctx, name, if_exists=False):
    """Open the latest saved aggregate HTML report of a workflow."""
    parent, entries, owner, _, root = select(ctx, name, report=True)
    project = None
    if owner is not None:
        project = create_app(host=parent.app.host).load_project.execute(
            config_file=entries[owner], overrides=parent.overrides, ci=parent.ci
        )
    folder = report_directory(root, name, project)
    reports = [path for path in folder.glob("*/workflow.html") if path.is_file()]
    if not reports:
        if not if_exists:
            raise PtkError(f"no report for workflow {name!r} - run the workflow first")
        console.print(
            f"[cyan]Info:[/] No report for workflow {escape(name)!r}: "
            "the workflow hasn't run yet, or its report was removed.",
            highlight=False,
            soft_wrap=True,
        )
        return
    latest = max(reports, key=lambda path: (path.stat().st_mtime_ns, path.parent.name))
    print_report(latest)
    if not parent.app.open_in_browser(latest):
        console.print("[dim]no browser available here - open the file above[/]")


def execute_workflow(ctx, name, *, dry_run=False):
    from ...adapters.locking import job_lock
    from ...application.use_cases.run import Cancelled, RunRequest
    from ...application.use_cases.workflow import (
        CallOutcome,
        PrepareWorkflow,
        RunWorkflow,
    )
    from ...domain.execution.model import Status
    from ...domain.reporting.summary import run_summary
    from . import console as present

    parent, entries, owner, spec, root = select(ctx, name)
    is_ci = parent.app.host.is_ci() if parent.ci is None else parent.ci
    if is_ci and not dry_run:
        raise PtkError(
            "workflows run locally only; CX/CI execution uses individual jobs (GitHub template generation is planned separately)"
        )
    from ...application.use_cases.workflow_variants import WorkflowVariants
    from .cleanup import clean_selected, mode

    cleaning = mode(parent)
    owner_project = None
    if owner is not None:
        owner_project = create_app(host=parent.app.host).load_project.execute(
            config_file=entries[owner], overrides=parent.overrides, ci=parent.ci
        )
    variants = WorkflowVariants(owner_project, parent.variant)
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
            create_app(
                host=parent.app.host,
                workspace=parent.app.workspace,
                started_at=parent.app.started_at,
            ),
            config=entries[alias],
            overrides=parent.overrides,
            ci=parent.ci,
            verbose=parent.verbose,
        )
        project = state.project()
        job = project.config.jobs.get(node.job)
        if job is not None and any(
            name in job.params and job.params[name].type == "secret"
            for name in node.params
        ):
            raise PtkError(
                "secret parameters must not be stored in workflow configuration; use job credentials"
            )
        request = RunRequest(
            job=node.job,
            variant=variants.for_project(alias, project),
            params=node.params,
            dry_run=dry_run,
            role=state.role(),
        )
        if parent.clean:
            from ...application.use_cases.cleanup import prepare_cleanup

            prepared = prepare_cleanup(
                project, request.job, request.variant, request.role
            )
        else:
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
                f"{indent}{node.spec.name}: {node.repo}/{p.job} [{p.variant or 'default'}]"
            )
    if cleaning:
        clean_selected(
            [node.prepared for node in plan.walk() if node.prepared is not None],
            dry_run=dry_run,
        )
        if parent.clean:
            return
    if dry_run:
        click.echo("workflow dry-run; no jobs executed")
        return
    # Install once per participating repository, before any parallel job starts.
    checked_repositories = set()
    for node in plan.walk():
        if node.prepared is not None:
            project = node.prepared.project
            if project.root not in checked_repositories:
                bindings[node.path].app.hooks.execute(project, click.echo)
                checked_repositories.add(project.root)
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    target = report_directory(root, name, owner_project) / run_id
    child_openings = {}

    def run(node, cancel):
        state, prepared = bindings[node.path], node.prepared
        p = prepared.plan
        with job_lock(prepared.project.root, p.variant, p.job):
            console.print(
                f"[bold]{escape('/'.join(node.path))}: {escape(node.repo)}/{escape(p.job)}[/]"
            )
            runner = state.app.run_job(prepared.project)
            result = runner.execute(
                prepared,
                [present.ConsoleObserver(console), *state.app.log_observers(prepared)],
                cancel,
            )
            opening = write_reports(
                state, prepared.project, p, result, open_browser=False
            )
            files = []
            report_errors = False
            try:
                child_target = target / "jobs" / Path(*node.path)
                summary = snapshot_logs(run_summary(p, result), child_target)
                report, files = state.app.reports.write(
                    prepared.project, summary, ["json", "html"], child_target
                )
                report_errors = report.has_errors
                if opening is not None:
                    opening = next(
                        (file for file in files if file.suffix == ".html"), opening
                    )
            except (PtkError, OSError, ValueError) as exc:
                report_errors = True
                err_console.print(
                    f"[yellow]workflow child report not written: {escape(str(exc))}[/]"
                )
            if opening is not None:
                child_openings[node.path] = (state.app, opening)
            return CallOutcome(
                result.status, [str(f) for f in files], p.run_id, report_errors
            )

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
    open_summary = False
    try:
        path = write_workflow_report(result, target)
        print_report(path)
    except OSError as exc:
        err_console.print(f"[yellow]workflow report not written: {escape(str(exc))}[/]")
    else:
        if not is_ci and (
            spec.open_report == "always"
            or spec.open_report == "on-errors"
            and result.has_errors
        ):
            open_summary = True
            try:
                opened = parent.app.open_in_browser(path)
            except (OSError, ValueError):
                opened = False
            if not opened:
                console.print(
                    "[dim]no browser available here - open the workflow report file above[/]"
                )
    if not is_ci and not open_summary:
        for node in plan.walk():
            if node.path in child_openings:
                app, child_report = child_openings[node.path]
                try:
                    opened = app.open_in_browser(child_report)
                except (OSError, ValueError):
                    opened = False
                if not opened:
                    console.print(
                        "[dim]no browser available here - open the child report file above[/]"
                    )
    raise click.exceptions.Exit(
        130
        if result.status == Status.CANCELLED
        else 1
        if result.status == Status.FAILED
        else 0
    )


@workflow_group.command("run")
@click.argument("name", shell_complete=complete_workflows)
@click.option(
    "--dry-run", is_flag=True, help="Preview the workflow without executing jobs."
)
@click.pass_context
@guarded
def run_workflow(ctx, name, dry_run):
    execute_workflow(ctx, name, dry_run=dry_run)


def workflow_command(name, spec, *, hidden=False):
    if hidden:
        return denied_command(name, "workflow")

    @click.pass_context
    @guarded
    def run(ctx, dry_run):
        execute_workflow(ctx, name, dry_run=dry_run)

    command = click.RichCommand(
        name,
        callback=run,
        params=[
            click.Option(
                ["--dry-run"], is_flag=True, help="Preview without executing jobs."
            )
        ],
        help=f"{spec.help or f'Run workflow {name}.'} (local workflow)",
        hidden=hidden,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    command.ptk_workflow = name
    return command


def workspace_shortcuts(ctx):
    if "workflow_shortcuts" not in ctx.meta:
        try:
            parent, _, owners, available = catalog(ctx)
        except PtkError as exc:
            raise click.ClickException(str(exc)) from None
        ctx.meta["workflow_shortcuts"] = {
            name: workflow_command(
                name,
                spec,
                hidden=not (
                    can_view(parent, owners, owner, spec)
                    and matches_namespace(ctx, owners, owner, spec)
                ),
            )
            for name, (owner, spec, _) in available.items()
        }
    return ctx.meta["workflow_shortcuts"]


def workspace_sync(
    ctx, entries, *, target, names, check, diff, command, users_only, output
):
    """Preflight every member before writing shared repository integrations."""
    from .workspace_commands import visit

    root_ctx = ctx.find_root()
    parent, _, owners, available = catalog(ctx)
    for alias in sorted(entries):
        owner = owners[alias]
        if not command_allowed(
            "maintainer.sync", owner.role(), owner.project().config.command_audience
        ):
            raise PtkError(f"{alias}: 'maintainer sync' is a maintainer-only command")
    args = ["maintainer", "sync", target, *names]
    if check:
        args.append("--check")
    if diff:
        args.append("--diff")
    if target != "tasks":
        return visit(root_ctx, [(alias, args) for alias in sorted(entries)])
    if output is None:
        # Member tasks are generated in each repository; the workspace file holds workflow tasks.
        task_args = [
            *args,
            "--command",
            command,
            *(["--users-only"] if users_only else []),
        ]
        visit(root_ctx, [(alias, task_args) for alias in sorted(entries)])
    workflows = []
    for name, (owner, spec, _) in sorted(available.items()):
        if not can_view(parent, owners, owner, spec):
            continue
        restricted = spec.audience == "maintainer" or bool(
            owner
            and owners[owner].project().config.command_audience.get("workflow")
            == "maintainer"
        )
        if users_only and restricted:
            continue
        workflows.append((name, spec.help, restricted))
    root = parent.app.workspace.root(Path.cwd())
    result = parent.app.vscode_tasks.workflows(
        workflows, root=root, command=command, path=output, check=check
    )
    click.echo(
        f"{result.path}: {'up to date' if result.up_to_date else 'out of date' if check else 'updated'}"
    )
    if check and not result.up_to_date:
        raise click.exceptions.Exit(1)
