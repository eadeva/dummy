"""Run the public and maintenance command surfaces against real projects."""

import json
import sys

import pytest
from click.shell_completion import BashComplete
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer
from tests.project_files import write_project


def project(root):
    def job(marker, audience="all"):
        return {
            "audience": audience,
            "params": {"word": {"default": "hello"}},
            "steps": [
                {
                    "write": {
                        "run": [
                            sys.executable,
                            "-c",
                            f"from pathlib import Path; Path({marker!r}).write_text('done')",
                        ]
                    }
                }
            ],
        }

    write_project(
        root / ".main.ptk.yml",
        {
            "repository": {"alias": "demo", "config_path": "."},
            "project": {"name": "demo"},
            "jobs": {
                "build": job("public-result"),
                "publish": job("private-result", "maintainer"),
            },
            "workflows": {
                "verify": {"open_report": None, "steps": [{"build": "build"}]},
                "release": {
                    "audience": "maintainer",
                    "open_report": None,
                    "steps": [{"publish": "publish"}],
                },
            },
            "variants": {"default": "small", "variants": {"small": {}, "large": {}}},
            "versioning": {"project": {"source": "literal", "version": "1.2.3"}},
            "reporting": {"formats": []},
        },
    )
    grant_maintainer(root)
    return ["-C", str(root / ".main.ptk.yml")]


@pytest.mark.parametrize(
    "target,marker",
    [
        ("build", "public-result"),
        ("verify", "public-result"),
        ("publish", "private-result"),
        ("release", "private-result"),
    ],
)
def test_jobs_and_workflows_have_direct_commands_with_safe_previews(
    tmp_path, target, marker
):
    base = project(tmp_path)
    namespace = ["maintainer"] if target in {"publish", "release"} else []
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    result = runner.invoke(
        cli, [*base, *namespace, target, "--dry-run"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert not (tmp_path / marker).exists()
    result = runner.invoke(cli, [*base, *namespace, target], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert (tmp_path / marker).read_text() == "done"
    preview = [
        *base,
        *namespace,
        *(["run"] if target in {"build", "publish"} else ["workflow", "run"]),
        target,
        "--dry-run",
    ]
    assert runner.invoke(cli, preview).exit_code == 0


def test_visibility_completion_and_inventory_follow_the_namespace(
    tmp_path, monkeypatch
):
    base = project(tmp_path)
    monkeypatch.setenv("PTK_ROLE", "")
    runner = CliRunner(env={"PTK_CI": "0"})
    complete = BashComplete(cli, {}, "ptk", "_PTK_COMPLETE")
    names = lambda args: {
        item.value for item in complete.get_completions([*base, *args], "")
    }
    assert {"build", "verify", "self-service", "maintainer"} <= names([])
    assert not {"publish", "release", "describe", "run"} & names([])
    assert {"publish", "release", "sync", "config"} <= names(["maintainer"])
    assert names(["run"]) == {"build"}
    assert names(["maintainer", "run"]) == {"publish"}
    assert names(["workflow", "run"]) == {"verify"}
    assert names(["maintainer", "workflow", "run"]) == {"release"}
    inventory = json.loads(runner.invoke(cli, [*base, "describe", "--json"]).output)[
        "projects"
    ][0]
    jobs = {item["name"]: item for item in inventory["jobs"]}
    workflows = {item["name"]: item for item in inventory["workflows"]}
    assert jobs["publish"]["command"] == ["maintainer", "run", "publish"]
    assert jobs["publish"]["help_command"] == ["maintainer", "publish"]
    assert workflows["release"]["command"] == [
        "maintainer",
        "workflow",
        "run",
        "release",
    ]
    assert "publish" not in runner.invoke(cli, [*base, "--help"]).output
    assert "publish" in runner.invoke(cli, [*base, "maintainer", "--help"]).output
    monkeypatch.setenv("PTK_ROLE", "user")
    assert "maintainer" not in names([])
    for args in (
        ["publish"],
        ["run", "publish"],
        ["maintainer", "publish"],
        ["maintainer", "release"],
        ["workflow", "run", "release"],
    ):
        result = runner.invoke(cli, [*base, *args, "--dry-run"])
        assert result.exit_code != 0, result.output
    assert not (tmp_path / "private-result").exists()


def test_generated_tasks_preserve_restricted_command_paths(tmp_path):
    base = project(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    result = runner.invoke(cli, [*base, "maintainer", "sync", "tasks"])
    assert result.exit_code == 0, result.output
    tasks = json.loads((tmp_path / ".vscode/tasks.json").read_text())["tasks"]
    by_label = {task["label"]: task["args"] for task in tasks}
    assert by_label["ptk: publish"][-3:] == ["maintainer", "run", "publish"]
    assert by_label["ptk: workflow release"] == [
        "maintainer",
        "workflow",
        "run",
        "release",
    ]
    assert (
        runner.invoke(cli, [*base, "maintainer", "sync", "tasks", "--check"]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            cli, [*base, "maintainer", "sync", "tasks", "--users-only"]
        ).exit_code
        == 0
    )
    tasks = json.loads((tmp_path / ".vscode/tasks.json").read_text())["tasks"]
    assert {task["label"] for task in tasks} == {"ptk: build", "ptk: workflow verify"}


def test_validation_combines_optional_checks_and_handles_missing_projects(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"})
    missing = runner.invoke(cli, ["validate"])
    assert missing.exit_code == 2
    assert "No PTK project found" in missing.output and "ptk init" in missing.output
    base = project(tmp_path)
    result = runner.invoke(
        cli, [*base, "validate", "--variants", "--versions", "--generated"]
    )
    assert result.exit_code == 0, result.output
    assert "small" in result.output and "Version sources" in result.output
    for args in (["--strict"], ["--job", "build"]):
        assert runner.invoke(cli, [*base, "validate", *args]).exit_code == 2
    (tmp_path / "project.ptk.yml").write_text("name: demo\nunknown: broken\n")
    invalid = runner.invoke(cli, [*base, "validate"])
    assert "unknown" in invalid.output and "No PTK project found" not in invalid.output


def test_validation_preserves_misplaced_marker_diagnostic(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".main.ptk.yml").write_text("repository: {alias: demo, config_path: .}\n")
    monkeypatch.chdir(nested)
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code == 2
    assert "must be at repository root" in result.output
    assert "No PTK project found" not in result.output


def test_workspace_and_member_workflows_keep_their_namespace(tmp_path, monkeypatch):
    from tests.project_files import read_project, write_workflows

    project(tmp_path / "app")
    entry = tmp_path / "app/.main.ptk.yml"
    model = read_project(entry)
    del model["variants"]
    write_project(entry, model)
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    grant_maintainer(tmp_path)
    write_workflows(
        tmp_path / "workflows",
        {
            "ship": {
                "audience": "maintainer",
                "open_report": None,
                "steps": [{"release": {"repo": "demo", "job": "publish"}}],
            }
        },
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    for group in ("self-service", "maintainer"):
        result = runner.invoke(cli, [group], catch_exceptions=False)
        assert result.exit_code == 0 and "Usage:" in result.output, result.output
    for args in (
        ["maintainer", "ship"],
        ["maintainer", "demo/release"],
        ["demo", "maintainer", "release"],
        ["demo", "maintainer", "publish"],
        ["demo/verify"],
    ):
        result = runner.invoke(cli, [*args, "--dry-run"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
    assert not (tmp_path / "app/private-result").exists()
    assert not (tmp_path / "app/public-result").exists()
    result = runner.invoke(cli, ["maintainer", "ship"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "app/private-result").exists()
    for args in (["ship"], ["workflow", "run", "ship"], ["demo", "release"]):
        assert runner.invoke(cli, [*args, "--dry-run"]).exit_code != 0
    user = runner.invoke(
        cli, ["maintainer", "ship", "--dry-run"], env={"PTK_ROLE": "user"}
    )
    assert user.exit_code != 0 and "maintainer-only" in user.output
