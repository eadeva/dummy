"""Hidden CX commands that transfer declared outputs between generated workflow jobs."""

import json
import os
from pathlib import Path
from zipfile import BadZipFile

import rich_click as click

from ...adapters import github_actions as actions
from ...domain.errors import PtkError
from .state import guarded


def _scope():
    scope = (
        os.environ.get("GITHUB_REPOSITORY", "")
        + "/"
        + os.environ.get("GITHUB_RUN_ID", "")
    )
    if scope == "/":
        raise PtkError("CX artifact transfer needs GITHUB_REPOSITORY and GITHUB_RUN_ID")
    return scope


def _emit(values):
    """``name=value`` lines for GITHUB_OUTPUT."""
    for name, value in values.items():
        text = str(value).lower() if isinstance(value, bool) else str(value)
        if "\n" in text or "\r" in text:
            raise PtkError(f"output {name} contains a line break")
        click.echo(f"{name}={text}")


def _json(value, name):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise PtkError(f"{name} is not valid JSON: {exc}") from None


def _run(action):
    try:
        return action()
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, BadZipFile) as exc:
        raise PtkError(str(exc)) from None


@click.group("cx", hidden=True)
def cx_group():
    """Artifact transfer steps of generated GitHub workflows."""


def _transfer(user, token):
    return _run(lambda: actions.Curl(user, token))


_USER = click.option(
    "--user", envvar="PTK_ARTIFACT_USER", required=True, help="Artifactory login."
)
_TOKEN = click.option(
    "--token", envvar="PTK_ARTIFACT_TOKEN", required=True, help="Artifactory token."
)


@cx_group.command("upload")
@click.option("--producer", envvar="PTK_PRODUCER", required=True)
@click.option("--result", envvar="PTK_GITHUB_RESULT", required=True)
@click.option("--properties", envvar="PTK_PROPERTIES", default="{}")
@click.option("--outcome", envvar="PTK_JOB_OUTCOME", default="success")
@_USER
@_TOKEN
@guarded
def upload(producer, result, properties, outcome, user, token):
    """Upload the job's declared outputs with their properties; manifest last."""
    handoff = Path(result)
    if not handoff.is_file():
        if outcome == "success":
            raise PtkError("PTk did not return a job result; update PTk in the image")
        _emit({"outputs-valid": False})
        return
    data = _json(handoff.read_text(encoding="utf-8"), "job result")
    upload_file = data.get("upload_file")
    if not upload_file:
        if outcome == "success":
            raise PtkError(data.get("upload_problem") or "job wrote no upload manifest")
        _emit({"outputs-valid": False})
        return
    if data.get("output_contract_failure"):
        _emit({"outputs-valid": False})
        return
    manifest = _json(Path(upload_file).read_text(encoding="utf-8"), "upload manifest")
    row = _json(producer, "producer")
    address = _run(
        lambda: actions.upload(
            manifest,
            Path.cwd(),
            (row.get("upload") or {}).get("url", ""),
            row,
            _scope(),
            _json(properties, "additional properties"),
            _transfer(user, token),
        )
    )
    click.echo(f"uploaded {address}", err=True)
    _emit({"outputs-valid": True, "manifest-url": address})


@cx_group.command("download")
@click.option(
    "--root",
    required=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Checkout root; producer working directories are relative to it.",
)
@click.option("--producers", envvar="PTK_PRODUCERS", required=True)
@click.option("--needs", envvar="PTK_NEEDS", required=True)
@_USER
@_TOKEN
@guarded
def download(root, producers, needs, user, token):
    """Download and verify producer outputs, then replace the declared paths."""
    rows, jobs = _json(producers, "producers"), _json(needs, "needs")
    if not isinstance(rows, list) or not isinstance(jobs, dict):
        raise PtkError("producers must be an array and needs an object")
    for row in rows:
        if row.get("invocation") not in jobs:
            raise PtkError("producer is not declared in GitHub needs")
    restored = _run(
        lambda: actions.download(rows, root.resolve(), _scope(), _transfer(user, token))
    )
    for path in restored:
        click.echo(f"restored {path}", err=True)
