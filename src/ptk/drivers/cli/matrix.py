"""Hidden machine-readable workflow setup export for maintainers and CX."""

import json
from datetime import UTC, datetime

import rich_click as click

from ...application.use_cases.matrix import ExportMatrix
from ...domain.errors import PtkError
from .completion import jobs as complete_jobs
from .state import guarded, state_of


@click.command("matrix", hidden=True)
@click.option(
    "--job",
    "jobs",
    multiple=True,
    shell_complete=complete_jobs,
    help="Include only these jobs (repeatable); default: all eligible jobs.",
)
@click.option(
    "--event", help="Override GITHUB_EVENT_NAME for artifact routing previews."
)
@click.option(
    "--at", help="Use a timezone-aware ISO timestamp for all artifact destinations."
)
@click.option(
    "--format",
    "format_",
    type=click.Choice(["json", "github"]),
    default="json",
    show_default=True,
    help="JSON document, or matrix/upload_base/has_jobs lines for GITHUB_OUTPUT.",
)
@click.option(
    "--workflow",
    help="Export per-invocation matrices and producer selectors for a configured workflow.",
)
@click.pass_context
@guarded
def matrix_command(ctx, jobs, event, at, format_, workflow):
    """Export execution and artifact metadata for a GitHub workflow's setup job.

    Available to local maintainers and in CX. -V selects concrete variants or
    aliases; by default all concrete variants are exported. GitHub needs identifies
    producer jobs; output paths and artifact properties come from completed jobs.
    The matrix does not execute jobs, upload files or generate a workflow.
    """
    state = state_of(ctx)
    if ctx.find_root().params.get("overrides"):
        raise PtkError(
            "matrix exports project configuration; do not combine it with --set"
        )
    if state.clean or state.re_run:
        raise PtkError(
            "matrix is read-only; --clean and --re-run apply only to jobs and workflows"
        )
    if at is not None:
        try:
            at = datetime.fromisoformat(at)
            if at.tzinfo is None or at.utcoffset() is None:
                raise ValueError("timezone offset is required")
        except ValueError as exc:
            raise PtkError(f"invalid --at timestamp: {exc}") from None
    if workflow:
        if jobs:
            raise PtkError("--workflow cannot be combined with --job")
        from .github_workflows import workflow_matrix

        data = workflow_matrix(ctx, workflow, at=at or datetime.now(UTC), event=event)
    else:
        project = state.project()
        data = ExportMatrix(state.app.artifacts()).execute(
            project,
            role=state.role(),
            variant=state.variant,
            jobs=jobs,
            event=event,
            at=at,
        )
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if format_ == "github":
        for invocation, matrix in data.get("jobs", {}).items():
            click.echo("matrix_" + invocation + "=" + encode(matrix))
        click.echo("matrix=" + encode(data["matrix"]))
        click.echo("upload_base=" + encode(data["upload_base"]))
        click.echo("has_jobs=" + ("true" if data["matrix"]["include"] else "false"))
    else:
        click.echo(encode(data))
