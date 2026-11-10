"""Generated job commands and maintainer visibility."""

from __future__ import annotations

import os
import sys

import pytest
from rich.text import Text

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import project_files

HOST = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": "/tmp",
    "PTK_ROLE": "user",
}

PROJECT = """\
project:
  name: t
  default_job: build
jobs:
  build:
    help: Build it
    params:
      jobs:
        type: int
        default: 2
        help: Parallel jobs
      mode:
        type: choice
        choices:
        - debug
        - release
        default: release
      fast:
        type: bool
        default: false
      targets:
        type: list
        default:
        - all
      build_type:
        default: x
    steps:
      show:
        run: echo jobs=${params.jobs} mode=${params.mode} fast=${params.fast} targets=${params.targets} bt=${params.build_type}
  publish:
    help: Publish a release
    audience: maintainer
    steps:
      up:
        run: echo uploading
"""


@pytest.fixture
def invoke(write):
    root = write(project_files(PROJECT))
    grant_maintainer(root)

    def _invoke(*args: str, role: str = "user"):
        env = {**HOST, "PTK_ROLE": "user" if role == "user" else ""}
        base = []
        return CliRunner(env={"PTK_CX": "0", **env}).invoke(
            cli, [*base, *args], catch_exceptions=False, cwd=root
        )

    _invoke.root = root
    return _invoke


def test_job_help_has_typed_options(invoke):
    out = Text.from_ansi(invoke("build", "--help").output).plain
    for text in (
        "--jobs",
        "INTEGER",
        "[debug|release]",
        "--fast/--no-fast",
        "--targets",
        "--build-type",
        "default: 2",
        "--only-step",
    ):
        assert text in out, text


def test_typed_options_reach_the_steps(invoke):
    out = invoke(
        "build",
        "--dry-run",
        "--jobs",
        "5",
        "--mode",
        "debug",
        "--fast",
        "--targets",
        "fw,docs",
        "--build-type",
        "y",
    ).output
    assert "jobs=5 mode=debug fast=true targets=fw docs bt=y" in out
    assert "jobs = 5 (command line)" in out and "mode = 'debug' (command line)" in out
    defaults = invoke("build", "--dry-run").output
    assert "jobs=2 mode=release fast=false targets=all" in defaults


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX shell")
def test_generated_command_runs(invoke):
    result = invoke("build", "--jobs", "7")
    assert result.exit_code == 0, result.output
    assert "jobs=7" in result.output


def test_invalid_values_are_rejected_by_the_cli(invoke):
    bad = invoke("build", "--mode", "fastest")
    assert bad.exit_code == 2 and "fastest" in bad.output
    assert invoke("build", "--jobs", "many").exit_code == 2


def test_unknown_command_suggests(invoke):
    result = invoke("biuld")
    assert result.exit_code == 2 and "did you mean 'build'" in result.output


def test_maintainer_jobs_hidden_and_refused_for_users(invoke):
    user_help = invoke("--help").output
    assert "build" in user_help and "publish" not in user_help
    assert "publish" in invoke("maintainer", "--help", role="maintainer").output
    refused = invoke("publish")
    assert refused.exit_code == 2 and "maintainer-only" in refused.output
    assert "maintainer-only" in invoke("run", "publish").output
    assert "maintainer-only" in invoke("publish", "--help").output
    allowed = invoke("maintainer", "publish", "--dry-run", role="maintainer")
    assert allowed.exit_code == 0 and "uploading" in allowed.output


def test_broken_config_still_shows_help(write):
    root = write(project_files("project: {name: t}\njobs: {build: {stepz: []}}\n"))
    base = []
    help_out = CliRunner(env={"PTK_CX": "0", **HOST}).invoke(
        cli, [*base, "--help"], catch_exceptions=False, cwd=root
    )
    assert help_out.exit_code == 0 and "config" in help_out.output
    run = CliRunner(env={"PTK_CX": "0", **HOST}).invoke(
        cli, [*base, "build"], catch_exceptions=False, cwd=root
    )
    assert run.exit_code == 2 and "stepz" in run.output


def test_help_page_lists_jobs_once(invoke, tmp_path):
    out = tmp_path / "h.html"
    invoke("help", "--no-open", "-o", str(out))
    html = out.read_text()
    assert "ptk build [OPTIONS]" in html and "--jobs N" in html
    assert 'id="cmd-build"' not in html and 'id="cmd-dry-run-build"' not in html
