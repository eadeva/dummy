"""Tree projections and report graphs preserve dependency meaning and evidence."""

import io
import json
import re
from types import SimpleNamespace

from rich.console import Console

from ptk.adapters import graph_html
from ptk.adapters.reporting.html import render
from ptk.adapters.workflow_files import write_workflow_report
from ptk.application.use_cases.workflow import WorkflowJobResult, WorkflowResult
from ptk.domain.execution.model import Status
from ptk.domain.graphs import describe_graph
from ptk.domain.reporting.model import from_summary
from ptk.drivers.cli import graphs


def nodes(**dependencies):
    return {name: SimpleNamespace(needs=needs) for name, needs in dependencies.items()}


def graph_data(page):
    return json.loads(
        re.search(r'class="ptk-graph-data">(.*?)</script>', page, re.DOTALL)[1]
    )


def test_tree_preserves_joins_disconnected_targets_and_authored_order():
    graph = describe_graph(
        nodes(
            setup=[],
            right=["setup"],
            left=["setup"],
            package=["left", "right"],
            docs=[],
        )
    )
    assert graph["tree"] == [
        {"id": "setup", "parent": None, "shared": False},
        {"id": "right", "parent": 0, "shared": False},
        {"id": "package", "parent": 1, "shared": False},
        {"id": "left", "parent": 0, "shared": False},
        {"id": "package", "parent": 3, "shared": True},
        {"id": "docs", "parent": None, "shared": False},
    ]
    assert [node["id"] for node in graph["nodes"]] == [
        "setup",
        "right",
        "left",
        "package",
        "docs",
    ]
    assert describe_graph({}) == {"nodes": [], "tree": []}


def test_tree_expansion_is_bounded_for_deep_and_repeated_dependencies():
    chain = {
        str(index): SimpleNamespace(needs=[str(index - 1)] if index else [])
        for index in range(1500)
    }
    assert len(describe_graph(chain)["tree"]) == 1500
    shared = nodes(start=[])
    previous = ["start"]
    for index in range(30):
        current = [f"left{index}", f"right{index}"]
        shared.update({name: SimpleNamespace(needs=previous) for name in current})
        previous = current
    graph = describe_graph(shared)
    assert len(graph["tree"]) == sum(len(node.needs) for node in shared.values()) + 1
    assert sum(not entry["shared"] for entry in graph["tree"]) == len(shared)


def test_terminal_tree_shows_shared_references_and_partial_run(tmp_path, monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr(
        graphs, "console", Console(file=output, width=120, color_system=None)
    )
    target = graphs.show_graph(
        tmp_path,
        "build",
        "job",
        nodes(setup=[], left=["setup"], right=["setup"], package=["left", "right"]),
        selected={"package"},
        variant="debug",
        only_step="package",
    )
    text = output.getvalue()
    assert (
        text.index("setup  not selected")
        < text.index("left  not selected")
        < text.index("package  selected")
    )
    assert text.count("needs all: left, right") == 2
    assert text.count("shared — shown above") == 1
    assert "prerequisites not run: left, right, setup" in text
    assert "debug" in text
    graph = graph_data(target.read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == 4
    assert sum(node["selected"] for node in graph["nodes"]) == 1


def test_workflow_tree_reads_in_execution_direction_without_duplicate_labels(
    tmp_path, monkeypatch
):
    output = io.StringIO()
    monkeypatch.setattr(
        graphs, "console", Console(file=output, width=120, color_system=None)
    )
    workflow = nodes(check=[], test=["check"], package=["test"], docs=[])
    for name, node in workflow.items():
        node.job = name
    target = graphs.show_graph(tmp_path, "verify", "workflow", workflow)
    text = output.getvalue()
    assert "prerequisites → dependents" in text
    tree = graph_data(target.read_text(encoding="utf-8"))["tree"]
    assert tree == [
        {"id": "check", "parent": None, "shared": False},
        {"id": "test", "parent": 0, "shared": False},
        {"id": "package", "parent": 1, "shared": False},
        {"id": "docs", "parent": None, "shared": False},
    ]
    assert (
        text.index("check")
        < text.index("test")
        < text.index("package")
        < text.index("docs")
    )
    for name in workflow:
        assert f"{name}  {name}" not in text


def test_independent_roots_keep_all_join_edges():
    graph = describe_graph(
        nodes(left=[], right=[], join=["left", "right"], after=["join"])
    )
    assert graph["tree"] == [
        {"id": "left", "parent": None, "shared": False},
        {"id": "join", "parent": 0, "shared": False},
        {"id": "after", "parent": 1, "shared": False},
        {"id": "right", "parent": None, "shared": False},
        {"id": "join", "parent": 3, "shared": True},
    ]
    assert graph["nodes"][2]["needs"] == ["left", "right"]


def test_job_report_records_all_edges_but_hides_disabled_step_details():
    summary = {
        "context": {
            "selection": {
                "only_step": "test",
                "omitted_dependencies": ["configure", "build"],
            }
        },
        "steps": [
            {
                "step": "configure",
                "kind": "run",
                "needs": [],
                "status": "skipped",
                "message": "not selected",
            },
            {
                "step": "build",
                "kind": "run",
                "needs": ["configure"],
                "status": "skipped",
                "report": False,
                "message": "private detail",
                "command": "private command",
            },
            {
                "step": "test",
                "kind": "run",
                "needs": ["build"],
                "status": "failed",
                "allowed_failure": True,
                "duration": 2,
            },
        ],
    }
    report = from_summary(summary, [])
    assert [step.label for step in report.steps] == ["configure", "test"]
    page = render(report)
    assert '<details class="ptk-graph">' in page
    assert "private detail" not in page and "private command" not in page
    graph = graph_data(page)
    assert [node["id"] for node in graph["nodes"]] == ["configure", "build", "test"]
    assert graph["nodes"][1] == {
        "id": "build",
        "needs": ["configure"],
        "status": "hidden",
        "message": "Step details excluded by report: false",
    }
    assert graph["nodes"][2]["allowed_failure"] is True
    assert "prerequisites not run: configure, build" in graph["notice"]


def test_workflow_report_preserves_results_targets_variants_and_joins(tmp_path):
    result = WorkflowResult(
        "delivery",
        Status.CANCELLED,
        4,
        [
            WorkflowJobResult(
                "build",
                Status.PASSED,
                repo="engine",
                job="build",
                variant="debug",
                duration=2,
            ),
            WorkflowJobResult(
                "tests",
                Status.FAILED,
                repo="engine",
                job="test",
                needs=["build"],
                allowed_failure=True,
            ),
            WorkflowJobResult(
                "docs",
                Status.CANCELLED,
                repo="docs",
                job="build",
                needs=["build"],
                message="cancelled",
            ),
            WorkflowJobResult(
                "package",
                Status.SKIPPED,
                repo="engine",
                job="package",
                needs=["tests", "docs"],
            ),
        ],
    )
    target = write_workflow_report(result, tmp_path)
    page = target.read_text(encoding="utf-8")
    assert '<details class="ptk-graph">' in page
    graph = graph_data(page)
    assert len(graph["nodes"]) == 4
    assert sum(len(node["needs"]) for node in graph["nodes"]) == 4
    assert graph["nodes"][0]["label"] == "engine:build"
    assert graph["nodes"][0]["variant"] == "debug"
    assert graph["nodes"][1]["allowed_failure"] is True
    assert [node["status"] for node in graph["nodes"]] == [
        "passed",
        "failed",
        "cancelled",
        "skipped",
    ]
    assert json.loads((tmp_path / "workflow.json").read_text())["jobs"][3]["needs"] == [
        "tests",
        "docs",
    ]


def test_graph_serialization_keeps_script_like_text_as_data():
    graph = describe_graph(nodes(build=[]))
    graph["nodes"][0]["label"] = (
        '</script><script>window.injected=true</script> & "text"'
    )
    page = graph_html.render(graph, "<title>")
    assert graph_data(page) == graph
    assert "<script>window.injected" not in page
    assert "&lt;title&gt;" in page
    assert "<script src=" not in page and "<link " not in page
