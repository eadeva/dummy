"""Bazel invocation, target and test-attempt evidence in the shared report."""

import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import graph_html
from . import ui
from .ui import e, fields, link


def artifact_link(record, root):
    try:
        uri = urlsplit(record.get("uri", ""))
        if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
            return ""
        name = unquote(uri.path)
        if os.name == "nt" and len(name) > 2 and name[0] == "/" and name[2] == ":":
            name = name[1:]
        path = Path(name)
        return (
            link(path, root, "Open local artifact")
            if path.is_absolute() and path.is_file()
            else ""
        )
    except (OSError, ValueError):
        return ""


def section(reports, root=None):
    from .html import owner

    datasets = [(owner(report), bazel) for report in reports for bazel in report.bazel]
    if not datasets:
        return ""
    findings = [f for _, bazel in datasets for f in bazel.diagnostics]
    active = Counter(f.level for f in findings if f.disposition == "active")
    content = ui.cards(
        {
            "Bazel errors": active["error"],
            "Bazel warnings": active["warning"],
            "Ignored": sum(f.disposition == "ignored" for f in findings),
            "Justified": sum(f.disposition == "justified" for f in findings),
            "Target results": sum(len(b.targets) for _, b in datasets),
            "Test-target summaries": sum(len(b.tests) for _, b in datasets),
        },
        tones={"Bazel errors": "failed", "Bazel warnings": "warning"},
        targets={"Bazel errors": "diagnostics", "Bazel warnings": "diagnostics"},
    )
    for identity, bazel in datasets:
        content += (
            "<details><summary>"
            + e(
                f"{identity}[{bazel.step}] · Bazel {bazel.version or 'version unavailable'} · {bazel.command or 'invocation'}"
            )
            + '</summary><div class="item-detail">'
        )
        content += fields(
            {
                "Invocation": bazel.invocation_id,
                "Executable": bazel.executable,
                "Workspace": bazel.workspace,
                "Evidence": bazel.source,
                "PTK command result": bazel.status,
                "Captured command duration": f"{bazel.duration:.2f}s"
                if bazel.duration
                else "Not recorded",
                "Bazel build exit": f"{bazel.exit_name} ({bazel.exit_code})"
                if bazel.exit_code is not None
                else "Not recorded",
                "Event stream": "Complete"
                if bazel.complete
                else "Incomplete / unavailable",
            }
        )
        content += (
            "<details><summary>Available evidence</summary>"
            + fields(bazel.availability)
            + "</details>"
        )
        if bazel.graph:
            content += "<h3>Build target dependencies</h3>" + graph_html.section(
                bazel.graph, f"Bazel targets · {identity}[{bazel.step}]"
            )
        else:
            content += (
                '<p class="meta">Target dependencies: '
                + e(
                    bazel.availability.get(
                        "target graph", "No cquery evidence recorded"
                    )
                )
                + "</p>"
            )
        if bazel.tests:
            counts = Counter(t["status"] for t in bazel.tests)
            content += "<h3>Test-target outcomes</h3>" + ui.cards(
                dict(counts),
                tones={
                    "FAILED": "failed",
                    "TIMEOUT": "failed",
                    "PASSED": "passed",
                    "FLAKY": "warning",
                },
            )
        if bazel.metrics:
            metrics = {}
            for label, group, key in (
                (
                    "Actions executed (incl. remote cache)",
                    "actionSummary",
                    "actionsExecuted",
                ),
                (
                    "Targets configured this invocation",
                    "targetMetrics",
                    "targetsConfigured",
                ),
                ("Packages loaded", "packageMetrics", "packagesLoaded"),
                ("Wall time (ms)", "timingMetrics", "wallTimeInMs"),
                ("CPU time (ms)", "timingMetrics", "cpuTimeInMs"),
            ):
                if key in bazel.metrics.get(group, {}):
                    metrics[label] = bazel.metrics[group][key]
            content += "<h3>Build metrics</h3>" + fields(metrics)
            content += (
                '<details><summary>Build metrics</summary><p class="meta">Counters describe this invocation. Actions executed includes remote cache hits and excludes local action-cache hits. Missing counters are unavailable, not zero. Test cache indicators belong to individual attempts.</p><pre>'
                + e(json.dumps(bazel.metrics, indent=2, ensure_ascii=False))
                + "</pre></details>"
            )
        for title, records in (
            ("Targets", bazel.targets),
            ("Test-target summaries", bazel.tests),
            ("Test attempts, shards and runs", bazel.test_attempts),
            ("Reported actions", bazel.actions),
            ("Configurations", bazel.configurations),
            ("Artifact references", bazel.artifacts),
        ):
            if not records:
                continue
            content += (
                f'<h3>{e(title)}</h3><div data-filter="Bazel {e(title)}">'
                + ui.toolbar("Bazel " + title, {})
            )
            for record in records:
                name = (
                    record.get("label")
                    or record.get("name")
                    or record.get("mnemonic")
                    or record.get("id")
                    or "Artifact"
                )
                result = record.get("status", "")
                config = record.get("configuration", "")
                attempt = (
                    f" · run {record['run']} / shard {record['shard']} / attempt {record['attempt']}"
                    if "attempt" in record
                    else ""
                )
                content += (
                    "<details data-record><summary>"
                    + e(
                        f"{name} · {result}"
                        + (f" · {config}" if config else "")
                        + attempt
                    )
                    + "</summary><pre>"
                    + e(json.dumps(record, indent=2, ensure_ascii=False))
                    + "</pre>"
                    + (
                        artifact_link(record, root)
                        if title == "Artifact references"
                        else ""
                    )
                    + "</details>"
                )
            content += '<p data-filter-count aria-live="polite"></p></div>'
        content += "</div></details>"
    return (
        '<section id="bazel"><h2>Bazel</h2><p class="meta">Diagnostics appear once in the shared Diagnostics section. Test targets and attempts are separate from imported JUnit case totals. Artifact references are retained without downloading their contents. BEP event relationships are not target dependency edges.</p>'
        + content
        + "</section>"
    )
