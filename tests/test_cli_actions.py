"""Generated action commands, maintainer visibility, VS Code tasks."""

from __future__ import annotations

import json
import os
import sys

import pytest
from click.testing import CliRunner

from ptk.adapters.vscode_file import strip_jsonc
from ptk.domain import vscode
from ptk.drivers.cli.main import cli

HOST = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": "/tmp",
    "PTK_ROLE": "user",
}

PROJECT = """
project: {name: t, default_action: build}
actions:
  build:
    help: Build it
    params:
      jobs: {type: int, default: 2, help: Parallel jobs}
      mode: {type: choice, choices: [debug, release], default: release}
      fast: {type: bool, default: false}
      targets: {type: list, default: [all]}
      build_type: {default: x}
    steps:
      - show: "echo jobs=${params.jobs} mode=${params.mode} fast=${params.fast} targets=${params.targets} bt=${params.build_type}"
  publish:
    help: Publish a release
    audience: maintainer
    steps: [{up: "echo uploading"}]
"""


@pytest.fixture
def invoke(write):
    root = write({"main.ptk.yml": PROJECT})

    def _invoke(*args: str, role: str = "user"):
        env = {**HOST, "PTK_ROLE": role}
        base = ["--config", str(root / "main.ptk.yml"), "--no-ci"]
        return CliRunner(env=env).invoke(cli, [*base, *args], catch_exceptions=False)

    _invoke.root = root
    return _invoke


def test_action_help_has_typed_options(invoke):
    out = invoke("build", "--help").output
    for text in (
        "--jobs",
        "INTEGER",
        "[debug|release]",
        "--fast/--no-fast",
        "--targets",
        "--build-type",
        "default: 2",
        "-V",
        "--from",
    ):
        assert text in out, text


def test_typed_options_reach_the_steps(invoke):
    out = invoke(
        "dry-run",
        "build",
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
    defaults = invoke("dry-run", "build").output
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


def test_maintainer_actions_hidden_and_refused_for_users(invoke):
    user_help = invoke("--help").output
    assert "build" in user_help and "publish" not in user_help
    assert "publish" in invoke("--help", role="maintainer").output
    refused = invoke("publish")
    assert refused.exit_code == 2 and "maintainer-only" in refused.output
    assert "maintainer-only" in invoke("run", "publish").output
    allowed = invoke("dry-run", "publish", role="maintainer")
    assert allowed.exit_code == 0 and "uploading" in allowed.output


def test_broken_config_still_shows_help(write):
    root = write(
        {"main.ptk.yml": "project: {name: t}\nactions: {build: {stepz: []}}\n"}
    )
    base = ["--config", str(root / "main.ptk.yml")]
    help_out = CliRunner(env=HOST).invoke(
        cli, [*base, "--help"], catch_exceptions=False
    )
    assert help_out.exit_code == 0 and "config" in help_out.output
    run = CliRunner(env=HOST).invoke(cli, [*base, "build"], catch_exceptions=False)
    assert run.exit_code == 2 and "stepz" in run.output


# --------------------------------------------------------------------------- vscode


def test_jsonc():
    text, comments = strip_jsonc('{"a": "x // y", /* c */ "b": [1, 2,], // end\n}')
    assert json.loads(text) == {"a": "x // y", "b": [1, 2]} and comments


def test_merge_keeps_user_tasks_and_inputs():
    tasks, inputs = vscode.build_tasks(
        [vscode.TaskAction("build", "Build", True, False)],
        command="ptk",
        variants=["a", "b"],
        default_variant="a",
    )
    existing = {
        "version": "2.0.0",
        "tasks": [{"label": "mine"}, {"label": "ptk: old"}],
        "inputs": [{"id": "other"}, {"id": "ptkVariant", "options": ["z"]}],
    }
    merged = vscode.merge(existing, tasks, inputs)
    assert [t["label"] for t in merged["tasks"]] == ["mine", "ptk: build"]
    assert [i["id"] for i in merged["inputs"]] == ["other", "ptkVariant"]
    assert merged["tasks"][1]["args"] == ["build", "-V", "${input:ptkVariant}"]
    assert merged["tasks"][1]["group"] == {"kind": "build", "isDefault": True}
    assert vscode.merge(merged, tasks, inputs) == merged  # idempotent


def test_vscode_tasks_command(invoke):
    tasks_file = invoke.root / ".vscode" / "tasks.json"
    tasks_file.parent.mkdir()
    tasks_file.write_text(
        '{\n  // mine\n  "version": "2.0.0",\n  "tasks": [{"label": "lint"},],\n}\n'
    )
    assert invoke("vscode", "tasks", "--check").exit_code == 1
    result = invoke("vscode", "tasks", "--command", "uv run ptk")
    assert (
        result.exit_code == 0
        and "comments in the file could not be kept" in result.output
    )
    data = json.loads(tasks_file.read_text())
    assert [t["label"] for t in data["tasks"]] == ["lint", "ptk: build"]
    assert data["tasks"][1]["command"] == "uv run ptk"
    assert (
        invoke("vscode", "tasks", "--check", "--command", "uv run ptk").exit_code == 0
    )
    # maintainers get their actions too, unless --users-only
    invoke("vscode", "tasks", role="maintainer")
    labels = [t["label"] for t in json.loads(tasks_file.read_text())["tasks"]]
    assert "ptk: publish" in labels
    invoke("vscode", "tasks", "--users-only", role="maintainer")
    labels = [t["label"] for t in json.loads(tasks_file.read_text())["tasks"]]
    assert "ptk: publish" not in labels


def test_help_page_lists_actions_once(invoke, tmp_path):
    out = tmp_path / "h.html"
    invoke("help", "--no-open", "-o", str(out))
    html = out.read_text()
    assert "ptk build [OPTIONS]" in html and "--jobs N" in html
    assert 'id="cmd-build"' not in html and 'id="cmd-dry-run-build"' not in html
