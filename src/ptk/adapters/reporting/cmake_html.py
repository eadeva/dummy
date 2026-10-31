"""CMake evidence in the shared offline report, with independent probe outcomes."""

import json
from collections import Counter

from .. import graph_html
from . import ui
from .ui import e, fields


def section(reports):
    from .html import owner

    datasets = [(owner(report), cmake) for report in reports for cmake in report.cmake]
    if not datasets:
        return ""
    findings = [f for _, cmake in datasets for f in cmake.diagnostics]
    counts = Counter(f.level for f in findings if f.disposition == "active")
    content = ui.cards(
        {
            "CMake errors": counts["error"],
            "CMake warnings": counts["warning"],
            "Ignored": sum(f.disposition == "ignored" for f in findings),
            "Justified": sum(f.disposition == "justified" for f in findings),
            "Targets": sum(len(cmake.targets) for _, cmake in datasets),
        },
        tones={"CMake errors": "failed", "CMake warnings": "warning"},
        targets={"CMake errors": "diagnostics", "CMake warnings": "diagnostics"},
    )
    for identity, cmake in datasets:
        content += (
            "<details><summary>"
            + e(f"{identity}[{cmake.step}] · CMake {cmake.version} · {cmake.importer}")
            + '</summary><div class="item-detail">'
        )
        content += fields(
            {
                "Build directory": cmake.source,
                "Executable": cmake.executable,
                "Invocation result": cmake.status,
                "Duration": f"{cmake.duration:.2f}s",
                **cmake.configuration,
            }
        )
        content += (
            "<details><summary>Available evidence</summary>"
            + fields(cmake.availability)
            + "</details>"
        )
        for title, records in (
            ("Toolchains", cmake.toolchains),
            ("Configuration checks", cmake.checks),
            ("Package and file discovery", cmake.packages),
            ("Targets", cmake.targets),
        ):
            if not records:
                continue
            content += (
                f'<h3>{e(title)}</h3><div data-filter="{e(title)}">'
                + ui.toolbar(title, {})
            )
            for record in records:
                name = record.get("name", record.get("language", "Record"))
                result = record.get("result", record.get("type", ""))
                if "found" in record:
                    result = "found" if record["found"] else "not found"
                content += f"<details data-record><summary>{e(name)} · {e(result)}</summary><pre>{e(json.dumps(record, indent=2, ensure_ascii=False))}</pre></details>"
            content += '<p data-filter-count aria-live="polite"></p></div>'
        for config in dict.fromkeys(t["configuration"] for t in cmake.targets):
            targets = [t for t in cmake.targets if t["configuration"] == config]
            ids = {t["id"] for t in targets}
            graph = {
                "nodes": [
                    {
                        "id": t["id"],
                        "label": t["name"],
                        "needs": [n for n in t["needs"] if n in ids],
                        "message": t["type"],
                        "status": "configured",
                    }
                    for t in targets
                ],
                "tree": [],
                "notice": "Configured build dependencies, including transitive dependencies reported by CMake. This is not a record of which targets compiled successfully.",
            }
            content += graph_html.section(
                graph, f"CMake targets · {config or 'default'}"
            )
        content += "</div></details>"
    return (
        '<section id="cmake"><h2>CMake</h2><p class="meta">Warnings and errors use PTK diagnostic dispositions. Unsupported feature probes and missing optional packages are information, not failed tests. Diagnostics are listed once in the shared Diagnostics section.</p>'
        + content
        + "</section>"
    )
