"""VS Code tasks for the configured actions (pure).

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
class TaskAction:
    name: str
    help: str
    is_default: bool
    passthrough: bool


def build_tasks(
    actions: list[TaskAction],
    *,
    command: str,
    variants: list[str],
    default_variant: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    for action in actions:
        args = [action.name]
        if variants:
            args += ["-V", f"${{input:{VARIANT_INPUT}}}"]
        task: dict[str, Any] = {
            "label": TASK_PREFIX + action.name,
            "type": "shell",
            "command": command,
            "args": args,
            "group": {"kind": "build", "isDefault": True}
            if action.is_default
            else "build",
            "problemMatcher": [],
        }
        if action.help:
            task["detail"] = action.help.splitlines()[0]
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
