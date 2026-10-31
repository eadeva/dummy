"""Report exporters: JSON (canonical), JUnit XML, Markdown (also the GitHub summary)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
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
        "cmake": {
            "invocations": len(report.cmake),
            "active": dict(
                Counter(
                    f.level
                    for c in report.cmake
                    for f in c.diagnostics
                    if f.disposition == "active"
                )
            ),
            "dispositions": dict(
                Counter(f.disposition for c in report.cmake for f in c.diagnostics)
            ),
        },
        "needs": {
            "records": sum(len(doc.needs) for doc in report.sphinx),
            "types": dict(
                Counter(
                    need.type or "Unspecified"
                    for doc in report.sphinx
                    for need in doc.needs
                )
            ),
            "statuses": dict(
                Counter(
                    need.status or "Unspecified"
                    for doc in report.sphinx
                    for need in doc.needs
                )
            ),
            "violations": dict(
                Counter(v.level for doc in report.sphinx for v in doc.violations)
            ),
        },
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
        result = step.status + (" (allowed)" if step.allowed_failure else "")
        if step.message and step.status != PASSED:
            result += f": {step.message}"
        time = f"{step.duration:.1f}s" if step.status in (PASSED, FAILED) else ""
        lines.append(
            f"| {ICON.get(step.status, '')} {_cell(step.name)} | {_cell(result)} | {time} |"
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
    if report.log_analysis_enabled:
        lines += [
            "## Log analysis",
            "",
            "| Severity | Disposition | Step | Message | Source log | Location | Occurrences | Reason |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for finding in report.log_findings:
            values = [
                finding.level,
                finding.disposition,
                finding.step,
                finding.message,
                finding.source_log,
                f"{finding.file}:{finding.line}"
                if finding.file
                else f"Log line {finding.log_line}",
                finding.occurrences,
                finding.reason,
            ]
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
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
    if report.sphinx:
        lines += [
            "## Sphinx documentation",
            "",
            "Needs and schema findings are separate from test totals and execution status.",
            "",
        ]
        for doc in report.sphinx:
            levels = Counter(v.level for v in doc.violations)
            lines += [
                f"**{_cell(doc.step)} · {_cell(doc.source)}:** {len(doc.needs)} needs; "
                + (
                    ", ".join(f"{n} {level}" for level, n in sorted(levels.items()))
                    or (
                        "no schema findings"
                        if doc.violations_imported
                        else "validation not reported"
                    )
                ),
                "",
            ]
            if doc.docs_index:
                from pathlib import Path

                lines += [
                    f"[Open built documentation](<{Path(doc.docs_index).as_uri()}>)",
                    "",
                ]
            lines += ["| Need type | Count |", "|---|---|"]
            lines += [
                f"| {_cell(kind or 'Unspecified')} | {count} |"
                for kind, count in sorted(Counter(n.type for n in doc.needs).items())
            ]
            lines += ["", "| Lifecycle status | Count |", "|---|---|"]
            lines += [
                f"| {_cell(status or 'Unspecified')} | {count} |"
                for status, count in sorted(
                    Counter(n.status for n in doc.needs).items()
                )
            ]
            lines.append("")
            for violation in doc.violations[:20]:
                lines.append(
                    f"- **{_cell(violation.level)}** `{_cell(violation.need_id)}`: {_cell(violation.message)}"
                )
            if len(doc.violations) > 20:
                lines.append(
                    f"- … and {len(doc.violations) - 20} more; see the HTML or JSON report."
                )
            lines.append("")
    if report.cmake:
        lines += [
            "## CMake",
            "",
            "Probe outcomes are not test failures. Diagnostic dispositions do not change process outcomes.",
            "",
        ]
        for cmake in report.cmake:
            lines += [
                f"**{_cell(cmake.step)} · CMake {_cell(cmake.version)} · {_cell(cmake.importer)}:** {_cell(cmake.status)}; {len(cmake.targets)} targets",
                "",
                "| Severity | Disposition | Message | Sources | Reason |",
                "|---|---|---|---|---|",
            ]
            for finding in cmake.diagnostics:
                lines.append(
                    "| "
                    + " | ".join(
                        _cell(v)
                        for v in (
                            finding.level,
                            finding.disposition,
                            finding.message,
                            "; ".join(finding.context),
                            finding.reason,
                        )
                    )
                    + " |"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
