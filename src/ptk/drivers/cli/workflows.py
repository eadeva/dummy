"""Workflow CLI: resolve repository owners, preflight calls, then orchestrate."""

from __future__ import annotations

import json
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
from ...domain import run_output as display
from ...domain.errors import PtkError
from .access import AccessGroup, denied_command, in_maintainer
from .completion import workflows as complete_workflows
from .jobs import write_reports
from .options import cache_option, docker_option
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
                cx=parent.cx,
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


def maintainer_only(owners, owner, spec):
    return spec.audience == "maintainer" or bool(
        owner
        and owners[owner].project().config.command_audience.get("workflow")
        == "maintainer"
    )


def matches_namespace(ctx, owners, owner, spec):
    return maintainer_only(owners, owner, spec) == in_maintainer(ctx)


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
    """List, inspect and run dependency graphs of repository jobs."""
    from .cleanup import mode

    if mode(state_of(ctx)) and ctx.invoked_subcommand != "run":
        raise PtkError("--clean and --re-run require workflow run")


@workflow_group.command("list")
@click.pass_context
@guarded
def list_workflows(ctx):
    """List workflows; the maintainer list also shows maintainer-only workflows."""
    parent, _, owners, available = catalog(ctx)
    maintainer = in_maintainer(ctx)
    shown = 0
    for name, (owner, spec, _) in sorted(available.items()):
        if not can_view(parent, owners, owner, spec):
            continue
        restricted = maintainer_only(owners, owner, spec)
        if restricted and not maintainer:
            continue
        mark = " (maintainer)" if restricted else ""
        click.echo(f"{name}{mark}: {spec.help}")
        shown += 1
    if not shown:
        click.echo("no workflows")


def authored(spec):
    return spec.model_dump(exclude_defaults=True)


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
            config_file=entries[owner], overrides=parent.overrides, cx=parent.cx
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
    identity = display.prefix(name, "workspace") if owner is None else f"[{name}]"
    if owner is not None:
        # Opening the latest report does not select a variant. Use the saved run,
        # never today's CLI selection; an HTML-only report still has its owner.
        try:
            summary = json.loads(
                latest.with_suffix(".json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            pass
        else:
            if isinstance(summary, dict) and "owner_variant" in summary:
                identity = display.prefix(name, summary["owner_variant"])
    print_report(latest, identity=identity, kind="WORKFLOW")
    if not parent.app.open_in_browser(latest):
        console.print("[dim]no browser available here - open the file above[/]")


def execute_workflow(ctx, name, *, dry_run=False, graph=False, no_cache_ptk=False):
    from ...adapters.locking import job_lock
    from ...application.use_cases.run import Cancelled, RunRequest
    from ...application.use_cases.workflow import (
        CallOutcome,
        PrepareWorkflow,
        RunWorkflow,
    )
    from ...domain.execution.model import Status
    from ...domain.logging import console_level
    from ...domain.reporting.model import from_summary
    from ...domain.reporting.summary import header, run_summary
    from . import console as present
    from .workflow_output import WorkflowOutput

    parent, entries, owner, spec, root = select(ctx, name)
    if graph or dry_run:
        from .graphs import show_graph

        show_graph(root, name, "workflow", spec.jobs, variant=parent.variant)
        if graph and not dry_run:
            return
    is_cx = parent.app.host.is_cx() if parent.cx is None else parent.cx
    if is_cx and not dry_run:
        raise PtkError(
            "workflows run locally only; CX execution uses individual jobs (use ptk maintainer gen-workflows for GitHub templates)"
        )
    from ...application.use_cases.workflow_variants import WorkflowVariants
    from .cleanup import clean_selected, mode

    cleaning = mode(parent)
    owner_project = None
    if owner is not None:
        owner_project = create_app(host=parent.app.host).load_project.execute(
            config_file=entries[owner], overrides=parent.overrides, cx=parent.cx
        )
    variants = WorkflowVariants(owner_project, parent.variant)
    bindings = {}

    def prepare(node, invocation):
        prefix, separator, job_name = invocation.rpartition(":")
        alias = prefix if separator else owner
        if alias is None:
            raise PtkError("workspace workflow calls require a qualified job: REPO:JOB")
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
            cx=parent.cx,
            verbose=parent.verbose,
        )
        project = state.project()
        job = project.config.jobs.get(job_name)
        if job is not None and any(
            name in job.params and job.params[name].type == "secret"
            for name in node.params
        ):
            raise PtkError(
                "secret parameters must not be stored in workflow configuration; use job credentials"
            )
        from .docker import runs_in_docker

        request = RunRequest(
            job=job_name,
            variant=variants.for_project(alias, project),
            params=node.params,
            dry_run=dry_run,
            role=state.role(),
            no_cache_ptk=no_cache_ptk or parent.no_cache_ptk or parent.re_run,
            # The image provides the tools of jobs that run in Docker.
            check_tools=not (
                job is not None and parent.use_docker(project) and runs_in_docker(job)
            ),
        )
        if parent.clean:
            from ...application.use_cases.cleanup import prepare_cleanup

            prepared = prepare_cleanup(
                project, request.job, request.variant, request.role
            )
        else:
            prepared = state.app.prepare_run(project).execute(project, request)
        bindings[invocation] = state
        return alias, prepared

    plan = PrepareWorkflow().execute(name, spec, prepare)
    if dry_run or cleaning:
        for node in plan.jobs:
            p = node.prepared.plan
            readiness = (
                "; ".join(
                    part
                    for part in (
                        "needs: " + ", ".join(node.spec.needs)
                        if node.spec.needs
                        else "",
                        "after: " + ", ".join(node.spec.local_needs)
                        if node.spec.local_needs
                        else "",
                    )
                    if part
                )
                or "ready"
            )
            click.echo(
                f"{node.id}: {node.repo}:{p.job} [{p.variant or 'default'}] — {readiness}"
            )
    if cleaning:
        clean_selected(
            [node.prepared for node in plan.jobs],
            dry_run=dry_run,
        )
        if parent.clean:
            return
    if dry_run:
        click.echo(
            "PTk cache: disabled for this invocation"
            if no_cache_ptk or parent.no_cache_ptk or parent.re_run
            else "PTk cache: opt-in; reuse is checked after prerequisites run"
        )
        click.echo("workflow dry-run; no jobs executed")
        return
    # Install once per participating repository, before any parallel job starts.
    checked_repositories = set()
    for node in plan.jobs:
        project = node.prepared.project
        if project.root not in checked_repositories:
            bindings[node.id].app.hooks.execute(project, click.echo)
            checked_repositories.add(project.root)
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    started_at = datetime.now(UTC).isoformat()
    target = report_directory(root, name, owner_project) / run_id
    child_openings = {}
    child_reports = {}
    for node in plan.jobs:
        node.prepared.plan.report_context["workflow"] = {
            "name": name,
            "run_id": run_id,
            "invocation": node.id,
            "report_file": str(target / "workflow.html"),
        }
    output = WorkflowOutput(
        console, plan, target, run_id, root, owner_project, variants.selected
    )

    docker_runs = {}

    def docker_job(node):
        from .docker import runs_in_docker

        project = node.prepared.project
        spec = project.config.jobs[node.prepared.plan.job]
        return parent.use_docker(project) and runs_in_docker(spec)

    def run_in_docker(node):
        from .docker import container_argv, job_paths, job_secrets, session

        state, prepared = bindings[node.id], node.prepared
        p = prepared.plan
        spec = prepared.project.config.jobs[p.job]
        docker = session(state, prepared.project, docker_runs)
        argv = container_argv(
            job=p.job,
            maintainer=spec.audience == "maintainer",
            variant=p.variant,
            params=node.spec.params,
            overrides=parent.overrides,
            verbose=parent.verbose,
            no_cache_ptk=no_cache_ptk or parent.no_cache_ptk or parent.re_run,
        )
        code = docker.run(
            argv, secrets=job_secrets(state, prepared.project, [p]), cx=False
        )
        docker.copy_back(job_paths(p))
        report = Path(p.dirs["reports_dir"]) / "report.html"
        status = {0: Status.PASSED, 130: Status.CANCELLED}.get(code, Status.FAILED)
        return CallOutcome(
            status,
            [str(report)] if report.is_file() else [],
            p.run_id,
            report_errors=code != 0,
        )

    def run(node, cancel):
        if docker_job(node):
            return run_in_docker(node)
        state, prepared = bindings[node.id], node.prepared
        p = prepared.plan
        with job_lock(prepared.project.root, p.variant, p.job):
            runner = state.app.run_job(prepared.project)
            result = runner.execute(
                prepared,
                [
                    present.ConsoleObserver(
                        console,
                        level=console_level("info", verbose=parent.verbose),
                        job_label=output.job_label(node),
                    ),
                    *state.app.log_observers(prepared, verbose=parent.verbose),
                    output.observer(node, verbose=parent.verbose),
                ],
                cancel,
            )
            output.job_finished(node, result)
            child_reports[node.id] = from_summary(run_summary(p, result), [])
            opening = write_reports(
                state,
                prepared.project,
                p,
                result,
                open_browser=False,
                job_label=output.job_label(node),
            )
            files = []
            report_errors = False
            try:
                from ...domain.workflows import workflow_job_id

                child_target = target / "jobs" / workflow_job_id(node.id)
                summary = snapshot_logs(run_summary(p, result), child_target)
                report = state.app.reports.build(prepared.project, summary)
                child_reports[node.id] = report
                files = state.app.reports.export(report, ["json", "html"], child_target)
                report_errors = report.has_errors
                if opening is not None:
                    opening = next(
                        (file for file in files if file.name == opening.name), opening
                    )
            except (PtkError, OSError, ValueError) as exc:
                report_errors = True
                err_console.print(
                    f"[yellow]workflow child report not written: {escape(str(exc))}[/]"
                )
            if opening is not None:
                child_openings[node.id] = (state.app, opening)
            return CallOutcome(
                result.status,
                [str(f) for f in files],
                p.run_id,
                report_errors,
                reused_from=result.reused_from,
                output_contract_failure=result.output_contract_failure,
            )

    cancel = Cancelled()
    holder = {}

    def work():
        try:
            holder["result"] = RunWorkflow().execute(plan, run, cancel)
        except BaseException as exc:  # noqa: BLE001 - propagate in the main thread
            holder["error"] = exc

    from contextlib import ExitStack

    from .docker import session

    reservations = ExitStack()
    try:
        # All repository locks up front, in a fixed order, so workflows cannot deadlock.
        for node in plan.jobs:
            if docker_job(node):
                session(bindings[node.id], node.prepared.project, docker_runs)
        for docker in sorted(docker_runs.values(), key=lambda item: item.name):
            reservations.enter_context(docker.reserved())
        output.start()
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
        output.finish(result)
    finally:
        reservations.close()
        output.close()
    open_summary = False
    try:
        for node in plan.jobs:
            if node.id in child_reports:
                continue
            job = next((job for job in result.jobs if job.id == node.id), None)
            if job is None:
                continue
            p = node.prepared.plan
            summary = node.prepared.mask_context(
                {
                    **header(p),
                    "status": "not_run",
                    "steps": [
                        {
                            "step": step.label,
                            "kind": step.kind,
                            "needs": list(step.spec.needs),
                            "report": step.spec.report,
                            "status": "not_run",
                            "message": job.message or "No step result recorded",
                        }
                        for step in p.steps
                    ],
                }
            )
            child_reports[node.id] = from_summary(summary, [])
        path = write_workflow_report(
            result,
            target,
            owner_variant=variants.selected,
            children=child_reports,
            context={
                "run_id": run_id,
                "started_at": started_at,
                "workspace": owner_project is None,
            },
        )
        print_report(path, identity=output.identity, kind="WORKFLOW")
        print_report(
            target / "diagnostics.html", identity=output.identity, kind="WORKFLOW"
        )
    except OSError as exc:
        err_console.print(f"[yellow]workflow report not written: {escape(str(exc))}[/]")
    else:
        if not is_cx and (result.has_errors or spec.open_report == "always"):
            open_summary = True
            opening = target / "diagnostics.html" if result.has_errors else path
            try:
                opened = parent.app.open_in_browser(opening)
            except (OSError, ValueError):
                opened = False
            if not opened:
                console.print(
                    "[dim]no browser available here - open the workflow report file above[/]"
                )
    if not is_cx and not open_summary:
        for node in plan.jobs:
            if node.id in child_openings:
                app, child_report = child_openings[node.id]
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
@click.option(
    "--graph",
    is_flag=True,
    help="Show the dependency graph without preparing or executing jobs.",
)
@click.pass_context
@guarded
def run_workflow(ctx, name, dry_run, graph, no_cache_ptk, docker):
    if docker is not None:
        state_of(ctx).docker = docker
    execute_workflow(ctx, name, dry_run=dry_run, graph=graph, no_cache_ptk=no_cache_ptk)


run_workflow.params.extend([cache_option(), docker_option()])


def workflow_command(name, spec, *, hidden=False):
    if hidden:
        return denied_command(name, "workflow")

    @click.pass_context
    @guarded
    def run(ctx, dry_run, graph, no_cache_ptk, docker):
        if docker is not None:
            state_of(ctx).docker = docker
        execute_workflow(
            ctx, name, dry_run=dry_run, graph=graph, no_cache_ptk=no_cache_ptk
        )

    command = click.RichCommand(
        name,
        callback=run,
        params=[
            cache_option(),
            docker_option(),
            click.Option(
                ["--graph"],
                is_flag=True,
                help="Show the dependency graph without executing jobs.",
            ),
            click.Option(
                ["--dry-run"], is_flag=True, help="Preview without executing jobs."
            ),
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


def workspace_sync(ctx, entries, *, target, names, check, diff, force=False):
    """Preflight every member before running the sync in each repository."""
    from .workspace_commands import visit

    root_ctx = ctx.find_root()
    _, _, owners, _ = catalog(ctx)
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
    if force:
        args.append("--force")
    return visit(root_ctx, [(alias, args) for alias in sorted(entries)])
