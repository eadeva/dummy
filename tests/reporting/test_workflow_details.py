"""Workflow evidence and nested graphs are snapshots, with no invented execution."""

import json

from tests.project_files import read_project, write_project
from tests.workflows.test_cli import command, invoke, repository


def test_workflow_snapshots_steps_hidden_details_and_blocked_jobs(tmp_path):
    failing = command("print('ERROR: project failure'); raise SystemExit(1)")
    failing["steps"]["private"] = {
        "run": "echo private-output",
        "report": False,
        "needs": "run",
    }
    root = repository(
        tmp_path,
        jobs={"build": failing, "package": command("print('never runs')")},
        workflows={
            "verify": {
                "jobs": {
                    "build": {"job": "build"},
                    "package": {"job": "package", "needs": "build"},
                }
            }
        },
    )
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 1, result.output
    report_file = next(root.glob("_reports/workflows/verify/*/workflow.json"))
    recorded = report_file.read_text()
    data = json.loads(recorded)
    graph = data["graph"]["nodes"]
    assert graph[1]["needs"] == ["build"]
    children = graph[0]["children"]["nodes"]
    assert children[1]["status"] == "hidden" and children[1]["needs"] == ["run"]
    assert "target" not in children[1] and "duration" not in children[1]
    assert data["children"]["package"]["steps"][0]["status"] == "not_run"
    assert (
        data["children"]["package"]["steps"][0]["message"]
        == "blocked by needs: build (failed)"
    )
    page = report_file.with_suffix(".html").read_text()
    assert "private-output" not in page and "private-output" not in recorded
    assert "project failure" in page
    assert 'data-source="log"' in page and 'data-source="execution"' in page
    assert "Expand all jobs" in page
    child = report_file.parent / "jobs/build/report.html"
    assert "Back to workflow verify" in child.read_text()
    log = data["children"]["build"]["steps"][0]["log_file"]
    assert str(report_file.parent) in log
    config = root / ".main.ptk.yml"
    changed = read_project(config)
    changed["jobs"]["build"]["steps"] = {"replacement": {"run": "echo changed"}}
    write_project(config, changed)
    assert invoke(root, "build").exit_code == 0
    assert report_file.read_text() == recorded
    assert "replacement" not in report_file.with_suffix(".html").read_text()


def test_workspace_children_keep_equal_step_names_and_independent_variants(tmp_path):
    from tests.project_files import write_workflows

    for alias in ("one", "two"):
        repository(tmp_path / alias, alias, jobs={"build": command("print('hello')")})
    (tmp_path / ".main.ptk.yml").write_text(
        "virtual_monorepo: true\nmembers: [one, two]\n"
    )
    write_workflows(
        tmp_path / "workflows",
        {
            "verify": {
                "jobs": {"first": {"job": "one:build"}, "second": {"job": "two:build"}}
            }
        },
    )
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    path = next(tmp_path.glob("_reports/workflows/verify/*/workflow.json"))
    data = json.loads(path.read_text())
    first, second = data["graph"]["nodes"]
    assert (
        first["children"]["nodes"][0]["id"]
        == second["children"]["nodes"][0]["id"]
        == "run"
    )
    assert (
        first["children"]["nodes"][0]["target"]
        != second["children"]["nodes"][0]["target"]
    )
    assert data["context"]["workspace"] is True
    page = path.with_suffix(".html").read_text()
    assert "[default][one:build]" in page and "[default][two:build]" in page
