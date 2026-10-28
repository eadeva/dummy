"""Artifact destination outputs for external upload workflows."""

import json
from datetime import datetime

import rich_click as click

from ...domain.errors import PtkError
from .access import AccessGroup
from .completion import jobs as complete_jobs
from .state import guarded, state_of


@click.group("artifacts", cls=AccessGroup)
def artifacts_group():
    """Resolve upload destinations; file selection and uploads belong to workflows."""


@artifacts_group.command("destination")
@click.option(
    "--job", required=True, shell_complete=complete_jobs, help="Producing PTK job."
)
@click.option("--event", help="Override GITHUB_EVENT_NAME for a local preview.")
@click.option(
    "--at", help="Reuse a timezone-aware ISO timestamp, e.g. 2026-10-26T15:07:00+01:00."
)
@click.option(
    "--format",
    "format_",
    type=click.Choice(["json", "github", "url"]),
    default="json",
    show_default=True,
)
@click.pass_context
@guarded
def destination(ctx, job, event, at, format_):
    """Resolve the URL, repository and relative path without uploading or writing files."""
    if at is not None:
        try:
            at = datetime.fromisoformat(at)
            if at.tzinfo is None or at.utcoffset() is None:
                raise ValueError("timezone offset is required")
        except ValueError as exc:
            raise PtkError(f"invalid --at timestamp: {exc}") from None
    state = state_of(ctx)
    result = state.app.artifacts().execute(
        state.project(),
        job=job,
        variant=state.variant,
        event=event,
        role=state.role(),
        at=at,
    )
    if format_ == "github":
        for key, value in result.items():
            click.echo(f"{key}={value}")
    elif format_ == "url":
        click.echo(result["url"])
    else:
        click.echo(json.dumps(result, indent=2))
