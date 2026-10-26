"""Workflow commands and deterministic collision handling for local/CX callers."""

import sys
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from tests.workflows.test_cli import command, invoke, repository

from ptk.drivers.cli import actions
from ptk.drivers.cli.main import cli


def setup_project(root, *, collide=False):
    return repository(
        root,
        actions={
            "verify" if collide else "check": command(
                "from pathlib import Path; Path('action-ran').touch()"
            ),
            "other": command("from pathlib import Path; Path('workflow-ran').touch()"),
        },
        workflows={
            "verify": {"help": "Verify everything", "steps": [{"run": "other"}]}
        },
    )


def test_shortcut_in_help_and_execution(tmp_path):
    root = setup_project(tmp_path)
    help_ = invoke(root, "--help")
    assert "verify" in help_.output and "Verify everything" in help_.output
    result = invoke(root, "verify")
    assert result.exit_code == 0, result.output
    assert (root / "workflow-ran").is_file()
    assert not (root / "action-ran").exists()


@pytest.mark.parametrize("choice", ["action", "workflow"])
def test_local_collision_prompts_before_parsing_target_options(
    tmp_path, monkeypatch, choice
):
    root = setup_project(tmp_path, collide=True)
    monkeypatch.setattr(
        actions,
        "sys",
        SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True), exit=sys.exit),
    )
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli,
        ["-c", str(root / ".main.ptk.yml"), "verify"],
        input=choice + "\n",
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "both an action and a workflow" in result.output
    assert (root / f"{choice}-ran").is_file()
    other = "action" if choice == "workflow" else "workflow"
    assert not (root / f"{other}-ran").exists()


def test_collision_is_noninteractive_in_help_cx_and_explicit_commands(tmp_path):
    root = setup_project(tmp_path, collide=True)
    help_ = invoke(root, "verify", "--help")
    assert help_.exit_code == 0 and "Also a local workflow" in help_.output
    ambiguous = invoke(root, "verify")
    assert ambiguous.exit_code == 2 and "non-interactive" in ambiguous.output
    assert not (root / "action-ran").exists()
    ci = invoke(root, "--ci", "verify")
    assert ci.exit_code == 0 and (root / "action-ran").is_file(), ci.output
    assert not (root / "workflow-ran").exists()
    assert invoke(root, "run", "verify").exit_code == 0
    assert invoke(root, "workflow", "run", "verify").exit_code == 0
    assert (root / "workflow-ran").is_file()


def test_vmr_workspace_and_member_shortcuts(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    setup_project(tmp_path / "app")
    (tmp_path / "workflow.ptk.yml").write_text(
        "workflows:\n  all:\n    steps:\n      - check: {repo: app, action: other}\n"
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    for args in (["all"], ["app/verify"], ["app", "verify"]):
        result = runner.invoke(cli, args, catch_exceptions=False)
        assert result.exit_code == 0, result.output


def test_shortcut_respects_workflow_command_policy(tmp_path):
    root = repository(
        tmp_path,
        workflows={"verify": {"steps": [{"build": "build"}]}},
        extra={"command_audience": {"workflow": "maintainer"}},
    )
    assert "verify" not in invoke(root, "--help").output
    assert invoke(root, "verify").exit_code != 0
