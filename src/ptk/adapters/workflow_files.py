"""Workflow-only documents and immutable run summaries."""

import json
import shutil
from dataclasses import asdict
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


def write_workflow_report(
    result, target: Path, *, owner_variant=None, children=None, context=None
) -> Path:
    from .reporting.workflow_html import render

    children, context = children or {}, context or {}
    target.mkdir(parents=True, exist_ok=True)
    page, graph = render(
        result, target, owner_variant=owner_variant, children=children, context=context
    )
    (target / "workflow.json").write_text(
        json.dumps(
            {
                **asdict(result),
                "owner_variant": owner_variant,
                "context": context,
                "children": {key: asdict(report) for key, report in children.items()},
                "graph": graph,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output = target / "workflow.html"
    output.write_text(page, encoding="utf-8")
    diagnostic_page, _ = render(
        result,
        target,
        owner_variant=owner_variant,
        children=children,
        context=context,
        diagnostics_only=True,
    )
    (target / "diagnostics.html").write_text(diagnostic_page, encoding="utf-8")
    return output


def snapshot_logs(summary: dict, target: Path) -> dict:
    """Keep child report links valid when the same job is called again."""
    from .reporting.importers import step_folders

    inputs = target / "inputs"
    source_reports = summary.get("reports_dir")
    if source_reports:
        for folder in step_folders(
            [
                step["step"]
                for step in summary.get("steps", [])
                if step.get("report", True)
            ]
        ):
            source = Path(source_reports) / folder
            if source.is_dir():
                shutil.copytree(source, inputs / folder, dirs_exist_ok=True)
    summary = {
        **summary,
        "reports_dir": str(inputs),
        "log_dir": str(target / "logs"),
        "steps": [dict(step) for step in summary.get("steps", [])],
    }
    for index, step in enumerate(summary["steps"]):
        source = Path(step.get("log_file") or "")
        if step.get("log_file") and source.is_file():
            destination = target / "logs" / f"{index}.log"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            step["log_file"] = str(destination)
    upload = summary.get("upload_file")
    if upload and Path(upload).is_file():
        destination = target / "upload.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(upload, destination)
        summary["upload_file"] = str(destination)
    return summary
