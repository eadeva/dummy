"""Real dependency execution, inspection, concurrency and partial-run semantics."""

import os
import sys
import threading
from itertools import pairwise

import pytest
import yaml

from ptk.application.use_cases.run import Cancelled, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import PtkError
from ptk.domain.execution.model import Status
from ptk.domain.reporting.summary import run_summary
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def prepare(root, steps, *, max_workers=4, **request):
    write_project(
        root / ".main.ptk.yml",
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "graphs"},
                "jobs": {"go": {"steps": steps, "max_workers": max_workers}},
            },
            sort_keys=False,
        ),
    )
    app = create_app(environ=dict(os.environ))
    project = app.load_project.execute(root)
    return app, app.prepare_run(project).execute(
        project, RunRequest(job="go", **request)
    )


def command(code, **kwargs):
    return {"run": [sys.executable, "-c", code], "timeout": 10, **kwargs}


def test_ready_nodes_overlap_and_join(tmp_path):
    app, prepared = prepare(
        tmp_path,
        {
            "worker": command(
                "from pathlib import Path; import time; p=Path('ready'); exec('while not p.exists(): time.sleep(0.02)'); Path('done').touch()"
            ),
            "release": command("from pathlib import Path; Path('ready').touch()"),
            "join": command(
                "from pathlib import Path; assert Path('done').exists()",
                needs=["worker", "release"],
            ),
        },
    )
    result = app.run_job(prepared.project).execute(prepared)
    assert result.status is Status.PASSED
    assert [step.name for step in result.steps] == ["worker", "release", "join"]
    assert result.steps[2].start >= max(
        step.start + step.duration for step in result.steps[:2]
    )


@pytest.mark.parametrize("allowed", [False, True])
def test_failure_blocks_only_dependents(tmp_path, allowed):
    app, prepared = prepare(
        tmp_path,
        {
            "failure": command("raise SystemExit(7)", continue_on_error=allowed),
            "dependent": command("pass", needs="failure"),
            "independent": command("pass"),
        },
    )
    result = app.run_job(prepared.project).execute(prepared)
    assert result.steps[0].exit_code == 7
    assert result.steps[1].status is (Status.PASSED if allowed else Status.SKIPPED)
    assert result.steps[2].status is Status.PASSED
    assert result.status is (Status.PASSED if allowed else Status.FAILED)


def test_skipped_prerequisite_blocks_join_even_if_failure_allowed(tmp_path):
    app, prepared = prepare(
        tmp_path,
        {
            "first": {"uses": "echo", "when": "False", "continue_on_error": True},
            "join": {"uses": "echo", "needs": "first"},
            "free": {"uses": "echo"},
        },
    )
    result = app.run_job(prepared.project).execute(prepared)
    assert [s.status for s in result.steps] == [
        Status.SKIPPED,
        Status.SKIPPED,
        Status.PASSED,
    ]
    assert "first (skipped)" in result.steps[1].message


def test_worker_limit_without_implicit_order(tmp_path):
    app, prepared = prepare(
        tmp_path,
        {name: {"uses": "wait", "with": {"seconds": 0.08}} for name in ("a", "b", "c")},
        max_workers=1,
    )
    result = app.run_job(prepared.project).execute(prepared)
    assert all(s.status is Status.PASSED for s in result.steps)
    ordered = sorted(result.steps, key=lambda s: s.start)
    assert all(b.start >= a.start + a.duration for a, b in pairwise(ordered))


def test_cancel_reaches_running_and_pending_steps(tmp_path):
    app, prepared = prepare(
        tmp_path,
        {
            "worker": command("import time; time.sleep(30)"),
            "other": command("import time; time.sleep(30)"),
            "later": command("raise AssertionError('must not run')", needs="worker"),
        },
    )
    cancel = Cancelled()
    timer = threading.Timer(0.4, cancel.set)
    timer.start()
    try:
        result = app.run_job(prepared.project).execute(prepared, cancel=cancel)
    finally:
        timer.cancel()
    assert result.status is Status.CANCELLED
    assert all(s.status is Status.CANCELLED for s in result.steps)
    assert result.duration < 5


def test_to_uses_dependencies_instead_of_declaration_position(tmp_path):
    steps = {
        "target": {"uses": "echo", "needs": "first"},
        "unrelated": {"uses": "echo"},
        "first": {"uses": "echo"},
    }
    app, prepared = prepare(tmp_path, steps, end="target")
    result = app.run_job(prepared.project).execute(prepared)
    assert [s.status for s in result.steps] == [
        Status.PASSED,
        Status.SKIPPED,
        Status.PASSED,
    ]


def test_only_step_reports_omitted_prerequisites_and_preserves_root_cwd(tmp_path):
    app, prepared = prepare(
        tmp_path,
        {
            "setup": command("raise AssertionError('not selected')"),
            "target": command(
                "from pathlib import Path; assert Path('.main.ptk.yml').is_file()",
                needs="setup",
            ),
        },
        only_step="target",
    )
    result = app.run_job(prepared.project).execute(prepared)
    assert [s.status for s in result.steps] == [Status.SKIPPED, Status.PASSED]
    summary = run_summary(prepared.plan, result)
    assert summary["context"]["selection"]["omitted_dependencies"] == ["setup"]
    report = app.reports.build(prepared.project, summary)
    from ptk.adapters.reporting.html import render

    assert "Prerequisites not run: setup" in render(report)
    preview = CliRunner().invoke(
        cli, ["go", "--only-step", "target", "--dry-run"], cwd=tmp_path
    )
    assert preview.exit_code == 0, preview.output
    assert "prerequisites not run: setup" in preview.output


def test_known_step_directories_are_available_without_stored_outputs(tmp_path):
    _app, prepared = prepare(
        tmp_path,
        {
            "compile.one": {"uses": "echo"},
            "read": {
                "uses": "echo",
                "needs": "compile.one",
                "with": {"message": "${steps.compile.one.build_dir}"},
            },
        },
    )
    assert prepared.plan.steps[1].with_["message"] == str(
        tmp_path / "_builds/default/go/compile.one"
    )
    with pytest.raises(PtkError, match="unknown|unavailable"):
        prepare(
            tmp_path,
            {
                "read": {
                    "uses": "echo",
                    "with": {"message": "${steps.read.outputs.binary}"},
                }
            },
        )


def test_unordered_uv_project_steps_require_separate_environments(tmp_path):
    steps = {
        name: {"run": "python --version", "python": {"project": "."}}
        for name in ("a", "b")
    }
    with pytest.raises(PtkError, match="share uv project environment"):
        prepare(tmp_path, steps, dry_run=True)
    steps["b"]["needs"] = "a"
    prepare(tmp_path, steps, dry_run=True)


def test_graph_inspection_needs_no_parameters_credentials_or_process(tmp_path):
    _app, _prepared = prepare(
        tmp_path,
        {"first": {"uses": "echo"}, "next": {"uses": "echo", "needs": "first"}},
    )
    job = tmp_path / "jobs/go.ptk.yml"
    data = yaml.safe_load(job.read_text())
    data["params"] = {"message": {"required": True}}
    data["steps"]["first"] = {"run": "echo ${params.message}"}
    job.write_text(yaml.safe_dump(data))
    result = CliRunner().invoke(cli, ["go", "--graph"], cwd=tmp_path)
    assert result.exit_code == 0, result.output
    assert "dependency graph" in result.output
    page = (tmp_path / ".ptk/graphs/job-go.html").read_text()
    assert "<svg" in page and 'marker-end="url(#arrow)"' in page
    assert not (tmp_path / "_logs").exists()
    assert not (tmp_path / "_builds").exists()
    rejected = CliRunner().invoke(cli, ["go", "--from", "first"], cwd=tmp_path)
    assert rejected.exit_code == 2 and "No such option" in rejected.output
