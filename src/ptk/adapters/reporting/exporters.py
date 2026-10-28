"""Report exporters: JSON (canonical), JUnit XML, Markdown (also the GitHub summary)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict

from ...domain.reporting.model import (
    ERROR,
    FAILED,
    PASSED,
    SKIPPED,
    Report,
    test_metrics,
)

ICON = {PASSED: "✅", FAILED: "❌", SKIPPED: "⏭️", "cancelled": "⏹️", ERROR: "💥"}


def to_json(report: Report) -> str:
    data = asdict(report)
    data["totals"] = {
        "tests": dict(report.test_totals()),
        "test_cases": test_metrics(c for suite in report.suites for c in suite.cases),
        "findings": dict(report.finding_totals()),
    }
    return json.dumps(data, indent=2, default=str) + "\n"


def to_junit(report: Report) -> str:
    """Steps as one test suite (CI dashboards show the job), imported suites after it."""
    root = ET.Element("testsuites", name=f"{report.project} {report.job}")
    suite = ET.SubElement(
        root,
        "testsuite",
        name=f"ptk {report.job} [{report.variant}]",
        timestamp=report.started_at,
        time=f"{report.duration:.3f}",
    )
    properties = ET.SubElement(suite, "properties")
    for name, value in report.context.items():
        ET.SubElement(
            properties,
            "property",
            name=name,
            value=json.dumps(value, ensure_ascii=False),
        )
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for step in report.steps:
        if step.kind == "set":
            continue
        counts["tests"] += 1
        parent = step.label.rsplit("/", 1)[0] if "/" in step.label else report.job
        case = ET.SubElement(
            suite,
            "testcase",
            name=step.name,
            classname=parent,
            time=f"{step.duration:.3f}",
        )
        if step.status == FAILED and not step.allowed_failure:
            counts["failures"] += 1
            node = ET.SubElement(case, "failure", message=step.message or "failed")
            node.text = step.command
        elif step.status == "cancelled":
            counts["errors"] += 1
            ET.SubElement(case, "error", message=step.message or "cancelled")
        elif step.status == SKIPPED:
            counts["skipped"] += 1
            ET.SubElement(case, "skipped", message=step.message)
        elif step.allowed_failure:
            out = ET.SubElement(case, "system-out")
            out.text = f"failed but allowed (continue_on_error): {step.message}"
    for key, value in counts.items():
        suite.set(key, str(value))
    for imported in report.suites:
        node = ET.SubElement(
            root,
            "testsuite",
            name=f"{imported.step}: {imported.name}",
            tests=str(len(imported.cases)),
            failures=str(imported.count(FAILED)),
            errors=str(imported.count(ERROR)),
            skipped=str(imported.count(SKIPPED)),
        )
        for test in imported.cases:
            case = ET.SubElement(
                node,
                "testcase",
                name=test.name,
                classname=test.classname,
                time=f"{test.time:.3f}",
            )
            if test.status in (FAILED, ERROR):
                tag = "failure" if test.status == FAILED else "error"
                ET.SubElement(case, tag, message=test.message[:500]).text = test.message
            elif test.status == SKIPPED:
                ET.SubElement(case, "skipped", message=test.message)
    ET.indent(root)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        + ET.tostring(root, encoding="unicode")
        + "\n"
    )


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(report: Report) -> str:
    lines = [
        f"## Job - {report.job} {ICON.get(report.status, '')} — {report.status}",
        "",
        (
            f"Project **{_cell(report.project)}**, variant **{_cell(report.variant)}**, "
            f"run `{report.run_id}`, {report.duration:.1f}s"
        ),
        "",
    ]
    context = report.context
    alias = context.get("repository_alias", report.project)
    version = (
        context.get("versions", {})
        .get("projects", {})
        .get(alias, {})
        .get("value", "Not recorded")
    )
    lines += [
        f"**PTK version:** {_cell(report.ptk_version or 'Not recorded')} · **Project version:** {_cell(version)}",
        "",
    ]
    if context.get("variant"):
        lines += [
            "**Variant details:** `"
            + _cell(json.dumps(context["variant"], ensure_ascii=False))
            + "`",
            "",
        ]
    if context.get("tools"):
        lines += ["| Tool | Version | Source (executable) |", "|---|---|---|"]
        lines += [
            f"| {_cell(t['name'])} | {_cell(t.get('version') or 'Not detected')} | {_cell(t.get('source') or 'Not recorded')} |"
            for t in context["tools"]
        ]
        lines.append("")
    if report.params:
        lines += ["| Parameter | Value | From |", "|---|---|---|"]
        for name, value in report.params.items():
            lines.append(
                f"| {_cell(name)} | `{_cell(value)}` | {_cell(report.param_sources.get(name, ''))} |"
            )
        lines.append("")
    lines += ["| Step | Result | Time |", "|---|---|---|"]
    for step in report.steps:
        indent = "&nbsp;&nbsp;" * step.depth
        result = step.status + (" (allowed)" if step.allowed_failure else "")
        if step.message and step.status != PASSED:
            result += f": {step.message}"
        time = f"{step.duration:.1f}s" if step.status in (PASSED, FAILED) else ""
        lines.append(
            f"| {indent}{ICON.get(step.status, '')} {_cell(step.name)} | {_cell(result)} | {time} |"
        )
    lines.append("")
    totals = report.test_totals()
    if totals:
        metrics = test_metrics(c for suite in report.suites for c in suite.cases)
        lines += [
            " | ".join(f"**{k}:** {v}" for k, v in metrics.items()),
            "",
            "Executed excludes skipped; failed includes errors.",
            "",
        ]
        parts = [
            f"{totals[s]} {s}" for s in (PASSED, FAILED, ERROR, SKIPPED) if totals[s]
        ]
        lines += [f"**Tests:** {', '.join(parts)}", ""]
        failed = [
            (suite, case)
            for suite in report.suites
            for case in suite.cases
            if case.status in (FAILED, ERROR)
        ]
        for suite, case in failed[:20]:
            lines.append(
                f"- ❌ `{_cell(case.classname)}.{_cell(case.name)}` ({_cell(suite.step)}): "
                f"{_cell(case.message[:200])}"
            )
        if len(failed) > 20:
            lines.append(f"- … and {len(failed) - 20} more")
        lines.append("")
    if report.findings:
        totals_f = report.finding_totals()
        lines += [
            "**Findings:** "
            + ", ".join(f"{n} {lvl}" for lvl, n in sorted(totals_f.items())),
            "",
        ]
    for cov in report.coverage:
        lines += [f"**Coverage** ({_cell(cov.step)}): {cov.percent:.1f}% of lines", ""]
    return "\n".join(lines).rstrip() + "\n"
