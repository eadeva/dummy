"""Job reports: outcome first, then execution, diagnostics and retained evidence."""

import copy
import json

from .. import graph_html
from . import bazel_html, cmake_html, diagnostics, gn_html, needs_html, ui
from .ui import anchor, badge, e, fields, link


def owner(report):
    alias = report.context.get("repository_alias", report.project)
    return (
        f"[{report.variant or 'default'}][{alias + ':' if alias else ''}{report.job}]"
    )


def version(report):
    alias = report.context.get("repository_alias", report.project)
    return (
        report.context.get("versions", {})
        .get("projects", {})
        .get(alias, {})
        .get("value", "Not recorded")
    )


def step_entries(report, root=None, *, scope=""):
    rows = []
    for step in report.steps:
        detail = fields(
            {
                "Needs": ", ".join(step.needs) or "None",
                "Kind": step.kind,
                "Attempts": step.attempts,
                "Exit code": step.exit_code if step.exit_code is not None else "—",
            }
        )
        if step.message:
            detail += f"<p>{e(step.message)}</p>"
        if step.command:
            detail += f"<pre>{e(step.command)}</pre>"
        detail += link(step.log_file, root)
        rows.append(
            {
                "target": anchor("step", scope, step.label),
                "label": step.label,
                "owner": owner(report),
                "kind": "step",
                "status": step.status,
                "allowed": step.allowed_failure,
                "duration": step.duration,
                "start": step.start,
                "detail": detail,
            }
        )
    return rows


def recorded_graph(report, *, scope=""):
    graph = copy.deepcopy(report.graph)
    for node in graph["nodes"]:
        node["kind"] = "step"
        if node.get("status") != "hidden":
            node["target"] = anchor("step", scope, node["id"])
    return graph


def overview(entries, reports, diagnostics_items, *, entity="Steps"):
    counts = {
        key: sum(row["status"] == key for row in entries)
        for key in ("passed", "failed", "skipped", "cancelled")
    }
    allowed = sum(
        row.get("allowed", False) and row["status"] == "failed" for row in entries
    )
    values = {
        f"{entity} passed": counts["passed"],
        f"{entity} failed": f"{counts['failed']} ({allowed} allowed)"
        if allowed
        else counts["failed"],
        f"{entity} skipped": counts["skipped"],
        f"{entity} cancelled": counts["cancelled"],
    }
    tones = {
        f"{entity} passed": "passed",
        f"{entity} failed": "failed",
        f"{entity} skipped": "skipped",
        f"{entity} cancelled": "warning",
    }
    targets = dict.fromkeys(values, "execution")
    cases = [
        case for report in reports for suite in report.suites for case in suite.cases
    ]
    if cases:
        values["Tests passed"] = (
            f"{sum(case.status == 'passed' for case in cases)} / {len(cases)}"
        )
        values["Tests failed"] = sum(
            case.status in ("failed", "error") for case in cases
        )
        targets.update({"Tests passed": "tests", "Tests failed": "tests"})
        tones["Tests failed"] = "failed"
    values["Active log errors"] = sum(
        item.count
        for item in diagnostics_items
        if item.source == "log"
        and item.severity == "error"
        and item.disposition == "active"
    )
    targets["Active log errors"] = "diagnostics"
    tones["Active log errors"] = "failed" if values["Active log errors"] else "info"
    values["Other diagnostics"] = sum(
        item.source in ("static", "report", "sphinx", "cmake", "bazel", "gn")
        and item.disposition == "active"
        for item in diagnostics_items
    )
    targets["Other diagnostics"] = "diagnostics"
    if any(report.sphinx for report in reports):
        values["Needs"] = sum(
            len(doc.needs) for report in reports for doc in report.sphinx
        )
        targets["Needs"] = "needs"
    return ui.cards(values, tones=tones, targets=targets)


def tests_section(reports):
    suites = [(report, suite) for report in reports for suite in report.suites]
    if not suites:
        return ""
    rows = []
    totals = {"Executed": 0, "Passed": 0, "Skipped": 0, "Failed": 0}
    for report, suite in suites:
        for case in suite.cases:
            totals["Executed"] += case.status != "skipped"
            totals["Passed"] += case.status == "passed"
            totals["Skipped"] += case.status == "skipped"
            totals["Failed"] += case.status in ("failed", "error")
            rows.append(
                f'<details class="test-case" data-record data-status="{e(case.status)}"><summary>{badge(case.status)} {e(case.classname + "." if case.classname else "")}{e(case.name)} <span class="duration">{case.time:.2f}s</span></summary><div class="item-detail">{fields({"Owner": owner(report), "Step": suite.step, "Suite": suite.name, "Source": suite.source})}<pre>{e(case.message or "No additional test output.")}</pre></div></details>'
            )
    return (
        '<section id="tests"><h2>Tests</h2>'
        + ui.cards(
            totals, tones={"Passed": "passed", "Failed": "failed", "Skipped": "skipped"}
        )
        + '<p class="meta">Executed excludes skipped tests. Failed includes errors. Test counts do not include execution records or log occurrences.</p><div data-filter="tests">'
        + ui.toolbar(
            "tests",
            {
                "status": (
                    "Test result",
                    [
                        ("", "All results"),
                        ("passed", "Passed"),
                        ("failed", "Failed"),
                        ("error", "Error"),
                        ("skipped", "Skipped"),
                    ],
                    "",
                )
            },
        )
        + "".join(rows)
        + '<p data-filter-count aria-live="polite"></p></div></section>'
    )


def configuration(report):
    context = report.context
    values = {
        "Project": report.project,
        "Repository alias": context.get("repository_alias", report.project),
        "Project version": version(report),
        "PTK version": report.ptk_version or "Not recorded",
        "Variant": report.variant or "default",
    }
    content = (
        '<details><summary>Project information</summary><div class="item-detail">'
        + fields(values)
        + "</div></details>"
    )
    variant = context.get("variant", {})
    if variant:
        features = "".join(
            f"<tr><td>{e(key)}</td><td><code>{e(json.dumps(value, ensure_ascii=False))}</code></td></tr>"
            for key, value in variant.get("features", {}).items()
        )
        content += (
            '<details><summary>Selected variant features</summary><div class="item-detail">'
            + fields(
                {
                    "Description": variant.get("description", ""),
                    "Components": ", ".join(variant.get("components", [])) or "None",
                    "Inheritance": " → ".join(variant.get("chain", [])) or "None",
                }
            )
            + '<div class="table-wrap"><table><tr><th>Feature</th><th>Value</th></tr>'
            + features
            + "</table></div></div></details>"
        )
    tools = list(context.get("tools", []))
    known = {tool["name"] for tool in tools}
    tools += [
        {"name": name}
        for name in context.get("required_tools", [])
        if name not in known
    ]
    rows = "".join(
        f"<tr><td>{e(tool['name'])}</td><td>{e(tool.get('version') or 'Not detected')}</td><td>{e(tool.get('required') or 'Any')}</td><td>{e(tool.get('source') or 'Not recorded')}</td></tr>"
        for tool in tools
    )
    content += (
        '<details><summary>Tool dependencies</summary><div class="item-detail">'
        + (
            '<div class="table-wrap"><table><tr><th>Name</th><th>Version</th><th>Required</th><th>Source (executable)</th></tr>'
            + rows
            + "</table></div>"
            if tools
            else '<p class="meta">No declared tool dependencies.</p>'
        )
        + "</div></details>"
    )
    if report.params:
        rows = "".join(
            f"<tr><td>{e(name)}</td><td><code>{e(value)}</code></td><td>{e(report.param_sources.get(name, ''))}</td></tr>"
            for name, value in report.params.items()
        )
        content += (
            '<details><summary>Parameters</summary><div class="item-detail table-wrap"><table><tr><th>Name</th><th>Value</th><th>From</th></tr>'
            + rows
            + "</table></div></details>"
        )
    return content


def evidence(report, root=None):
    links = [
        link(step.log_file, root, step.label + " log")
        for step in report.steps
        if step.log_file
    ]
    content = (
        '<ul class="evidence-links">'
        + "".join(f"<li>{item}</li>" for item in links)
        + "</ul>"
        if links
        else '<p class="meta">No captured step logs were recorded.</p>'
    )
    if report.coverage:
        content += "<h3>Imported line coverage</h3>" + ui.cards(
            {
                f"{cov.step} · {cov.source}": f"{cov.percent:.1f}% ({cov.lines_covered}/{cov.lines_valid})"
                for cov in report.coverage
            }
        )
    return content


def render(report, *, link_root=None):
    entries = step_entries(report, link_root)
    items = diagnostics.collect(report, owner(report), link_root)
    summary = overview(entries, [report], items)
    selection = report.context.get("selection", {})
    if selection.get("only_step"):
        summary += (
            '<p class="notice"><strong>Single-step execution:</strong> '
            + e(selection["only_step"])
            + ". Prerequisites not run: "
            + e(", ".join(selection["omitted_dependencies"]) or "none")
            + ". Required outputs must already exist; PTK does not restore outputs from previous runs.</p>"
        )
    workflow = report.context.get("workflow", {})
    evidence_html = evidence(report, link_root)
    if workflow.get("report_file"):
        evidence_html = (
            "<p>"
            + link(
                workflow["report_file"],
                link_root,
                "Back to workflow " + workflow["name"],
            )
            + "</p>"
            + evidence_html
        )
    return ui.page(
        title=f"Job - {report.job} {report.status} - {report.project}",
        kind="job",
        name=report.job,
        status=report.status,
        metadata={
            "Owner": owner(report),
            "Project": report.project,
            "Project version": version(report),
            "PTK": report.ptk_version or "Not recorded",
            "Started": report.started_at or "Not recorded",
            "Duration": f"{report.duration:.2f}s",
            "Run": report.run_id,
        },
        overview=summary,
        failures=diagnostics.failures(items),
        execution_html=ui.execution(
            entries,
            "Recorded steps · select a step for command, dependencies and captured output.",
        ),
        graph=graph_html.section(
            recorded_graph(report), f"Job {report.job} · {report.variant}"
        ),
        timeline_html=ui.timeline(entries, report.duration),
        diagnostics=diagnostics.render(
            items, analysis_enabled=report.log_analysis_enabled
        ),
        tests=tests_section([report]),
        needs=needs_html.section([report], link_root),
        cmake=cmake_html.section([report]),
        bazel=bazel_html.section([report], link_root),
        gn=gn_html.section([report]),
        evidence=evidence_html,
        configuration=configuration(report),
    )
