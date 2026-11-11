"""Workflow execution with real portable jobs and bounded VMR discovery."""

import json
import sys
from pathlib import Path

import pytest
import yaml
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project, write_workflows

from ptk.drivers.cli.main import cli


def command(code):
    return {"steps": {"run": {"run": [sys.executable, "-c", code]}}}


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
    return CliRunner(env={"PTK_ROLE": "user", "PTK_CX": "0", **(env or {})}).invoke(
        cli, [*args], catch_exceptions=False, cwd=root
    )


def summaries(root):
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in root.rglob("workflow.json")
    ]


def test_discovery_preview_then_sequential_calls_and_immutable_reports(tmp_path):
    job = command(
        "from pathlib import Path; import os, sys; assert os.environ['PTK_JOB'] == sys.argv[2]; assert sys.argv[2] in ('build', 'test'); assert 'PTK_ACTION' not in os.environ; p=Path('order.txt'); p.write_text((p.read_text() if p.exists() else '') + sys.argv[1]); print(sys.argv[1])"
    )
    job["params"] = {"word": {"default": "x"}}
    job["steps"]["run"]["run"].extend(["${params.word}", "${run.job}"])
    root = repository(
        tmp_path,
        jobs={"build": job, "test": job},
        workflows={
            "verify": {
                "jobs": {
                    "build": {"params": {"word": "A"}},
                    "test": {"params": {"word": "B"}, "needs": ["build"]},
                }
            }
        },
    )
    assert "verify" in invoke(root, "workflow", "list").output
    assert "params:" in invoke(root, "workflow", "show", "verify").output
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    preview = invoke(root, "workflow", "run", "verify", "--dry-run")
    assert preview.exit_code == 0, preview.output
    assert (
        sorted(
            p.relative_to(root)
            for p in root.rglob("*")
            if p.relative_to(root).parts[0] != ".ptk"
        )
        == before
    )
    assert (root / ".ptk/graphs/workflow-verify.html").is_file()
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    assert (root / "order.txt").read_text() == "AB"
    [summary] = summaries(root)
    assert summary["status"] == "passed"
    html = next(root.glob("_reports/workflows/verify/*/workflow.html")).read_text(
        encoding="utf-8"
    )
    assert "report.html</a>" in html and "report.json</a>" in html
    assert "<title>Workflow - verify</title>" in html
    assert "<h1>Workflow - verify</h1>" in html
    assert [s["status"] for s in summary["jobs"]] == ["passed", "passed"]
    reports = list(root.glob("_reports/workflows/verify/*/jobs/*/report.json"))
    assert len(reports) == 2
    for report in reports:
        data = json.loads(report.read_text())
        assert data["job"] in {"build", "test"}
        assert "action" not in data
        child_html = report.with_suffix(".html").read_text(encoding="utf-8")
        assert f"<h1>Job - {data['job']}</h1>" in child_html
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
        workflows={"verify": {"jobs": {"a": {}, "b": {}}}},
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
                "jobs": {
                    "fail": {"continue_on_error": continued},
                    "after": {"needs": ["fail"]},
                }
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == (0 if continued else 1), result.output
    assert (root / "after").exists() is continued
    [summary] = summaries(root)
    assert summary["jobs"][1]["status"] == ("passed" if continued else "skipped")


@pytest.mark.parametrize(
    "call,error",
    [
        ({"job": "missing"}, "unknown job"),
        ({"job": "missing:build"}, "not a configured member"),
        ({"job": "build", "params": {"unknown": 1}}, "unknown parameter"),
        ({"job": "restricted"}, "maintainer-only"),
    ],
)
def test_all_calls_are_preflighted_before_running(tmp_path, call, error):
    jobs = {
        "build": command("from pathlib import Path; Path('ran').touch()"),
        "first": command("from pathlib import Path; Path('ran').touch()"),
        "restricted": {**command("print('secret')"), "audience": "maintainer"},
    }
    root = repository(
        tmp_path,
        jobs=jobs,
        workflows={
            "verify": {
                "jobs": {
                    "first": {},
                    call["job"]: {
                        **{k: v for k, v in call.items() if k != "job"},
                        "needs": ["first"],
                    },
                }
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code != 0 and error in result.output, result.output
    assert not (root / "ran").exists()
    assert not (root / "_reports").exists()


def test_reject_parallel_output_and_uv_environment_collisions(tmp_path):
    root = repository(
        tmp_path,
        workflows={"bad": {"jobs": {"build": {}, "app:build": {}}}},
    )
    result = invoke(root, "workflow", "run", "bad", "--dry-run")
    assert result.exit_code != 0 and "only be chosen once per workflow" in result.output
    a = command("pass")
    a["steps"]["run"]["python"] = {"project": "."}
    write_workflows(
        (root / "config/workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump({"workflows": {"bad": {"jobs": {"a": {}, "b": {}}}}})
        )["workflows"],
    )
    write_project(
        root / ".main.ptk.yml",
        {**read_project(root / ".main.ptk.yml"), "jobs": {"a": a, "b": a}},
    )
    result = invoke(root, "workflow", "run", "bad", "--dry-run")
    assert result.exit_code != 0 and "uv project environment" in result.output


def test_vmr_targets_keep_environment_and_reports(tmp_path, monkeypatch):
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
            workflows={"local": {"jobs": {"build": {}}}},
            extra={"environment": {"set": {"IDENTITY": alias}}},
        )
    write_workflows(
        (root / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump(
                {"workflows": {"all": {"jobs": {"a:build": {}, "b:build": {}}}}}
            )
        )["workflows"],
    )
    monkeypatch.chdir(root)
    for target in (root, root / "a", root / "b"):
        grant_maintainer(target)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CX": "0"})
    for args in (
        ["workflow", "list"],
        ["workflow", "run", "all"],
        ["workflow", "run", "a/local"],
        ["a", "workflow", "run", "local", "--dry-run"],
    ):
        result = runner.invoke(cli, args, catch_exceptions=False)
        assert result.exit_code == 0, result.output
    for alias in ("a", "b"):
        assert (root / alias / "selected").read_text() == alias
    assert (
        len(list((root / "_reports/workflows/all").glob("*/jobs/*/report.html"))) == 2
    )


@pytest.mark.parametrize("level", ["job", "step"])
def test_parallel_python_calls_use_their_resolved_venv_paths(tmp_path, level):
    jobs = {}
    for name in ("a", "b"):
        job = command("pass")
        step = job["steps"]["run"]
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
        workflows={"verify": {"jobs": {"a": {}, "b": {}}}},
    )
    preview = invoke(root, "workflow", "run", "verify", "--dry-run")
    assert preview.exit_code == 0, preview.output
    target = jobs["b"] if level == "job" else jobs["b"]["steps"]["run"]
    target["env"]["UV_PROJECT_ENVIRONMENT"] = "${project.root}/.ptk/venvs/b/../a"
    write_project(
        root / ".main.ptk.yml", {**read_project(root / ".main.ptk.yml"), "jobs": jobs}
    )
    collision = invoke(root, "workflow", "run", "verify", "--dry-run")
    assert collision.exit_code == 2 and "uv project environment" in collision.output


def test_source_locations_and_workflow_name_validation(tmp_path):
    root = repository(tmp_path)
    folder = root / "config/workflows"
    folder.mkdir(exist_ok=True)
    file = folder / "verify.ptk.yml"
    file.write_text("jobs:\n  build:\n    acton: build\n")
    result = invoke(root, "validate")
    assert result.exit_code != 0
    assert "verify.ptk.yml:3" in result.output and "acton" in result.output
    file.unlink()
    nested = folder / "bad/name.ptk.yml"
    nested.parent.mkdir()
    nested.write_text("jobs:\n  build:\n    job: build\n")
    result = invoke(root, "workflow", "list")
    assert result.exit_code != 0 and "directly in this directory" in result.output


@pytest.mark.parametrize("body", [{}])
def test_entry_named_name_is_a_normal_job_call(tmp_path, body):
    root = repository(
        tmp_path,
        jobs={"name": command("pass")},
        workflows={"verify": {"jobs": {"name": body}}},
    )
    result = invoke(root, "workflow", "run", "verify", "--dry-run")
    assert result.exit_code == 0 and "name: app:name" in result.output, result.output


def test_secret_parameters_cannot_be_embedded_in_workflow_yaml(tmp_path):
    job = command("from pathlib import Path; Path('ran').touch()")
    job["params"] = {"token": {"type": "secret"}}
    root = repository(
        tmp_path,
        jobs={"build": job},
        workflows={
            "verify": {"jobs": {"build": {"params": {"token": "hidden-value"}}}}
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 2 and "secret parameters" in result.output, result.output
    assert "hidden-value" not in result.output
    assert not (root / "ran").exists()


@pytest.mark.parametrize("command_policy", [False, True])
def test_maintainer_workflows_are_protected(tmp_path, command_policy):
    root = repository(
        tmp_path,
        workflows={
            "verify": {
                "audience": "all" if command_policy else "maintainer",
                "jobs": {"build": {}},
            }
        },
        extra={"command_audience": {"workflow": "maintainer"}}
        if command_policy
        else {},
    )
    denied = invoke(root, "workflow", "run", "verify")
    assert denied.exit_code != 0 and "maintainer-only" in denied.output, denied.output
    grant_maintainer(root)
    allowed = invoke(
        root, "maintainer", "workflow", "run", "verify", env={"PTK_ROLE": ""}
    )
    assert allowed.exit_code == 0, allowed.output


def test_maintainer_workflow_list_shows_all_and_users_only_their_own(tmp_path):
    root = repository(
        tmp_path,
        workflows={
            "verify": {"help": "Checks", "jobs": {"build": {}}},
            "release": {"audience": "maintainer", "jobs": {"build": {}}},
        },
    )
    user = invoke(root, "workflow", "list").output
    assert "verify: Checks" in user and "release" not in user
    grant_maintainer(root)
    listed = invoke(root, "maintainer", "workflow", "list", env={"PTK_ROLE": ""}).output
    assert "verify: Checks" in listed and "release (maintainer):" in listed
    empty = repository(tmp_path / "empty", workflows={})
    assert "no workflows" in invoke(empty, "workflow", "list").output


def test_published_example_runs_locally_without_github(tmp_path, monkeypatch):
    import shutil

    source = Path(__file__).resolve().parents[2] / "examples/workflows"
    target = tmp_path / "local vmr"
    shutil.copytree(source, target)
    monkeypatch.chdir(target)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CX": "0"})
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
    "cx_args,env",
    [
        ([], {"PTK_CX": "1"}),
        ([], {"PTK_CX": "", "GITHUB_ACTIONS": "true"}),
    ],
)
def test_workflow_execution_is_local_only(tmp_path, cx_args, env, opened_reports):
    root = repository(
        tmp_path,
        jobs={"build": command("from pathlib import Path; Path('ran').touch()")},
        workflows={"verify": {"jobs": {"build": {}}}},
    )
    result = invoke(root, *cx_args, "workflow", "run", "verify", env=env)
    assert result.exit_code != 0 and "locally only" in result.output
    assert not (root / "ran").exists()
    preview = invoke(root, *cx_args, "workflow", "run", "verify", "--dry-run", env=env)
    assert preview.exit_code == 0, preview.output
    assert opened_reports == []


def test_qualified_underscore_targets_and_invocation_ids_are_distinct(tmp_path):
    repository(
        tmp_path / "app",
        "my_repo",
        jobs={"job_name": command("print('qualified target')")},
        workflows={"local_flow": {"jobs": {"job_name": {}}}},
    )
    repository(tmp_path / "other", "other_repo", jobs={"job_name": command("pass")})
    (tmp_path / ".main.ptk.yml").write_text(
        "virtual_monorepo: true\nmembers: [app, other]\n"
    )
    write_workflows(
        tmp_path / "workflows",
        {
            "verify": {
                "jobs": {
                    "my_repo:job_name": {},
                    "other_repo:job_name": {
                        "needs": "my_repo:job_name",
                    },
                }
            }
        },
    )
    for name in ("verify", "my_repo/local_flow"):
        result = invoke(tmp_path, "workflow", "run", name, "--dry-run")
        assert result.exit_code == 0, result.output
        assert "my_repo:job_name" in result.output
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    [summary] = summaries(tmp_path)
    assert [job["id"] for job in summary["jobs"]] == [
        "my_repo:job_name",
        "other_repo:job_name",
    ]
    assert summary["jobs"][1]["needs"] == ["my_repo:job_name"]
    assert "steps" not in summary
    shown = invoke(tmp_path, "workflow", "show", "verify")
    assert shown.exit_code == 0
    assert (
        "other_repo:job_name"
        in yaml.safe_load(shown.output)["workflows"]["verify"]["jobs"]
    )


def test_workspace_calls_require_qualified_target_before_any_execution(tmp_path):
    repository(
        tmp_path / "app",
        jobs={"build": command("from pathlib import Path; Path('ran').touch()")},
    )
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    write_workflows(
        tmp_path / "workflows",
        {
            "verify": {
                "jobs": {
                    "app:build": {},
                    "build": {"needs": "app:build"},
                }
            }
        },
    )
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert (
        result.exit_code == 2 and "require a qualified job: REPO:JOB" in result.output
    )
    assert not (tmp_path / "app/ran").exists()


def test_dependency_errors_have_source_locations_and_prevent_execution(tmp_path):
    root = repository(
        tmp_path,
        jobs={"build": command("from pathlib import Path; Path('ran').touch()")},
    )
    file = root / "config/workflows/verify.ptk.yml"
    file.parent.mkdir()
    file.write_text("jobs:\n  first: {needs: second}\n  second: {needs: first}\n")
    for args in [("validate",), ("workflow", "run", "verify")]:
        result = invoke(root, *args)
        assert result.exit_code == 2
        assert "verify.ptk.yml:" in result.output
        assert "first -> second -> first" in result.output
    assert not (root / "ran").exists()


def test_skipped_report_explains_dependency_and_independent_branch_runs(tmp_path):
    root = repository(
        tmp_path,
        jobs={
            "fail": command("raise SystemExit(1)"),
            "after": command("from pathlib import Path; Path('after').touch()"),
            "independent": command(
                "from pathlib import Path; Path('independent').touch()"
            ),
        },
        workflows={
            "verify": {
                "jobs": {
                    "fail": {},
                    "after": {"needs": "fail"},
                    "independent": {},
                }
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 1, result.output
    assert (root / "independent").exists() and not (root / "after").exists()
    [summary] = summaries(root)
    assert summary["jobs"][1]["message"] == "blocked by needs: fail (failed)"
    html = next(root.glob("_reports/workflows/verify/*/workflow.html")).read_text()
    assert "<dt>Needs</dt>" in html and "blocked by needs: fail (failed)" in html
