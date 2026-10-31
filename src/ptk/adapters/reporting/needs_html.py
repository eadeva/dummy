"""Offline Sphinx evidence: descriptive charts and a filterable needs table."""

import json
from collections import Counter
from urllib.parse import quote

from . import ui
from .ui import anchor, e, fields, link


def need_link(need):
    if not need.page:
        return e(need.id)
    # Paths and fragment identifiers are encoded separately.
    from pathlib import Path

    return f'<a href="{e(Path(need.page).as_uri())}#{quote(need.id, safe="")}">{e(need.id)}</a>'


def chart(counts, title, field, *, pie=False):
    total = sum(counts.values())
    if not total:
        return f'<figure class="needs-chart"><figcaption>{e(title)}</figcaption><p class="meta">No needs imported.</p></figure>'
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    legend, shapes = [], []
    offset = 0.0
    for index, (label, count) in enumerate(ranked):
        color = f"var(--chart-{index % 8})"
        portion = count * 100 / total
        display = label or "Unspecified"
        legend.append(
            f'<li><button type="button" data-need-field="{field}" data-need-value="{e(label or "__unspecified__")}"><span class="chart-swatch" style="background:{color}"></span><span>{e(display)}</span><strong>{count}</strong><span class="meta">{portion:.1f}%</span></button></li>'
        )
        if pie:
            shapes.append(
                f'<circle cx="90" cy="90" r="65" fill="none" stroke="{color}" stroke-width="28" pathLength="100" stroke-dasharray="{portion:.6f} {100 - portion:.6f}" stroke-dashoffset="{-offset:.6f}" transform="rotate(-90 90 90)"/>'
            )
        else:
            shapes.append(
                f'<div class="needs-bar"><span>{e(display)}</span><span class="needs-bar-track"><span style="width:{count * 100 / max(counts.values()):.3f}%;background:{color}"></span></span><strong>{count}</strong></div>'
            )
        offset += portion
    description = "; ".join(
        f"{label or 'Unspecified'}: {count}" for label, count in ranked
    )
    graphic = (
        f'<svg viewBox="0 0 180 180" role="img" aria-label="{e(title + ": " + description)}">{"".join(shapes)}<text x="90" y="88" text-anchor="middle" class="donut-total">{total}</text><text x="90" y="108" text-anchor="middle" class="donut-label">needs</text></svg>'
        if pie
        else '<div class="needs-bars">' + "".join(shapes) + "</div>"
    )
    return f'<figure class="needs-chart"><figcaption>{e(title)}</figcaption><div class="needs-chart-body">{graphic}<ul class="chart-legend">{"".join(legend)}</ul></div></figure>'


def section(reports, root=None):
    from .html import owner

    datasets = [(owner(report), doc) for report in reports for doc in report.sphinx]
    if not datasets:
        return ""
    needs = [need for _, doc in datasets for need in doc.needs]
    types = Counter(need.type for need in needs)
    statuses = Counter(need.status for need in needs)
    rows, sources = [], []
    for index, (identity, doc) in enumerate(datasets):
        source_id = anchor("needs-source", index)
        source_links = " · ".join(
            filter(
                None,
                [
                    link(doc.needs_file, root, "needs.json"),
                    link(doc.violations_file, root, "schema_violations.json"),
                    link(doc.docs_index, root, "Open built documentation"),
                ],
            )
        )
        sources.append(
            f'<details id="{source_id}"><summary><span class="entity step">{e(identity)}[{e(doc.step)}]</span> · {e(doc.source)} · {len(doc.needs)} needs</summary><div class="item-detail">{fields({"Documentation project": doc.project or "Not recorded", "Documentation version": doc.version or "Unspecified", "Needs export": "Imported" if doc.needs_imported else "Unavailable", "Validation export": "Imported" if doc.violations_imported else "Unavailable; validation not reported", "Needs validated": doc.validated_needs if doc.validated_needs is not None else "Not recorded"})}<p>{e(doc.validation_summary)}</p><p>{source_links}</p></div></details>'
        )
        by_need = Counter(v.need_id for v in doc.violations)
        for need in doc.needs:
            level = next(
                (
                    level
                    for level in ("error", "warning", "note")
                    if any(
                        v.need_id == need.id and v.level == level
                        for v in doc.violations
                    )
                ),
                "none" if doc.violations_imported else "unreported",
            )
            validation = (
                f"{by_need[need.id]} findings"
                if by_need[need.id]
                else "No recorded findings"
                if doc.violations_imported
                else "Not reported"
            )
            attrs = {
                "owner": identity,
                "step": doc.step,
                "source": str(index),
                "type": need.type or "__unspecified__",
                "status": need.status or "__unspecified__",
                "validation": level,
            }
            attributes = " ".join(
                f'data-{key}="{e(value)}"' for key, value in attrs.items()
            )
            searchable = f"{identity} {doc.step} {doc.source} {need.id} {need.title} {json.dumps(need.fields, ensure_ascii=False)}"
            details = f'<details><summary>{e(need.title or "Untitled")}</summary><div class="item-detail">{fields({"Document": need.docname or "Not recorded", "Line": need.line or "Not recorded"})}<pre>{e(json.dumps(need.fields, ensure_ascii=False, indent=2))}</pre></div></details>'
            rows.append(
                f'<tr id="{anchor("need", index, need.id)}" data-record {attributes} data-search="{e(searchable)}"><td>{need_link(need)}</td><td>{details}</td><td>{e(need.type_name or need.type or "Unspecified")}</td><td>{e(need.status or "Unspecified")}</td><td>{e(", ".join(need.tags))}</td><td><span class="{e(level)}">{e(validation)}</span></td><td><a href="#{source_id}">{e(identity)}[{e(doc.step)}] · {e(doc.source)}</a></td></tr>'
            )

    def options(values):
        return [
            ("", "All"),
            *(
                (value or "__unspecified__", value or "Unspecified")
                for value in sorted(set(values))
            ),
        ]

    controls = ui.toolbar(
        "needs",
        {
            "type": ("Need type", options(types), ""),
            "status": ("Need status", options(statuses), ""),
            "owner": ("Need owner", options(identity for identity, _ in datasets), ""),
            "step": ("Need step", options(doc.step for _, doc in datasets), ""),
            "source": (
                "Need source",
                [
                    ("", "All sources"),
                    *(
                        (str(index), f"{identity}[{doc.step}] · {doc.source}")
                        for index, (identity, doc) in enumerate(datasets)
                    ),
                ],
                "",
            ),
            "validation": (
                "Need validation",
                [
                    ("", "All"),
                    ("error", "Errors"),
                    ("warning", "Warnings"),
                    ("note", "Notes"),
                    ("none", "No recorded findings"),
                    ("unreported", "Not reported"),
                ],
                "",
            ),
        },
    )
    violations = [v for _, doc in datasets for v in doc.violations]
    cards = ui.cards(
        {
            "Imported needs": len(needs),
            "Schema errors": sum(v.level == "error" for v in violations),
            "Schema warnings": sum(v.level == "warning" for v in violations),
            "Schema notes": sum(v.level == "note" for v in violations),
        },
        tones={"Schema errors": "failed", "Schema warnings": "warning"},
        targets={
            "Schema errors": "diagnostics",
            "Schema warnings": "diagnostics",
            "Schema notes": "diagnostics",
        },
    )
    return (
        '<section id="needs"><h2>Sphinx documentation</h2>'
        + cards
        + '<div class="docs-links">'
        + "".join(
            link(
                doc.docs_index,
                root,
                f"Open docs · {identity}[{doc.step}] · {doc.source}",
            )
            for identity, doc in datasets
            if doc.docs_index
        )
        + "</div>"
        + '<p class="meta">Counts describe imported need records, not tests, implementation progress or proof of correctness. Each source is counted separately; nested violation details are not additional findings.</p><details><summary>Needs charts and table</summary><div class="item-detail"><div class="needs-charts">'
        + chart(types, "Needs by type", "type", pie=True)
        + chart(statuses, "Needs by lifecycle status", "status")
        + '</div><p class="meta">Charts show all imported needs. Select a legend entry to filter the table; status labels are project-defined.</p><div id="needs-table" data-filter="needs">'
        + controls
        + '<div class="table-wrap"><table class="needs-table"><thead><tr><th scope="col">ID</th><th scope="col">Title and fields</th><th scope="col">Type</th><th scope="col">Status</th><th scope="col">Tags</th><th scope="col">Validation</th><th scope="col">Owner and source</th></tr></thead><tbody data-records>'
        + "".join(rows)
        + '</tbody></table></div><p data-filter-count aria-live="polite"></p></div></div></details><details><summary>Documentation sources and links</summary><div class="item-detail">'
        + "".join(sources)
        + '</div></details><p class="meta">Documentation links refer to the recorded build output and require those files to remain available. Needs data and violation details are retained with this report.</p></section>'
    )
