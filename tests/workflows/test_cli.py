from tests.project_files import write_workflows

"""Workflow execution with real portable jobs and bounded VMR discovery."""

import json
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project

from ptk.drivers.cli.main import cli


def command(code):
    return {"steps": [{"run": {"run": [sys.executable, "-c", code]}}]}


def repository(root, alias="app", *, jobs=None, workflows=None, extra=None):
    folder = root / "config"
    folder.mkdir(parents=True)
    config = {
        "repository": {"alias": alias, "config_path": "config"},
        "project": {"name": alias},
        "jobs": jobs or {"build": command("print('hello')")},
        "workflows": workflows or {},
        **(extra or {}),
    }
    write_project(root / ".main.ptk.yml", config)
    return root


def invoke(root, *args, env=None):
    return CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0", **(env or {})}).invoke(
        cli, ["-C", str(root / ".main.ptk.yml"), *args], catch_exceptions=False
    )


def summaries(root):
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in root.rglob("workflow.json")
    ]


def test_discovery_preview_then_sequential_calls_and_immutable_reports(tmp_path):
    job = command(
        "from pathlib import Path; import os, sys; assert os.environ['PTK_JOB'] == sys.argv[2] == 'build'; assert 'PTK_ACTION' not in os.environ; p=Path('order.txt'); p.write_text((p.read_text() if p.exists() else '') + sys.argv[1]); print(sys.argv[1])"
    )
    job["params"] = {"word": {"default": "x"}}
    job["steps"][0]["run"]["run"].extend(["${params.word}", "${run.job}"])
    root = repository(
        tmp_path,
        jobs={"build": job},
        workflows={
            "verify": {
                "steps": [
                    {"one": {"job": "build", "params": {"word": "A"}}},
                    {"two": {"job": "build", "params": {"word": "B"}}},
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
    html = next(root.glob("_reports/workflows/verify/*/workflow.html")).read_text(
        encoding="utf-8"
    )
    assert "report.html</a>" in html and "report.json</a>" not in html
    assert "<title>Workflow - verify</title>" in html
    assert "<h1>Workflow - verify</h1>" in html
    assert [s["status"] for s in summary["steps"]] == ["passed", "passed"]
    reports = list(root.glob("_reports/workflows/verify/*/jobs/*/report.json"))
    assert len(reports) == 2
    for report in reports:
        data = json.loads(report.read_text())
        assert data["job"] == "build"
        assert "action" not in data
        child_html = report.with_suffix(".html").read_text(encoding="utf-8")
        assert "<h1>Job - build</h1>" in child_html
        log = Path(data["steps"][0]["log_file"])
        assert log.is_relative_to(report.parent)
        assert data["params"]["word"] in log.read_text()


def test_parallel_jobs_actually_overlap(tmp_path):
    def barrier(own, other):
        return command(
            f"from pathlib import Path; import time; Path('{own}').touch(); deadline=time.monotonic()+5\nwhile not Path('{other}').exists() and time.monotonic()<deadline: time.sleep(.02)\nassert Path('{other}').exists()"
        )

    root = repository(
        tmp_path,
        jobs={"a": barrier("a", "b"), "b": barrier("b", "a")},
        workflows={
            "verify": {
                "steps": [
                    {
                        "checks": {
                            "parallel": True,
                            "steps": [
                                {"a": {"job": "a"}},
                                {"b": {"job": "b"}},
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
        jobs={
            "fail": command("raise SystemExit(1)"),
            "after": command("from pathlib import Path; Path('after').touch()"),
        },
        workflows={
            "verify": {
                "steps": [
                    {"broken": {"job": "fail", "continue_on_error": continued}},
                    {"next": {"job": "after"}},
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
        ({"job": "missing"}, "unknown job"),
        ({"repo": "missing", "job": "build"}, "not a configured member"),
        ({"job": "build", "params": {"unknown": 1}}, "unknown parameter"),
        ({"job": "restricted"}, "maintainer-only"),
    ],
)
def test_all_calls_are_preflighted_before_running(tmp_path, call, error):
    jobs = {
        "build": command("from pathlib import Path; Path('ran').touch()"),
        "restricted": {**command("print('secret')"), "audience": "maintainer"},
    }
    root = repository(
        tmp_path,
        jobs=jobs,
        workflows={"verify": {"steps": [{"first": {"job": "build"}}, {"bad": call}]}},
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
    write_project(
        root / ".main.ptk.yml",
        {**read_project(root / ".main.ptk.yml"), "jobs": {"a": a, "b": a}},
    )
    write_workflows(
        (root / "config/workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump(
                {
                    "workflows": {
                        "bad": {"parallel": True, "steps": [{"one": "a"}, {"two": "b"}]}
                    }
                }
            )
        )["workflows"],
    )
    result = invoke(root, "workflow", "dry-run", "bad")
    assert result.exit_code != 0 and "uv project environment" in result.output


def test_vmr_targets_keep_environment_and_reports_and_have_editor_tasks(
    tmp_path, monkeypatch
):
    root = tmp_path
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [a, b]\n")
    for alias in ("a", "b"):
        job = command(
            "import os; from pathlib import Path; Path('selected').write_text(os.environ['IDENTITY'])"
        )
        repository(
            root / alias,
            alias,
            jobs={"build": job},
            workflows={"local": {"steps": [{"build": "build"}]}},
            extra={"environment": {"set": {"IDENTITY": alias}}},
        )
    write_workflows(
        (root / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump(
                {
                    "workflows": {
                        "all": {
                            "parallel": True,
                            "steps": [
                                {"a": {"repo": "a", "job": "build"}},
                                {"b": {"repo": "b", "job": "build"}},
                            ],
                        }
                    }
                }
            )
        )["workflows"],
    )
    monkeypatch.chdir(root)
    for target in (root, root / "a", root / "b"):
        grant_maintainer(target)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
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
    assert workflow["command"] == "ptk"
    assert workflow["args"] == ["a", "workflow", "run", "local"]
    # Windows can canonicalize ancestor capitalization (for example pytest-of-USER).
    assert Path(workflow["options"]["cwd"]).samefile(root)
    assert (
        len(list((root / "_reports/workflows/all").glob("*/jobs/*/report.html"))) == 2
    )


@pytest.mark.parametrize("level", ["job", "step"])
def test_parallel_python_calls_use_their_resolved_venv_paths(tmp_path, level):
    jobs = {}
    for name in ("a", "b"):
        job = command("pass")
        step = job["steps"][0]["run"]
        step["python"] = {"project": "."}
        job["env"] = {"UV_PROJECT_ENVIRONMENT": "${project.root}/shared"}
        target = job if level == "job" else step
        target["env"] = {
            "UV_PROJECT_ENVIRONMENT": f"${{project.root}}/.ptk/venvs/{name}"
        }
        jobs[name] = job
    root = repository(
        tmp_path,
        jobs=jobs,
        workflows={"verify": {"parallel": True, "steps": [{"a": "a"}, {"b": "b"}]}},
    )
    preview = invoke(root, "workflow", "dry-run", "verify")
    assert preview.exit_code == 0, preview.output
    target = jobs["b"] if level == "job" else jobs["b"]["steps"][0]["run"]
    target["env"]["UV_PROJECT_ENVIRONMENT"] = "${project.root}/.ptk/venvs/b/../a"
    write_project(
        root / ".main.ptk.yml", {**read_project(root / ".main.ptk.yml"), "jobs": jobs}
    )
    collision = invoke(root, "workflow", "dry-run", "verify")
    assert collision.exit_code == 2 and "uv project environment" in collision.output


def test_source_locations_and_workflow_name_validation(tmp_path):
    root = repository(tmp_path)
    folder = root / "config/workflows"
    folder.mkdir(exist_ok=True)
    file = folder / "verify.ptk.yml"
    file.write_text("steps:\n  - build: {acton: build}\n")
    result = invoke(root, "setup", "config", "validate")
    assert result.exit_code != 0
    assert "verify.ptk.yml:2" in result.output and "acton" in result.output
    file.unlink()
    nested = folder / "bad/name.ptk.yml"
    nested.parent.mkdir()
    nested.write_text("steps: [{build: build}]")
    result = invoke(root, "workflow", "list")
    assert result.exit_code != 0 and "directly in this directory" in result.output


@pytest.mark.parametrize("body", ["build", {"job": "build"}])
def test_entry_named_name_is_a_normal_job_call(tmp_path, body):
    root = repository(tmp_path, workflows={"verify": {"steps": [{"name": body}]}})
    result = invoke(root, "workflow", "dry-run", "verify")
    assert result.exit_code == 0 and "name: app/build" in result.output, result.output


def test_secret_parameters_cannot_be_embedded_in_workflow_yaml(tmp_path):
    job = command("from pathlib import Path; Path('ran').touch()")
    job["params"] = {"token": {"type": "secret"}}
    root = repository(
        tmp_path,
        jobs={"build": job},
        workflows={
            "verify": {
                "steps": [
                    {"build": {"job": "build", "params": {"token": "hidden-value"}}}
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
    grant_maintainer(root)
    allowed = invoke(root, "workflow", "run", "verify", env={"PTK_ROLE": ""})
    assert allowed.exit_code == 0, allowed.output
    for options, visible in (
        ([], True),
        (["--users-only"], False),
    ):
        result = invoke(
            root, "setup", "vscode", "tasks", *options, env={"PTK_ROLE": ""}
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
    grant_maintainer(root)
    assert invoke(root, "setup", "vscode", "tasks", env={"PTK_ROLE": ""}).exit_code == 0
    assert (
        invoke(
            root, "setup", "vscode", "tasks", "--check", env={"PTK_ROLE": ""}
        ).exit_code
        == 0
    )
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
        ["workflow", "run", "frontend/all"],
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
        ([], {"PTK_CI": "1"}),
        ([], {"PTK_CI": "", "GITHUB_ACTIONS": "true"}),
    ],
)
def test_workflow_execution_is_local_only(tmp_path, ci_args, env, opened_reports):
    root = repository(
        tmp_path,
        jobs={"build": command("from pathlib import Path; Path('ran').touch()")},
        workflows={"verify": {"steps": [{"build": "build"}]}},
    )
    result = invoke(root, *ci_args, "workflow", "run", "verify", env=env)
    assert result.exit_code != 0 and "locally only" in result.output
    assert not (root / "ran").exists()
    preview = invoke(root, *ci_args, "workflow", "dry-run", "verify", env=env)
    assert preview.exit_code == 0, preview.output
    assert opened_reports == []
