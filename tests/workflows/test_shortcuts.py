"""Workflow commands and deterministic collision handling for local/CX callers."""

import json
import sys
from types import SimpleNamespace

import pytest
import yaml
from tests.cli_runner import CliRunner
from tests.project_files import write_workflows
from tests.workflows.test_cli import command, invoke, repository

from ptk.drivers.cli import jobs
from ptk.drivers.cli.main import cli


def setup_project(root, *, collide=False):
    return repository(
        root,
        jobs={
            "verify" if collide else "check": command(
                "from pathlib import Path; Path('job-ran').touch()"
            ),
            "other": command("from pathlib import Path; Path('workflow-ran').touch()"),
        },
        workflows={
            "verify": {"help": "Verify everything", "jobs": {"run": {"job": "other"}}}
        },
    )


def test_shortcut_in_help_and_execution(tmp_path):
    root = setup_project(tmp_path)
    help_ = invoke(root, "--help")
    assert "verify" in help_.output and "Verify everything" in help_.output
    result = invoke(root, "verify")
    assert result.exit_code == 0, result.output
    assert (root / "workflow-ran").is_file()
    assert not (root / "job-ran").exists()


@pytest.mark.parametrize("choice", ["job", "workflow"])
def test_local_collision_prompts_before_parsing_target_options(
    tmp_path, monkeypatch, choice
):
    root = setup_project(tmp_path, collide=True)
    monkeypatch.setattr(
        jobs,
        "sys",
        SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True), exit=sys.exit),
    )
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli, ["verify"], input=choice + "\n", catch_exceptions=False, cwd=root
    )
    assert result.exit_code == 0, result.output
    assert "both a job and a workflow" in result.output
    assert (root / f"{choice}-ran").is_file()
    other = "job" if choice == "workflow" else "workflow"
    assert not (root / f"{other}-ran").exists()


def test_collision_is_noninteractive_in_help_cx_and_explicit_commands(tmp_path):
    root = setup_project(tmp_path, collide=True)
    help_ = invoke(root, "verify", "--help")
    assert help_.exit_code == 0 and "Also a local workflow" in help_.output
    ambiguous = invoke(root, "verify")
    assert ambiguous.exit_code == 2 and "non-interactive" in ambiguous.output
    assert not (root / "job-ran").exists()
    ci = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
        cli, ["verify"], cwd=root
    )
    assert ci.exit_code == 0 and (root / "job-ran").is_file(), ci.output
    assert not (root / "workflow-ran").exists()
    assert invoke(root, "run", "verify").exit_code == 0
    assert invoke(root, "workflow", "run", "verify").exit_code == 0
    assert (root / "workflow-ran").is_file()


def test_generated_editor_tasks_resolve_collisions_without_prompting(tmp_path):
    from tests.conftest import grant_maintainer

    root = setup_project(tmp_path, collide=True)
    grant_maintainer(root)
    result = invoke(root, "maintainer", "sync", "tasks", env={"PTK_ROLE": ""})
    assert result.exit_code == 0, result.output
    tasks = json.loads((root / ".vscode/tasks.json").read_text())["tasks"]
    for label, marker in (
        ("ptk: verify", "job-ran"),
        ("ptk: workflow verify", "workflow-ran"),
    ):
        task = next(task for task in tasks if task["label"] == label)
        run = invoke(root, *task["args"])
        assert run.exit_code == 0, run.output
        assert (root / marker).is_file()


def test_vmr_workspace_and_member_shortcuts(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    setup_project(tmp_path / "app")
    write_workflows(
        (tmp_path / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            "workflows:\n  all:\n    jobs:\n      check:\n        job: app:other\n"
        )["workflows"],
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    for args in (["all"], ["app/verify"], ["app", "verify"]):
        result = runner.invoke(cli, args, catch_exceptions=False)
        assert result.exit_code == 0, result.output


def test_shortcut_respects_workflow_command_policy(tmp_path):
    root = repository(
        tmp_path,
        workflows={"verify": {"jobs": {"build": {"job": "build"}}}},
        extra={"command_audience": {"workflow": "maintainer"}},
    )
    assert "verify" not in invoke(root, "--help").output
    assert invoke(root, "verify").exit_code != 0
