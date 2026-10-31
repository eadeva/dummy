"""Native GN generation evidence and target overview in full reports."""

from collections import Counter

from .. import graph_html
from . import ui
from .ui import e, fields


def section(reports):
    from .html import owner

    datasets = [(owner(report), gn) for report in reports for gn in report.gn]
    if not datasets:
        return ""
    active = Counter(
        f.level
        for _, gn in datasets
        for f in gn.diagnostics
        if f.disposition == "active"
    )
    content = ui.cards(
        {
            "GN errors": active["error"],
            "GN warnings": active["warning"],
            "Configured targets": sum(len(g.targets) for _, g in datasets),
        },
        tones={"GN errors": "failed", "GN warnings": "warning"},
        targets={"GN errors": "diagnostics", "GN warnings": "diagnostics"},
    )
    for identity, gn in datasets:
        content += (
            "<details><summary>"
            + e(
                f"{identity}[{gn.step}] · GN {gn.version or 'version unavailable'} · generation {gn.status}"
            )
            + '</summary><div class="item-detail">'
        )
        content += fields(
            {
                "Executable": gn.executable,
                "Source root": gn.root,
                "Build directory": gn.build_dir,
                "Evidence": gn.source,
                "Generation result": gn.status,
                "Exit code": gn.exit_code
                if gn.exit_code is not None
                else "Not recorded",
                "Duration": f"{gn.duration:.2f}s",
                **gn.configuration,
            }
        )
        content += (
            "<details><summary>Available evidence</summary>"
            + fields(gn.availability)
            + "</details>"
        )
        if gn.graph:
            content += "<h3>Generated target dependencies</h3>" + graph_html.section(
                gn.graph, f"GN targets · {identity}[{gn.step}]"
            )
        else:
            content += (
                '<p class="meta">Target graph: '
                + e(gn.availability.get("target graph", "No native JSON evidence"))
                + "</p>"
            )
        if gn.targets:
            content += (
                '<h3>Configured targets</h3><div data-filter="GN targets">'
                + ui.toolbar("GN targets", {})
            )
            for target in gn.targets:
                content += (
                    "<details data-record><summary>"
                    + e(f"{target['id']} · {target['type']}")
                    + "</summary>"
                    + fields(
                        {
                            "Toolchain": target["toolchain"],
                            "Test-only": str(target["testonly"]),
                            "Dependencies": ", ".join(target["needs"]) or "None",
                        }
                    )
                    + "</details>"
                )
            content += '<p data-filter-count aria-live="polite"></p></div>'
        content += "</div></details>"
    return (
        '<section id="gn"><h2>GN</h2><p class="meta">Generation produces Ninja build files. Target records describe the generated configuration, not compilation or test results. Errors and warnings appear once in Diagnostics.</p>'
        + content
        + "</section>"
    )
