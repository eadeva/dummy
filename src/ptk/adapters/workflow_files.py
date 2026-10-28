"""Workflow-only documents and immutable run summaries."""

import json
import os
import shutil
from dataclasses import asdict
from html import escape
from pathlib import Path

from ..application.use_cases.project import validation_problems
from ..domain.config.tree import to_plain
from ..domain.errors import ConfigError, Location, Problem
from ..domain.workflows import WorkflowFile, WorkflowSpec
from .config.discovery import checked_path
from .config.yaml_loader import YamlConfigReader


def read_workflows(folder: Path) -> WorkflowFile:
    """Workspace orchestration uses one section-scoped file per workflow."""
    workflows = {}
    if not folder.exists():
        return WorkflowFile(workflows={})
    checked_path(folder.parent, folder.name)
    for path in sorted(folder.iterdir()):
        checked_path(folder.parent, str(path.relative_to(folder.parent)))
        if not path.is_file() or not path.name.endswith(".ptk.yml"):
            raise ConfigError(
                [
                    Problem(
                        "expected <workflow>.ptk.yml directly in workflows/",
                        location=Location(str(path)),
                    )
                ]
            )
        tree = YamlConfigReader().read(path)
        problems = validation_problems(WorkflowSpec, tree, skip_unknown=False)
        if problems:
            raise ConfigError(problems)
        workflows[path.name.removesuffix(".ptk.yml")] = WorkflowSpec.model_validate(
            to_plain(tree)
        )
    return WorkflowFile(workflows=workflows)


def write_workflow_report(result, target: Path) -> Path:
    from .reporting.html import CSS, FILTER_SCRIPT, _cards

    target.mkdir(parents=True, exist_ok=True)
    (target / "workflow.json").write_text(
        json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8"
    )
    rows = []
    counts = {"Passed": 0, "Failed": 0, "Skipped": 0, "Cancelled": 0}

    def visit(step):
        if step.job:
            label = step.status.value.capitalize()
            if label in counts:
                counts[label] += 1
        links = []
        for report in step.reports:
            if Path(report).suffix.lower() != ".html":
                continue
            relative = os.path.relpath(report, target).replace(os.sep, "/")
            links.append(
                f'<a href="{escape(relative, quote=True)}">{escape(Path(report).name)}</a>'
            )
        cells = [
            step.path,
            step.repo,
            step.job,
            step.variant or "default",
            step.status.value + (" (allowed)" if step.allowed_failure else ""),
            f"{step.duration:.2f}s",
            step.message
            or (
                "Child report contains errors or could not be written"
                if step.report_errors
                else ""
            ),
        ]
        rows.append(
            "<tr>"
            + "".join(f"<td>{escape(str(c))}</td>" for c in cells)
            + f"<td>{' · '.join(links)}</td></tr>"
        )
        for child in step.children:
            visit(child)

    for step in result.steps:
        visit(step)
    titles = (
        "Step",
        "Repository",
        "Job",
        "Variant",
        "Result",
        "Duration",
        "Message",
        "Reports",
    )
    status = result.status.value
    title = escape(f"Workflow - {result.name}")
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{CSS}</style></head><body><main>"
        f'<header class="status"><h1>{title}</h1><span class="verdict {status}">{status}</span></header>'
        + _cards(
            counts,
            tones={
                "Passed": "passed",
                "Failed": "failed",
                "Skipped": "skipped",
                "Cancelled": "warning",
            },
        )
        + f'<p class="meta">Job calls only; duration {result.duration:.2f}s. Open a child report for project, tool and test details.</p>'
        + '<div class="table-wrap"><table><tr>'
        + "".join(f"<th>{t}</th>" for t in titles)
        + "</tr>"
        + "".join(rows)
        + "</table></div></main>"
        + FILTER_SCRIPT
        + "</body></html>"
    )
    output = target / "workflow.html"
    output.write_text(page, encoding="utf-8")
    return output


def snapshot_logs(summary: dict, target: Path) -> dict:
    """Keep child report links valid when the same job is called again."""
    summary = {**summary, "steps": [dict(step) for step in summary.get("steps", [])]}
    for index, step in enumerate(summary["steps"]):
        source = Path(step.get("log_file") or "")
        if step.get("log_file") and source.is_file():
            destination = target / "logs" / f"{index}.log"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            step["log_file"] = str(destination)
    return summary
