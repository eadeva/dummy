"""Workflow execution with real portable actions and bounded VMR discovery."""

import json
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli


def command(code):
    return {"steps": [{"run": {"run": [sys.executable, "-c", code]}}]}


def repository(root, alias="app", *, actions=None, workflows=None, extra=None):
    folder = root / "config"
    folder.mkdir(parents=True)
    (root / ".main.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": alias, "config_path": "config"},
                "include": "project.ptk.yml",
            }
        ),
        encoding="utf-8",
    )
    config = {
        "project": {"name": alias},
        "actions": actions or {"build": command("print('hello')")},
    }
    config.update(extra or {})
    (folder / "project.ptk.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (folder / "workflow.ptk.yml").write_text(
        yaml.safe_dump({"workflows": workflows or {}}), encoding="utf-8"
    )
    return root


def invoke(root, *args, env=None):
    return CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0", **(env or {})}).invoke(
        cli, ["-c", str(root / ".main.ptk.yml"), *args], catch_exceptions=False
    )


def summaries(root):
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in root.rglob("workflow.json")
    ]


def test_discovery_preview_then_sequential_calls_and_immutable_reports(tmp_path):
    action = command(
        "from pathlib import Path; import sys; p=Path('order.txt'); p.write_text((p.read_text() if p.exists() else '') + sys.argv[1]); print(sys.argv[1])"
    )
    action["params"] = {"word": {"default": "x"}}
    action["steps"][0]["run"]["run"].append("${params.word}")
    root = repository(
        tmp_path,
        actions={"build": action},
        workflows={
            "verify": {
                "steps": [
                    {"one": {"action": "build", "params": {"word": "A"}}},
                    {"two": {"action": "build", "params": {"word": "B"}}},
                ]
            }
        },
    )
    assert "verify" in invoke(root, "workflow", "list").output
    assert "params:" in invoke(root, "workflow", "show", "verify").output
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    preview = invoke(root, "workflow", "dry-run", "verify")
    assert preview.exit_code == 0, preview.output
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    assert (root / "order.txt").read_text() == "AB"
    [summary] = summaries(root)
    assert summary["status"] == "passed"
    assert [s["status"] for s in summary["steps"]] == ["passed", "passed"]
    reports = list(root.glob("_reports/workflows/verify/*/actions/*/report.json"))
    assert len(reports) == 2
    for report in reports:
        data = json.loads(report.read_text())
        log = Path(data["steps"][0]["log_file"])
        assert log.is_relative_to(report.parent)
        assert data["params"]["word"] in log.read_text()


def test_parallel_actions_actually_overlap(tmp_path):
    def barrier(own, other):
        return command(
            f"from pathlib import Path; import time; Path('{own}').touch(); deadline=time.monotonic()+5\nwhile not Path('{other}').exists() and time.monotonic()<deadline: time.sleep(.02)\nassert Path('{other}').exists()"
        )

    root = repository(
        tmp_path,
        actions={"a": barrier("a", "b"), "b": barrier("b", "a")},
        workflows={
            "verify": {
                "steps": [
                    {
                        "checks": {
                            "parallel": True,
                            "steps": [
                                {"a": {"action": "a"}},
                                {"b": {"action": "b"}},
                            ],
                        }
                    }
                ]
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("continued", [False, True])
def test_failure_controls_sequential_continuation(tmp_path, continued):
    root = repository(
        tmp_path,
        actions={
            "fail": command("raise SystemExit(1)"),
            "after": command("from pathlib import Path; Path('after').touch()"),
        },
        workflows={
            "verify": {
                "steps": [
                    {"broken": {"action": "fail", "continue_on_error": continued}},
                    {"next": {"action": "after"}},
                ]
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == (0 if continued else 1), result.output
    assert (root / "after").exists() is continued
    [summary] = summaries(root)
    assert summary["steps"][1]["status"] == ("passed" if continued else "skipped")


@pytest.mark.parametrize(
    "call,error",
    [
        ({"action": "missing"}, "unknown action"),
        ({"repo": "missing", "action": "build"}, "not a configured member"),
        ({"action": "build", "params": {"unknown": 1}}, "unknown parameter"),
        ({"action": "restricted"}, "maintainer-only"),
    ],
)
def test_all_calls_are_preflighted_before_running(tmp_path, call, error):
    actions = {
        "build": command("from pathlib import Path; Path('ran').touch()"),
        "restricted": {**command("print('secret')"), "audience": "maintainer"},
    }
    root = repository(
        tmp_path,
        actions=actions,
        workflows={
            "verify": {"steps": [{"first": {"action": "build"}}, {"bad": call}]}
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code != 0 and error in result.output, result.output
    assert not (root / "ran").exists()
    assert not (root / "_reports").exists()


def test_reject_parallel_output_and_uv_environment_collisions(tmp_path):
    root = repository(
        tmp_path,
        workflows={
            "bad": {"parallel": True, "steps": [{"one": "build"}, {"two": "build"}]}
        },
    )
    result = invoke(root, "workflow", "dry-run", "bad")
    assert result.exit_code != 0 and "parallel workflow branches share" in result.output
    a = command("pass")
    a["steps"][0]["run"]["python"] = {"project": "."}
    (root / "config/project.ptk.yml").write_text(
        yaml.safe_dump({"project": {"name": "app"}, "actions": {"a": a, "b": a}})
    )
    (root / "config/workflow.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "workflows": {
                    "bad": {"parallel": True, "steps": [{"one": "a"}, {"two": "b"}]}
                }
            }
        )
    )
    result = invoke(root, "workflow", "dry-run", "bad")
    assert result.exit_code != 0 and "uv project environment" in result.output


def test_vmr_targets_keep_environment_and_reports_and_have_editor_tasks(
    tmp_path, monkeypatch
):
    root = tmp_path
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [a, b]\n")
    for alias in ("a", "b"):
        action = command(
            "import os; from pathlib import Path; Path('selected').write_text(os.environ['IDENTITY'])"
        )
        repository(
            root / alias,
            alias,
            actions={"build": action},
            workflows={"local": {"steps": [{"build": "build"}]}},
            extra={"environment": {"set": {"IDENTITY": alias}}},
        )
    (root / "workflow.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "workflows": {
                    "all": {
                        "parallel": True,
                        "steps": [
                            {"a": {"repo": "a", "action": "build"}},
                            {"b": {"repo": "b", "action": "build"}},
                        ],
                    }
                }
            }
        )
    )
    monkeypatch.chdir(root)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"})
    for args in (
        ["workflow", "list"],
        ["workflow", "run", "all"],
        ["workflow", "run", "a/local"],
        ["a", "workflow", "dry-run", "local"],
        ["setup", "vscode", "tasks"],
        ["a", "setup", "vscode", "tasks"],
    ):
        result = runner.invoke(cli, args, catch_exceptions=False)
        assert result.exit_code == 0, result.output
    for alias in ("a", "b"):
        assert (root / alias / "selected").read_text() == alias
    workspace_tasks = json.loads((root / ".vscode/tasks.json").read_text())["tasks"]
    assert {t["label"] for t in workspace_tasks} == {
        "ptk: workflow all",
        "ptk: workflow a/local",
        "ptk: workflow b/local",
    }
    member_tasks = json.loads((root / "a/.vscode/tasks.json").read_text())["tasks"]
    workflow = next(t for t in member_tasks if t["label"] == "ptk: workflow local")
    assert workflow["command"] == "ptk a" and workflow["options"]["cwd"] == str(root)
    assert (
        len(list((root / "_reports/workflows/all").glob("*/actions/*/report.html")))
        == 2
    )


@pytest.mark.parametrize("level", ["action", "step"])
def test_parallel_python_calls_use_their_resolved_venv_paths(tmp_path, level):
    actions = {}
    for name in ("a", "b"):
        action = command("pass")
        step = action["steps"][0]["run"]
        step["python"] = {"project": "."}
        action["env"] = {"UV_PROJECT_ENVIRONMENT": "${project.root}/shared"}
        target = action if level == "action" else step
        target["env"] = {
            "UV_PROJECT_ENVIRONMENT": f"${{project.root}}/.ptk/venvs/{name}"
        }
        actions[name] = action
    root = repository(
        tmp_path,
        actions=actions,
        workflows={"verify": {"parallel": True, "steps": [{"a": "a"}, {"b": "b"}]}},
    )
    preview = invoke(root, "workflow", "dry-run", "verify")
    assert preview.exit_code == 0, preview.output
    target = actions["b"] if level == "action" else actions["b"]["steps"][0]["run"]
    target["env"]["UV_PROJECT_ENVIRONMENT"] = "${project.root}/.ptk/venvs/b/../a"
    (root / "config/project.ptk.yml").write_text(
        yaml.safe_dump({"project": {"name": "app"}, "actions": actions}),
        encoding="utf-8",
    )
    collision = invoke(root, "workflow", "dry-run", "verify")
    assert collision.exit_code == 2 and "uv project environment" in collision.output


def test_source_locations_and_workflow_name_validation(tmp_path):
    root = repository(tmp_path)
    file = root / "config/workflow.ptk.yml"
    file.write_text(
        "workflows:\n  verify:\n    steps:\n      - build: {acton: build}\n"
    )
    result = invoke(root, "setup", "config", "validate")
    assert result.exit_code != 0
    assert "workflow.ptk.yml:4" in result.output and "acton" in result.output
    file.write_text("workflows: {bad/name: {steps: [{build: build}]}}")
    result = invoke(root, "workflow", "list")
    assert result.exit_code != 0 and "invalid workflow name" in result.output


@pytest.mark.parametrize("body", ["build", {"action": "build"}])
def test_entry_named_name_is_a_normal_action_call(tmp_path, body):
    root = repository(tmp_path, workflows={"verify": {"steps": [{"name": body}]}})
    result = invoke(root, "workflow", "dry-run", "verify")
    assert result.exit_code == 0 and "name: app/build" in result.output, result.output


def test_secret_parameters_cannot_be_embedded_in_workflow_yaml(tmp_path):
    action = command("from pathlib import Path; Path('ran').touch()")
    action["params"] = {"token": {"type": "secret"}}
    root = repository(
        tmp_path,
        actions={"build": action},
        workflows={
            "verify": {
                "steps": [
                    {"build": {"action": "build", "params": {"token": "hidden-value"}}}
                ]
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 2 and "secret parameters" in result.output, result.output
    assert "hidden-value" not in result.output
    assert not (root / "ran").exists()


@pytest.mark.parametrize("command_policy", [False, True])
def test_maintainer_workflows_are_protected_and_hidden_from_user_tasks(
    tmp_path, command_policy
):
    root = repository(
        tmp_path,
        workflows={
            "verify": {
                "audience": "all" if command_policy else "maintainer",
                "steps": [{"build": "build"}],
            }
        },
        extra={"command_audience": {"workflow": "maintainer"}}
        if command_policy
        else {},
    )
    denied = invoke(root, "workflow", "run", "verify")
    assert denied.exit_code != 0 and "maintainer-only" in denied.output, denied.output
    allowed = invoke(root, "workflow", "run", "verify", env={"PTK_ROLE": "maintainer"})
    assert allowed.exit_code == 0, allowed.output
    for role, options, visible in (
        ("user", [], False),
        ("maintainer", [], True),
        ("maintainer", ["--users-only"], False),
    ):
        result = invoke(
            root, "setup", "vscode", "tasks", *options, env={"PTK_ROLE": role}
        )
        assert result.exit_code == 0, result.output
        tasks = json.loads((root / ".vscode/tasks.json").read_text())["tasks"]
        assert any(t["label"] == "ptk: workflow verify" for t in tasks) is visible


def test_workflow_tasks_are_idempotent_and_preserve_user_tasks(tmp_path):
    root = repository(tmp_path, workflows={"verify": {"steps": [{"build": "build"}]}})
    folder = root / ".vscode"
    folder.mkdir()
    (folder / "tasks.json").write_text(
        json.dumps(
            {"version": "2.0.0", "tasks": [{"label": "mine", "command": "hello"}]}
        )
    )
    assert invoke(root, "setup", "vscode", "tasks").exit_code == 0
    assert invoke(root, "setup", "vscode", "tasks", "--check").exit_code == 0
    tasks = json.loads((folder / "tasks.json").read_text())["tasks"]
    assert tasks[0]["label"] == "mine"
    task = next(t for t in tasks if t["label"] == "ptk: workflow verify")
    assert task["args"] == ["workflow", "run", "verify"]


def test_published_example_runs_locally_without_github(tmp_path, monkeypatch):
    import shutil

    source = Path(__file__).resolve().parents[2] / "examples/workflows"
    target = tmp_path / "local vmr"
    shutil.copytree(source, target)
    monkeypatch.chdir(target)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"})
    for args in (
        ["workflow", "run", "all"],
        ["workflow", "run", "frontend/verify"],
        ["frontend", "workflow", "run", "verify"],
    ):
        result = runner.invoke(cli, args, catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "Testing backend" in result.output
        assert "Testing frontend" in result.output


@pytest.mark.parametrize(
    "ci_args,env",
    [
        (["--ci"], {}),
        ([], {"PTK_CI": "1"}),
        ([], {"PTK_CI": "", "GITHUB_ACTIONS": "true"}),
    ],
)
def test_workflow_execution_is_local_only(tmp_path, ci_args, env):
    root = repository(
        tmp_path,
        actions={"build": command("from pathlib import Path; Path('ran').touch()")},
        workflows={"verify": {"steps": [{"build": "build"}]}},
    )
    result = invoke(root, *ci_args, "workflow", "run", "verify", env=env)
    assert result.exit_code != 0 and "locally only" in result.output
    assert not (root / "ran").exists()
    preview = invoke(root, *ci_args, "workflow", "dry-run", "verify", env=env)
    assert preview.exit_code == 0, preview.output
