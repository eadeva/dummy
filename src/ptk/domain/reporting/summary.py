"""The canonical run summary (``run.json``) - the source of every report (pure)."""

from __future__ import annotations

from typing import Any

from ..execution.model import ActionPlan, RunResult, StepResult
from ..layout import NO_VARIANT

SUMMARY_VERSION = 1


def step_dict(result: StepResult) -> dict[str, Any]:
    data: dict[str, Any] = {
        "step": result.label,
        "kind": result.kind,
        "status": result.status.value,
        "start": round(result.start, 3),
        "duration": round(result.duration, 3),
    }
    for key in ("exit_code", "message", "command", "log_file"):
        value = getattr(result, key)
        if value not in (None, ""):
            data[key] = value
    if result.attempts > 1:
        data["attempts"] = result.attempts
    if result.allowed_failure:
        data["allowed_failure"] = True
    return data


def header(plan: ActionPlan) -> dict[str, Any]:
    return {
        "summary_version": SUMMARY_VERSION,
        "run_id": plan.run_id,
        "project": plan.project,
        "action": plan.action,
        "variant": plan.variant or NO_VARIANT,
        "params": plan.params,
        "param_sources": plan.param_sources,
        "reports_dir": plan.dirs.get("reports_dir"),
        "log_dir": plan.dirs.get("log_dir"),
    }


def run_summary(plan: ActionPlan, result: RunResult) -> dict[str, Any]:
    hidden = [s.path for s in plan.walk() if not s.spec.report]
    return {
        **header(plan),
        "status": result.status.value,
        "started_at": result.started_at,
        "duration": round(result.duration, 3),
        "steps": [
            {**step_dict(r), "report": not any(r.path[: len(p)] == p for p in hidden)}
            for r in result.walk()
        ],
    }
