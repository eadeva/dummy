"""Plain run presentation shared by console and aggregate transcripts."""

import json
from collections import Counter

from .layout import NO_VARIANT


def one_line(value):
    return str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def boundary(kind, identity, state, width=80):
    mark = "=" if kind == "WORKFLOW" else "-"
    lead = (
        f"{mark * (3 if kind == 'STEP' else 8)} {kind}"
        + (f" {one_line(identity)}" if identity else "")
        + f" | {state} "
    )
    return lead + mark * max(3, width - len(lead))


def prefix(job, variant, step=None):
    return f"[{job}][{variant or NO_VARIANT}]" + (f"[{step}]" if step else "")


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


def counts(label, results):
    values = list(results)
    statuses = Counter(str(item.status) for item in values)
    parts = [
        f"{statuses[name]} {name}"
        for name in ("passed", "failed", "skipped", "cancelled")
    ]
    allowed = sum(item.allowed_failure for item in values)
    if allowed:
        parts.append(f"{allowed} allowed failure(s)")
    return f"{label}: " + " | ".join(parts)


def step_rows(step, command):
    rows = []
    if step.title != step.name:
        rows.append(f"Title: {one_line(step.title)}")
    if step.spec.generators:
        rows.append("Generators: " + ", ".join(step.spec.generators))
    if command:
        rows.append(f"Command: {command}")
    return rows


def outcome(result):
    text = f"{str(result.status).upper()} | {result.duration:.1f}s"
    if result.allowed_failure:
        text += " | allowed failure"
    return text


def result_rows(result):
    rows = [counts("Steps", result.steps)]
    if result.log_file:
        rows.append(f"Log: {result.log_file}")
    return rows
