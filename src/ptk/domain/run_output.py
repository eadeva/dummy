"""Run text and semantic roles shared by console and plain transcripts."""

import json
from collections import Counter
from dataclasses import dataclass

from .layout import NO_VARIANT


def one_line(value):
    return str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


# Each fragment carries a semantic role, never a terminal escape or markup.
Line = list[tuple[str, str]]
Block = list[Line]


def plain(block: Block) -> str:
    return "\n".join("".join(text for text, _role in row) for row in block)


def prefix(job, variant, step=None):
    return f"[{variant or NO_VARIANT}][{job}]" + (f"[{step}]" if step else "")


def contextual(identity, rows, role) -> Block:
    return [
        [(identity + " ", role), (line.expandtabs(8), "")]
        for row in rows
        for line in row.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]


def heading(kind, identity, *, result=None, width=80) -> Line:
    mark = "=" if kind == "WORKFLOW" else "-"
    label = kind + (" SUMMARY" if result is not None else "")
    row = [(f"{mark * 4} {label} {identity} | ", kind)]
    row += (
        outcome(result, duration=f"{result.duration:.1f}s")
        if result is not None
        else [("START", "")]
    )
    used = sum(len(text) for text, _role in row)
    row.append((" " + mark * max(4, width - used - 1), kind))
    return row


def start_block(kind, identity, rows, *, width=80) -> Block:
    return [heading(kind, identity, width=width), *contextual(identity, rows, kind)]


def step_block(identity, *, step=None, command=None, result=None) -> Block:
    row = [(identity + " STEP | ", "STEP")]
    row += outcome(result) if result is not None else [("START", "")]
    rows = step_rows(step, command) if step is not None else []
    if result is not None and result.message and result.message != str(result.status):
        rows.append(result.message)
    return [row, *contextual(identity, rows, "STEP")]


def project_version(plan):
    context = plan.report_context
    alias = context.get("repository_alias", plan.project)
    return (
        context.get("versions", {}).get("projects", {}).get(alias, {}).get("value")
        or "not configured"
    )


def variant_label(plan):
    data = plan.report_context.get("variant", {})
    name = plan.variant or f"{NO_VARIANT} (no variant model)"
    return name + (f" — {data['description']}" if data.get("description") else "")


def job_rows(plan, *, verbose=False):
    context = plan.report_context
    variant = context.get("variant", {})
    rows = [
        f"Project: {one_line(plan.project)} | Project version: {one_line(project_version(plan))}",
        f"Repository: {one_line(context.get('repository_alias', plan.project))} | PTK: {one_line(context.get('ptk_version') or 'not recorded')}",
        f"Variant: {one_line(variant_label(plan))}",
        f"Components: {len(variant.get('components', []))} | Resolved features: {len(variant.get('features', {}))}",
        f"Run: {plan.run_id} | Steps: {len(plan.steps)} | Max concurrent: {plan.max_workers}",
    ]
    workflow = context.get("workflow")
    if workflow:
        rows.append(
            f"Workflow: {one_line(workflow['name'])} | Invocation: {one_line(workflow['invocation'])}"
        )
    if plan.only_step:
        rows.append(
            f"Only step: {plan.only_step} | Prerequisites not run: {', '.join(plan.omitted_dependencies) or 'none'}. Required outputs must already exist."
        )
    if verbose and variant:
        rows.append("Inheritance: " + " → ".join(variant.get("chain", [])))
        rows.append(
            "Selected components: "
            + (", ".join(variant.get("components", [])) or "none")
        )
        rows.extend(
            f"  {name} = {json.dumps(value, ensure_ascii=False)}"
            for name, value in sorted(variant.get("features", {}).items())
        )
    return rows


def step_rows(step, command):
    rows = []
    if step.title != step.name:
        rows.append(f"Title: {one_line(step.title)}")
    if step.spec.generators:
        rows.append("Generators: " + ", ".join(step.spec.generators))
    if command:
        rows.append(f"Command: {command}")
    return rows


def display_status(result):
    return "reused" if getattr(result, "reused_from", "") else str(result.status)


def elapsed(result):
    return (
        "—"
        if display_status(result) in ("skipped", "pending", "reused")
        else f"{result.duration:.1f}s"
    )


def outcome(result, *, duration=None) -> Line:
    row = [
        (display_status(result).upper(), display_status(result)),
        (f" | {duration if duration is not None else elapsed(result)}", ""),
    ]
    if getattr(result, "allowed_failure", False):
        row.append((" | allowed failure", "warning"))
    return row


@dataclass(frozen=True)
class SummaryEntry:
    identity: str
    status: str
    duration: float
    allowed_failure: bool
    detail: str
    kind: str = "STEP"


def entry(identity, result, *, detail="", allowed=False, kind="STEP"):
    reason = result.message if result.message != str(result.status) else ""
    return SummaryEntry(
        one_line(identity),
        display_status(result),
        result.duration,
        allowed or result.allowed_failure,
        one_line("; ".join(part for part in (detail, reason) if part)),
        kind,
    )


def job_failures(result, label, *, allowed=False):
    return [
        entry(prefix(label, result.variant, step.name), step, allowed=allowed)
        for step in result.steps
        if step.status == "failed"
    ]


def summary_block(
    kind, identity, result, entries, *, failures=(), log_file=None, width=80
) -> Block:
    child_kind, label = ("STEP", "Step") if kind == "JOB" else ("JOB", "Job")
    rows = [heading(kind, identity, result=result, width=width)]
    # Align only this summary's columns. Streaming prefixes are never padded.
    name_width = max([len(label), *(len(item.identity) for item in entries)])
    if entries:
        rows.append([(f"{label:<{name_width}}  Result     Duration  Detail", "muted")])
    for item in entries:
        row = [
            (f"{item.identity:<{name_width}}  ", child_kind),
            (item.status.upper(), item.status),
            (f"{' ' * (11 - len(item.status))}{elapsed(item):>8}", ""),
        ]
        if item.allowed_failure:
            row.append(("  allowed failure", "warning"))
        if item.detail:
            row.append(("  " + item.detail, ""))
        rows.append(row)
    statuses = Counter(item.status for item in entries)
    counts = [(f"{identity} ", kind), (label + "s: ", "")]
    for index, status in enumerate(
        (
            "passed",
            "failed",
            "skipped",
            "cancelled",
            *(("reused",) if statuses["reused"] else ()),
        )
    ):
        if index:
            counts.append((" | ", ""))
        count = statuses[status]
        counts.append((f"{count} {status}", status if count else "muted"))
    allowed_count = sum(item.allowed_failure for item in entries)
    if allowed_count:
        counts.append((f" | {allowed_count} allowed failure(s)", "warning"))
    rows.append(counts)
    for failure in failures:
        row = [
            (f"{identity} ", kind),
            ("What failed: ", "failed"),
            (failure.identity, failure.kind),
            (" | FAILED", "failed"),
        ]
        if failure.allowed_failure:
            row.append((" | allowed failure", "warning"))
        if failure.detail:
            row.append((" | " + failure.detail, ""))
        rows.append(row)
    if log_file:
        rows += contextual(identity, [f"Log: {log_file}"], kind)
    return rows


def job_summary(result, label, *, width=80) -> Block:
    return summary_block(
        "JOB",
        prefix(label, result.variant),
        result,
        [entry(step.name, step) for step in result.steps],
        failures=job_failures(result, label),
        log_file=result.log_file,
        width=width,
    )
