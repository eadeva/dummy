"""One diagnostic presentation with explicit source, ownership and evidence."""

import json
from dataclasses import dataclass

from .ui import anchor, badge, e, fields, link, toolbar

SOURCES = {
    "execution": "Execution",
    "test": "Imported test",
    "log": "Log analysis",
    "static": "Static analysis",
    "report": "Report collection",
    "sphinx": "Sphinx-Needs",
}


@dataclass
class Diagnostic:
    owner: str
    step: str
    source: str
    severity: str
    title: str
    detail: str = ""
    disposition: str = "active"
    count: int = 0
    allowed: bool = False
    target: str = ""
    preview: str = ""
    search: str = ""


def collect(report, owner, root=None, *, scope="", allowed=False):
    result = []
    for step in report.steps:
        if step.status not in ("failed", "cancelled"):
            continue
        result.append(
            Diagnostic(
                owner,
                step.label,
                "execution",
                "error" if step.status == "failed" else "note",
                step.message or step.status.title(),
                f"<p>{badge(step.status, step.allowed_failure or allowed)}</p><pre>{e(step.command)}</pre>{link(step.log_file, root)}",
                allowed=step.allowed_failure or allowed,
                target=anchor("step", scope, step.label),
                search=step.command,
            )
        )
    for suite in report.suites:
        for case in suite.cases:
            if case.status not in ("failed", "error"):
                continue
            result.append(
                Diagnostic(
                    owner,
                    suite.step,
                    "test",
                    "error",
                    f"{case.classname + '.' if case.classname else ''}{case.name}",
                    fields(
                        {
                            "Suite": suite.name,
                            "Source": suite.source,
                            "Result": case.status,
                            "Duration": f"{case.time:.2f}s",
                        }
                    )
                    + f"<pre>{e(case.message)}</pre>",
                    preview=case.message.splitlines()[0][:240] if case.message else "",
                    search=f"{suite.name} {suite.source} {case.message}",
                )
            )
    for finding in report.findings:
        result.append(
            Diagnostic(
                owner,
                finding.step,
                "static",
                finding.level,
                finding.message,
                fields(
                    {
                        "Tool": finding.tool,
                        "Rule": finding.rule,
                        "Location": f"{finding.file}:{finding.line}"
                        if finding.line
                        else finding.file,
                    }
                ),
                search=f"{finding.tool} {finding.rule} {finding.file}",
            )
        )
    for finding in report.log_findings:
        evidence = fields(
            {
                "Tool": finding.tool,
                "Rule": finding.rule,
                "Location": f"{finding.file}:{finding.line}"
                if finding.line
                else finding.file or f"Log line {finding.log_line}",
                "Occurrences": finding.occurrences,
            }
        )
        evidence += link(finding.source_log, root)
        if finding.context:
            lines = []
            for line in finding.context:
                number = line.split(":", 1)[0]
                matched = number.isdigit() and int(number) in finding.log_lines
                lines.append(f"<mark>{e(line)}</mark>" if matched else e(line) + "\n")
            evidence += "<pre>" + "".join(lines) + "</pre>"
        if finding.reason:
            evidence += fields(
                {"Disposition rule": finding.suppression_rule, "Reason": finding.reason}
            )
        result.append(
            Diagnostic(
                owner,
                finding.step,
                "log",
                finding.level,
                finding.message,
                evidence,
                finding.disposition,
                finding.occurrences,
                search=f"{finding.tool} {finding.rule} {finding.file} {finding.source_log} {finding.suppression_rule} {finding.reason}",
            )
        )
    result.extend(
        Diagnostic(owner, "", "report", "error", problem) for problem in report.problems
    )
    for doc in report.sphinx:
        for violation in doc.violations:
            detail = fields(
                {
                    "Need": violation.need_id,
                    "Source": doc.source,
                    "Rule": violation.rule,
                    **violation.details,
                }
            )
            if violation.children:
                detail += (
                    '<details><summary>Nested validation details</summary><div class="item-detail"><pre>'
                    + e(json.dumps(violation.children, indent=2, ensure_ascii=False))
                    + "</pre></div></details>"
                )
            detail += link(doc.violations_file, root, "Captured schema_violations.json")
            result.append(
                Diagnostic(
                    owner,
                    doc.step,
                    "sphinx",
                    violation.level,
                    f"{violation.need_id}: {violation.message}",
                    detail,
                    search=json.dumps(
                        {
                            "rule": violation.rule,
                            "source": doc.source,
                            "details": violation.details,
                            "children": violation.children,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    if report.status == "failed" and not any(
        item.source == "execution" and item.severity == "error" for item in result
    ):
        result.append(
            Diagnostic(
                owner,
                "",
                "execution",
                "error",
                "Job failed; no visible step failure was recorded",
                allowed=allowed,
            )
        )
    visible = {step.label for step in report.steps}
    for item in result:
        if item.step in visible and not item.target:
            item.target = anchor("step", scope, item.step)
    return result


def failures(items):
    rows = []
    for index, item in enumerate(items):
        if item.severity != "error" or item.disposition != "active":
            continue
        identity = item.owner + (f"[{item.step}]" if item.step else "")
        allowed = " · failure allowed" if item.allowed else ""
        preview = (
            f'<span class="failure-preview">{e(item.preview)}</span>'
            if item.preview
            else ""
        )
        rows.append(
            f'<li><a href="#diagnostic-{index}">{e(item.title)}</a>{preview}<span class="meta">{e(identity)} · {SOURCES[item.source]}{allowed}</span></li>'
        )
    return (
        '<section id="failures"><h2>What failed</h2>'
        + (
            '<ul class="failure-list">' + "".join(rows) + "</ul>"
            if rows
            else '<p class="empty">No execution failures or active error diagnostics were recorded. See execution details for skips and cancellations.</p>'
        )
        + "</section>"
    )


def render(items, *, analysis_enabled=True):
    totals = {"error": 0, "warning": 0, "justified": 0, "ignored": 0}
    for item in items:
        if item.source == "log":
            totals[
                item.severity if item.disposition == "active" else item.disposition
            ] += item.count
    cards = (
        '<div class="diagnostic-cards">'
        + "".join(
            f'<button type="button" data-diagnostic-card="{key}" aria-label="Show {label.lower()}">{label}<strong>{totals[key]}</strong></button>'
            for key, label in [
                ("error", "Active log errors"),
                ("warning", "Active log warnings"),
                ("justified", "Justified log findings"),
                ("ignored", "Ignored log findings"),
            ]
        )
        + "</div>"
        if analysis_enabled
        else '<p class="meta">Log analysis was not enabled for this run.</p>'
    )
    choices = {
        "source": ("Source", [("", "All sources"), *SOURCES.items()], ""),
        "severity": (
            "Severity",
            [
                ("", "All severities"),
                ("error", "Error"),
                ("warning", "Warning"),
                ("note", "Note"),
            ],
            "",
        ),
        "disposition": (
            "Disposition",
            [
                ("", "All dispositions"),
                ("active", "Active"),
                ("justified", "Justified"),
                ("ignored", "Ignored"),
            ],
            "active",
        ),
        "owner": (
            "Owner",
            [
                ("", "All owners"),
                *((value, value) for value in dict.fromkeys(i.owner for i in items)),
            ],
            "",
        ),
        "step": (
            "Step",
            [
                ("", "All steps"),
                *(
                    (value, value)
                    for value in dict.fromkeys(i.step for i in items)
                    if value
                ),
            ],
            "",
        ),
    }
    rows = []
    for index, item in enumerate(items):
        identity = item.owner + (f"[{item.step}]" if item.step else "")
        attrs = " ".join(f'data-{key}="{e(getattr(item, key))}"' for key in choices)
        searchable = f"{identity} {SOURCES[item.source]} {item.title} {item.search}"
        attrs += f' data-search="{e(searchable)}"'
        target = (
            f'<p><a href="#{e(item.target)}">Open execution details</a></p>'
            if item.target
            else ""
        )
        allowed = " · failure allowed" if item.allowed else ""
        rows.append(
            f'<details id="diagnostic-{index}" class="diagnostic" data-record data-count="{item.count}" {attrs}{" hidden" if item.disposition != "active" else ""}><summary><span class="badge {e(item.severity)}">{e(item.severity.title())}</span><span class="diagnostic-title">{e(item.title)}</span><span class="meta"> · {e(SOURCES[item.source])}{allowed}</span></summary><div class="item-detail"><p class="meta">{e(identity)} · {e(item.disposition.title())}</p>{item.detail}{target}</div></details>'
        )
    empty = (
        '<p class="meta">No recognized active log diagnostics.</p>'
        if analysis_enabled and not totals["error"] and not totals["warning"]
        else ""
    )
    return (
        '<section id="diagnostics"><h2>Diagnostics</h2><p class="meta">One evidence list, with separate sources. Log occurrence counts do not add to test totals or change execution status. Ignored and justified findings remain available.</p><div data-filter="diagnostics">'
        + cards
        + empty
        + toolbar("diagnostics", choices)
        + "".join(rows)
        + '<p data-filter-count aria-live="polite"></p></div></section>'
    )
