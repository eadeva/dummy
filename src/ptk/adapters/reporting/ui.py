"""Shared, offline presentation primitives for job and workflow reports."""

import os
from functools import cache
from html import escape
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote

from .. import graph_html


def e(value):
    return escape(str(value), quote=True)


def anchor(*parts):
    return "r-" + "-".join(str(part).encode().hex() for part in parts)


def link(path, root=None, label=None):
    if not path:
        return ""
    path = Path(path)
    if root is not None:
        try:
            href = quote(os.path.relpath(path, root).replace(os.sep, "/"))
        except ValueError:
            href = path.as_uri()
    else:
        href = path.as_uri() if path.is_absolute() else quote(str(path))
    return f'<a href="{e(href)}">{e(label or path.name)}</a>'


def badge(status, allowed=False):
    label = {"not_run": "Not run", "hidden": "Details hidden"}.get(
        status, str(status).title()
    )
    return f'<span class="badge {e(status)}">{e(label)}</span>' + (
        '<span class="badge allowed">Failure allowed</span>' if allowed else ""
    )


def cards(values, *, tones=None, targets=None):
    tones, targets = tones or {}, targets or {}
    rows = []
    for key, value in values.items():
        tone = tones.get(key, "info") if value else "info"
        title = e(key)
        if key in targets:
            title = f'<a href="#{e(targets[key])}">{title}</a>'
        rows.append(
            f'<div class="card-{e(tone)}"><dt>{title}</dt><dd>{e(value)}</dd></div>'
        )
    return '<dl class="cards">' + "".join(rows) + "</dl>"


def fields(values):
    return (
        '<dl class="fields">'
        + "".join(
            f"<dt>{e(key)}</dt><dd>{e(value)}</dd>" for key, value in values.items()
        )
        + "</dl>"
    )


def toolbar(kind, choices):
    """Each independently filtered collection has one toolbar."""
    selects = []
    for key, (label, options, default) in choices.items():
        options = "".join(
            f'<option value="{e(value)}"{" selected" if value == default else ""}>{e(text)}</option>'
            for value, text in options
        )
        selects.append(
            f'<label>{e(label)}<select name="{e(key)}" aria-label="{e(label)}">{options}</select></label>'
        )
    return f'<div class="filter-toolbar">{"".join(selects)}<label class="search-label">Search<input type="search" name="search" aria-label="Search {e(kind)}" placeholder="Search {e(kind)}"></label><button type="button" data-reset>Reset filters</button></div>'


def execution(entries, title):
    rows = []
    for item in entries:
        detail = item.get("detail", "")
        rows.append(
            f'<details class="execution-item" id="{e(item["target"])}" data-record data-status="{e(item["status"])}" data-owner="{e(item["owner"])}">'
            f'<summary><span class="entity {e(item["kind"])}">{e(item["label"])}</span><span>{badge(item["status"], item.get("allowed", False))}</span><span class="duration">{duration(item)}</span></summary>'
            f'<div class="item-detail"><p class="meta">{e(item["owner"])}</p>{detail}'
            f'<button type="button" data-show-graph="{e(item["target"])}">Show in graph</button></div></details>'
        )
    return (
        '<section id="execution"><h2>Execution</h2><p class="meta">'
        + e(title)
        + '</p><div data-filter="execution">'
        + toolbar(
            "execution",
            {
                "status": (
                    "Result",
                    [
                        ("", "All results"),
                        ("passed", "Passed"),
                        ("failed", "Failed"),
                        ("skipped", "Skipped"),
                        ("cancelled", "Cancelled"),
                        ("not_run", "Not run"),
                    ],
                    "",
                ),
            },
        )
        + "".join(rows)
        + '<p data-filter-count aria-live="polite"></p></div></section>'
    )


def duration(item):
    return (
        "—"
        if item["status"] in ("skipped", "pending", "not_run", "hidden")
        else f"{item['duration']:.2f}s"
    )


def timeline(entries, total):
    total = max(
        total, max((s["start"] + s["duration"] for s in entries), default=0), 0.001
    )
    rows = []
    for item in entries:
        state = "allowed" if item.get("allowed") else item["status"]
        left, width = 100 * item["start"] / total, 100 * item["duration"] / total
        rows.append(
            f'<a class="timeline-row" href="#{e(item["target"])}" title="{e(item["owner"])}: {e(item["status"])}"><span class="timeline-label">{e(item["label"])}</span><span class="track"><span class="bar {e(state)}" style="left:{left:.3f}%;width:{max(width, 0.3):.3f}%"></span></span><span class="duration">{duration(item)}</span></a>'
        )
    return (
        '<section id="timeline"><h2>Timeline</h2><p class="meta">Actual start offsets and elapsed durations; select a row for execution details.</p><div class="timeline"><div class="timeline-axis"><span>0s</span><span>'
        + f"{total:.2f}s"
        + "</span></div>"
        + "".join(rows)
        + '</div><p class="meta">Hatched bars: failure allowed. Skipped and not-run items have no execution duration.</p></section>'
    )


@cache
def assets():
    root = files("ptk.adapters.reporting").joinpath("assets")
    return root.joinpath("report.css").read_text(encoding="utf-8"), root.joinpath(
        "report.js"
    ).read_text(encoding="utf-8")


def page(
    *,
    title,
    kind,
    name,
    status,
    metadata,
    overview,
    failures,
    execution_html,
    graph,
    timeline_html,
    diagnostics,
    tests,
    evidence,
    configuration,
    needs="",
    cmake="",
    bazel="",
):
    css, script = assets()
    sections = [
        ("overview", "Overview"),
        ("failures", "What failed"),
        ("execution", "Execution"),
        ("graph", "Graph"),
        ("timeline", "Timeline"),
        ("diagnostics", "Diagnostics"),
    ]
    if tests:
        sections.append(("tests", "Tests"))
    if needs:
        sections.append(("needs", "Documentation"))
    if cmake:
        sections.append(("cmake", "CMake"))
    if bazel:
        sections.append(("bazel", "Bazel"))
    sections.extend([("evidence", "Evidence"), ("configuration", "Configuration")])
    navigation = "".join(f'<a href="#{key}">{label}</a>' for key, label in sections)
    metadata_html = (
        '<dl class="header-fields">'
        + "".join(
            f"<div><dt>{e(key)}</dt><dd>{e(value)}</dd></div>"
            for key, value in metadata.items()
        )
        + "</dl>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{css}</style></head>
<body><main><header class="run-header {e(kind)}"><p class="eyebrow">PTK · {e(kind.title())} report</p><div class="title-row"><h1>{e(kind.title())} - {e(name)}</h1><span class="execution-status">Execution {badge(status)}</span></div>{metadata_html}</header>
<nav class="section-nav" aria-label="Report sections">{navigation}</nav>
<section id="overview"><h2>Overview</h2>{overview}<p class="meta">Execution status and diagnostic evidence are independent. Test totals come from imported test results; log occurrences are not additional tests.</p></section>
{failures}{execution_html}<section id="graph">{graph}</section>{timeline_html}{diagnostics}{tests}{needs}{cmake}{bazel}
<section id="evidence"><h2>Evidence</h2>{evidence}</section>
<section id="configuration"><h2>Configuration</h2>{configuration}</section>
<footer>PTK records execution and project-supplied evidence. Project implementations own artifact correctness, validation, side effects and isolation; this flexibility lets each project choose its tools and checks.</footer>
</main><script>{script}</script>{graph_html.assets()}</body></html>"""
