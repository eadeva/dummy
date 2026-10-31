"""Generate deterministic graph/report fixtures for offline browser verification."""

import sys
from pathlib import Path
from types import SimpleNamespace

from ptk.adapters.graph_html import render as graph_page
from ptk.adapters.reporting.html import render
from ptk.adapters.workflow_files import write_workflow_report
from ptk.application.use_cases.workflow import WorkflowJobResult, WorkflowResult
from ptk.domain.execution.model import Status
from ptk.domain.graphs import describe_graph
from ptk.domain.reporting.model import from_summary


def generate(target):
    target.mkdir(parents=True, exist_ok=True)
    summary = {
        "project": "Engine",
        "job": "delivery",
        "variant": "debug",
        "status": "failed",
        "run_id": "graph-preview",
        "duration": 9,
        "steps": [
            {
                "step": "configure",
                "kind": "run",
                "needs": [],
                "status": "passed",
                "duration": 1,
            },
            {
                "step": "compile",
                "kind": "run",
                "needs": ["configure"],
                "status": "passed",
                "duration": 4,
            },
            {
                "step": "unit-tests",
                "kind": "run",
                "needs": ["compile"],
                "status": "failed",
                "duration": 2,
                "allowed_failure": True,
                "message": "Known failure <SDK>",
            },
            {
                "step": "documentation",
                "kind": "run",
                "needs": ["compile"],
                "status": "cancelled",
                "message": "</script><script>window.injected=true</script>",
            },
            {
                "step": "package",
                "kind": "run",
                "needs": ["unit-tests", "documentation"],
                "status": "skipped",
                "message": "Blocked by documentation",
            },
            {
                "step": "checks-with-a-long-name-that-must-not-be-truncated",
                "kind": "run",
                "needs": [],
                "status": "failed",
                "message": "Independent checks failed",
            },
        ],
    }
    report = from_summary(summary, [])
    (target / "job.html").write_text(render(report), encoding="utf-8")
    graph = {
        **report.graph,
        "nodes": [{**node, "label": node["id"]} for node in report.graph["nodes"]],
    }
    (target / "graph.html").write_text(
        graph_page(graph, "Job delivery · debug"), encoding="utf-8"
    )
    jobs = [
        WorkflowJobResult(
            step["step"],
            Status(step["status"]),
            repo="engine",
            job=step["step"],
            variant="debug",
            needs=step["needs"],
            allowed_failure=step.get("allowed_failure", False),
            message=step.get("message", ""),
        )
        for step in summary["steps"]
    ]
    write_workflow_report(WorkflowResult("verify", Status.CANCELLED, 9, jobs), target)
    children = {}
    for name in ("build", "test", "docs"):
        child_summary = {
            **summary,
            "job": name,
            "context": {
                "repository_alias": "engine",
                "ptk_version": "0.19.0",
                "versions": {"projects": {"engine": {"value": "1.2.3"}}},
            },
            "steps": [dict(step) for step in summary["steps"]],
        }
        child_summary["steps"][0]["report"] = False
        child_summary["steps"][0]["command"] = "hidden command must not appear"
        child_summary["steps"][2]["start"] = 4
        children[name] = from_summary(child_summary, [])
    nested_jobs = [
        WorkflowJobResult(
            "build",
            Status.PASSED,
            repo="engine",
            job="build",
            variant="debug",
            duration=4,
        ),
        WorkflowJobResult(
            "test",
            Status.FAILED,
            repo="engine",
            job="test",
            variant="debug",
            start=4,
            duration=2,
            needs=["build"],
        ),
        WorkflowJobResult(
            "docs",
            Status.PASSED,
            repo="docs",
            job="build",
            variant="release",
            duration=3,
        ),
        WorkflowJobResult(
            "publish",
            Status.SKIPPED,
            repo="engine",
            job="publish",
            needs=["test", "docs"],
            message="blocked by test",
        ),
    ]
    write_workflow_report(
        WorkflowResult("delivery", Status.FAILED, 6, nested_jobs),
        target / "expanded",
        owner_variant="debug",
        children=children,
        context={"run_id": "review", "started_at": "2026-10-31T10:00:00+01:00"},
    )
    wide = {f"target-{index}": SimpleNamespace(needs=["shared"]) for index in range(24)}
    wide["shared"] = SimpleNamespace(needs=[])
    (target / "wide.html").write_text(
        graph_page(describe_graph(wide), "Many targets"), encoding="utf-8"
    )
    (target / "empty.html").write_text(
        graph_page(describe_graph({}), "Empty graph"), encoding="utf-8"
    )


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
