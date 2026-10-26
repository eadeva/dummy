"""VS Code tasks for the configured jobs (pure).

ptk owns the tasks whose label starts with ``ptk: `` and the input
``ptkVariant``; everything else in ``tasks.json`` belongs to the user and is
kept as it is. Regenerating is idempotent, so ``--check`` can compare.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TASK_PREFIX = "ptk: "
VARIANT_INPUT = "ptkVariant"


@dataclass(frozen=True)
class TaskJob:
    name: str
    help: str
    is_default: bool
    passthrough: bool


def build_tasks(
    jobs: list[TaskJob],
    *,
    command: str,
    variants: list[str],
    default_variant: str | None,
    repository_alias: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    for job in jobs:
        args = (
            (["-V", f"${{input:{VARIANT_INPUT}}}"] if variants else [])
            + ([repository_alias] if repository_alias else [])
            + [
                "run",
                job.name,
            ]
        )
        task: dict[str, Any] = {
            "label": TASK_PREFIX + job.name,
            "type": "shell",
            "command": command,
            "args": args,
            "group": {"kind": "build", "isDefault": True}
            if job.is_default
            else "build",
            "problemMatcher": [],
        }
        if job.help:
            task["detail"] = job.help.splitlines()[0]
        tasks.append(task)
    inputs: list[dict[str, Any]] = []
    if variants:
        variant_input: dict[str, Any] = {
            "id": VARIANT_INPUT,
            "type": "pickString",
            "description": "ptk variant",
            "options": list(variants),
        }
        if default_variant:
            variant_input["default"] = default_variant
        inputs.append(variant_input)
    return tasks, inputs


def merge(
    document: dict[str, Any] | None,
    tasks: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """User tasks and inputs first (unchanged), then ptk's."""
    doc = dict(document or {})
    doc.setdefault("version", "2.0.0")
    user_tasks = [
        t
        for t in doc.get("tasks", [])
        if not str(t.get("label", "")).startswith(TASK_PREFIX)
    ]
    doc["tasks"] = [*user_tasks, *tasks]
    user_inputs = [i for i in doc.get("inputs", []) if i.get("id") != VARIANT_INPUT]
    if user_inputs or inputs:
        doc["inputs"] = [*user_inputs, *inputs]
    else:
        doc.pop("inputs", None)
    return doc


def workflow_tasks(
    workflows: list[tuple[str, str]],
    *,
    command: str,
    repository_alias: str | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "label": TASK_PREFIX + "workflow " + name,
            "type": "shell",
            "command": command,
            "args": ([repository_alias] if repository_alias else [])
            + ["workflow", "run", name],
            "group": "build",
            "problemMatcher": [],
            "detail": help_text.splitlines()[0]
            if help_text
            else f"Run workflow {name}",
        }
        for name, help_text in workflows
    ]
