"""Single-file HTML report (offline, no external resources, light/dark).

The centre piece is a timeline: every step is a bar at its real start time and
duration, so parallel sets and slow steps are visible at a glance.
"""

from __future__ import annotations

import contextlib
import json
import os
from html import escape
from pathlib import Path

from ...domain.reporting.model import (
    ERROR,
    FAILED,
    PASSED,
    SKIPPED,
    Report,
    ReportStep,
    test_metrics,
)

CSS = """
:root{--bg:#f3f5f8;--paper:#fff;--ink:#18212f;--muted:#5b6778;--line:#dce2ea;--accent:#0f7b8a;
--pass:#2b8a57;--fail:#c43d2f;--skip:#9aa5b4;--cancel:#b7791f;--code:#eef1f5;
--card-info:#eaf3ff;--card-info-ink:#245b91;--card-pass:#eaf7ee;--card-pass-ink:#216539;
--card-fail:#fff0ee;--card-fail-ink:#a92e24;--card-skip:#edf0f3;--card-skip-ink:#526071;
--card-warn:#fff6df;--card-warn-ink:#805600}
@media (prefers-color-scheme:dark){:root{--bg:#0f141b;--paper:#161d27;--ink:#e6ebf2;--muted:#95a1b2;
--line:#273140;--accent:#4fc3cf;--pass:#52c08a;--fail:#f07462;--skip:#5d6b7e;--cancel:#e3b341;--code:#1d2531;
--card-info:#182a40;--card-info-ink:#91c4fa;--card-pass:#182f24;--card-pass-ink:#82d5a2;
--card-fail:#392321;--card-fail-ink:#ffa397;--card-skip:#252c35;--card-skip-ink:#bdc6d2;
--card-warn:#352d1a;--card-warn-ink:#f0cb78}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1,h2{font-family:Charter,"Bitstream Charter","Sitka Text",Cambria,Georgia,serif;letter-spacing:-.01em;line-height:1.2}
code,pre{font-family:ui-monospace,"Cascadia Code","SF Mono",Consolas,monospace;font-size:13px}
code{background:var(--code);padding:1px 6px;border-radius:4px}
a{color:var(--accent)}
main{max-width:1180px;margin:0 auto;padding:32px 24px 24px}
.status{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 18px;padding-bottom:18px;
border-bottom:1px solid var(--line);margin-bottom:22px}
.status h1{margin:0;font-size:40px}
.verdict{font-size:22px;font-weight:700}
.passed{color:var(--pass)}.failed,.error{color:var(--fail)}.skipped{color:var(--skip)}.cancelled{color:var(--cancel)}
.meta{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0 20px}
.cards div{--card-bg:var(--card-info);--card-ink:var(--card-info-ink);
background:var(--card-bg);border:1px solid var(--line);border-left:4px solid var(--card-ink);
border-radius:8px;padding:14px;overflow-wrap:anywhere}
.cards .card-passed{--card-bg:var(--card-pass);--card-ink:var(--card-pass-ink)}
.cards .card-failed{--card-bg:var(--card-fail);--card-ink:var(--card-fail-ink)}
.cards .card-skipped{--card-bg:var(--card-skip);--card-ink:var(--card-skip-ink)}
.cards .card-warning{--card-bg:var(--card-warn);--card-ink:var(--card-warn-ink)}
.cards dt{color:var(--card-ink);font-size:13px}.cards dd{color:var(--card-ink);margin:4px 0 0;font-size:22px;font-weight:650}
section{margin:0 0 34px}
section>h2{font-size:24px;margin:0 0 10px}
.timeline{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:10px 14px}
.row{display:grid;grid-template-columns:minmax(140px,240px) 1fr 64px;gap:12px;align-items:center;
padding:3px 0;font-size:14px}
.row .label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .time{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.track{position:relative;height:16px;background:repeating-linear-gradient(90deg,transparent 0 calc(10% - 1px),var(--line) calc(10% - 1px) 10%)}
.bar{position:absolute;top:2px;bottom:2px;min-width:3px;border-radius:3px}
.bar.passed{background:var(--pass)}.bar.failed,.bar.error{background:var(--fail)}
.bar.skipped{background:transparent;border:1px dashed var(--skip)}.bar.cancelled{background:var(--cancel)}
.bar.allowed{background:repeating-linear-gradient(45deg,var(--fail) 0 4px,transparent 4px 8px);border:1px solid var(--fail)}
.row.set .label{font-weight:650}
.row.set .bar{top:6px;bottom:6px;background:transparent;border:2px solid var(--accent);border-top:none}
.legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--muted);font-size:13px;margin-top:8px}
.legend i{display:inline-block;width:12px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
.problem{border-left:3px solid var(--fail);background:var(--paper);padding:10px 14px;margin:0 0 10px;border-radius:0 6px 6px 0}
.problem pre{margin:6px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--paper);border:1px solid var(--line)}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:13px;background:var(--bg)}
.table-wrap{overflow-x:auto}
.column-filter{width:100%;min-width:100px;padding:7px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink)}
.filter-row td{background:var(--bg)}
.filter-status{font-size:12px;color:var(--muted);margin:5px 0}
[hidden]{display:none!important}
details{background:var(--paper);border:1px solid var(--line);border-radius:6px;margin:0 0 8px}
details>summary{cursor:pointer;padding:8px 12px}
details table{border:none;border-top:1px solid var(--line)}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
@media (max-width:700px){.row{grid-template-columns:110px 1fr 48px}.status h1{font-size:30px}}
"""


FILTER_SCRIPT = r"""
<script>
for (const table of document.querySelectorAll('table')) {
  const heading = table.rows[0];
  if (!heading) continue;
  const rows = Array.from(table.rows).slice(1);
  const filters = document.createElement('tr');
  filters.className = 'filter-row';
  const inputs = Array.from(heading.cells, (cell) => {
    const td = document.createElement('td');
    const input = document.createElement('input');
    input.type = 'search';
    input.className = 'column-filter';
    input.placeholder = 'Filter ' + cell.textContent.trim();
    input.setAttribute('aria-label', input.placeholder);
    td.append(input); filters.append(td);
    return input;
  });
  heading.after(filters);
  const status = document.createElement('p');
  status.className = 'filter-status';
  status.setAttribute('aria-live', 'polite');
  table.after(status);
  const apply = () => {
    const queries = inputs.map(input => input.value.trim().toLocaleLowerCase());
    let visible = 0;
    for (const row of rows) {
      row.hidden = !queries.every((query, i) =>
        (row.cells[i]?.textContent || '').toLocaleLowerCase().includes(query));
      if (!row.hidden) visible++;
    }
    status.textContent = visible + ' of ' + rows.length + ' rows shown';
  };
  inputs.forEach(input => input.addEventListener('input', apply));
  apply();
}
</script>
"""


def _e(text: object) -> str:
    return escape(str(text), quote=True)


def _link(path: str, root: Path | None) -> str:
    """Relative link from the report folder, so _logs and _reports can move together."""
    if not path:
        return ""
    href = Path(path).as_uri() if Path(path).is_absolute() else path
    if root is not None:
        with contextlib.suppress(ValueError):
            href = os.path.relpath(path, root).replace(os.sep, "/")
    return f'<a href="{_e(href)}">log</a>'


def _row(step: ReportStep, total: float) -> str:
    left = 100 * step.start / total if total else 0
    width = 100 * step.duration / total if total else 0
    status = "allowed" if step.allowed_failure else step.status
    title = f"{step.label}: {step.status}"
    if step.message:
        title += f" - {step.message}"
    if step.command:
        title += f"\n{step.command}"
    timing = f"{step.duration:.1f}s" if step.status in (PASSED, FAILED) else ""
    indent = f"padding-left:{step.depth * 16}px"
    cls = "row set" if step.kind == "set" else "row"
    return (
        f'<div class="{cls}" title="{_e(title)}"><span class="label" style="{indent}">'
        f'<span class="{_e(step.status)}">●</span> {_e(step.name)}</span>'
        f'<span class="track"><span class="bar {_e(status)}" '
        f'style="left:{left:.2f}%;width:{max(width, 0.3):.2f}%"></span></span>'
        f'<span class="time">{timing}</span></div>'
    )


def _cards(values, *, tones=None) -> str:
    tones = tones or {}
    return (
        '<dl class="cards">'
        + "".join(
            f'<div class="card-{_e(tones.get(k, "info"))}"><dt>{_e(k)}</dt><dd>{_e(v)}</dd></div>'
            for k, v in values.items()
        )
        + "</dl>"
    )


TEST_CARD_TONES = {"Passed": "passed", "Failed": "failed", "Skipped": "skipped"}


def _project_header(report: Report) -> str:
    context = report.context
    alias = context.get("repository_alias", report.project)
    versions = context.get("versions", {}).get("projects", {})
    version = versions.get(alias, {}).get("value", "Not recorded")
    variant = context.get("variant", {})
    content = _cards(
        {
            "Project": report.project,
            "Repository alias": alias,
            "PTK version": context.get("ptk_version") or "Not recorded",
            "Project version": version,
            "Variant": report.variant,
        }
    )
    if variant:
        content += f"<p>{_e(variant.get('description', ''))}</p>"
        content += f"<p><strong>Components:</strong> {_e(', '.join(variant.get('components', [])) or 'None')}</p>"
        content += f"<p><strong>Inheritance:</strong> {_e(' → '.join(variant.get('chain', [])) or 'None')}</p>"
        features = variant.get("features", {})
        if features:
            content += '<details><summary>Selected variant features</summary><div class="table-wrap"><table><tr><th>Feature</th><th>Value</th></tr>'
            content += "".join(
                f"<tr><td>{_e(k)}</td><td>{_e(json.dumps(v, ensure_ascii=False))}</td></tr>"
                for k, v in features.items()
            )
            content += "</table></div></details>"
    tools = list(context.get("tools", []))
    known = {tool["name"] for tool in tools}
    tools += [
        {"name": name}
        for name in context.get("required_tools", [])
        if name not in known
    ]
    content += "<h3>Tool dependencies</h3>"
    if tools:
        content += '<div class="table-wrap"><table><tr><th>Name</th><th>Version</th><th>Required</th><th>Source (executable)</th></tr>'
        content += "".join(
            f"<tr><td>{_e(t['name'])}</td><td>{_e(t.get('version') or 'Not detected')}</td><td>{_e(t.get('required') or 'Any')}</td><td>{_e(t.get('source') or 'Not recorded')}</td></tr>"
            for t in tools
        )
        content += "</table></div>"
    else:
        content += (
            '<p class="meta">No declared tool dependencies.</p>'
            if context
            else '<p class="meta">Tool dependencies were not recorded for this run.</p>'
        )
    return (
        '<section aria-label="Project information"><h2>Project information</h2>'
        + content
        + "</section>"
    )


def render(report: Report, *, link_root: Path | None = None) -> str:
    total = max(
        report.duration,
        max((s.start + s.duration for s in report.steps), default=0),
        0.001,
    )
    steps = [s for s in report.steps if s.kind != "set"]
    counts = {
        k: sum(1 for s in steps if s.status == k) for k in (PASSED, FAILED, SKIPPED)
    }
    allowed = sum(1 for s in steps if s.allowed_failure)
    parts = [
        (
            '<header class="status">'
            f"<h1>Job - {_e(report.job)}</h1>"
            f'<span class="verdict {_e(report.status)}">{_e(report.status)}</span>'
            f'<span class="meta">{_e(report.project)}, variant {_e(report.variant)}, '
            f"run {_e(report.run_id)}, {report.duration:.1f}s</span></header>"
        )
    ]
    parts.append(_project_header(report))
    figures = [
        ("Steps passed", counts[PASSED]),
        (
            "Steps failed",
            f"{counts[FAILED]} ({allowed} allowed)" if allowed else counts[FAILED],
        ),
        ("Steps skipped", counts[SKIPPED]),
    ]
    tests = report.test_totals()
    if tests:
        figures.append(("Tests", f"{tests[PASSED]}/{sum(tests.values())} passed"))
    if report.findings:
        figures.append(("Findings", len(report.findings)))
    for cov in report.coverage:
        figures.append((f"Coverage {cov.step}", f"{cov.percent:.1f}%"))
    parts.append(
        _cards(
            dict(figures),
            tones={
                "Steps passed": "passed",
                "Steps failed": "failed",
                "Steps skipped": "skipped",
                "Findings": "failed"
                if any(f.level == "error" for f in report.findings)
                else "warning",
            },
        )
    )

    problems = []
    for step in report.failed_steps():
        if step.allowed_failure:
            continue
        problems.append(
            f'<div class="problem"><strong>{_e(step.label)}</strong> {_e(step.status)}'
            f"{(': ' + _e(step.message)) if step.message else ''} {_link(step.log_file, link_root)}"
            f"{('<pre>' + _e(step.command) + '</pre>') if step.command else ''}</div>"
        )
    for suite in report.suites:
        for case in suite.cases:
            if case.status in (FAILED, ERROR) and len(problems) < 60:
                problems.append(
                    f'<div class="problem"><strong>{_e(case.classname)}.{_e(case.name)}</strong> '
                    f"{_e(case.status)} <span class=meta>({_e(suite.step)})</span>"
                    f"{('<pre>' + _e(case.message) + '</pre>') if case.message else ''}</div>"
                )
    for text in report.problems:
        problems.append(f'<div class="problem">{_e(text)}</div>')
    if problems:
        parts.append(f"<section><h2>What failed</h2>{''.join(problems)}</section>")

    legend = "".join(
        f'<span><i style="background:var(--{c})"></i>{_e(t)}</span>'
        for c, t in (
            ("pass", "passed"),
            ("fail", "failed"),
            ("skip", "skipped"),
            ("cancel", "cancelled"),
        )
    )
    parts.append(
        f'<section><h2>Timeline</h2><div class="timeline">'
        f"{''.join(_row(s, total) for s in report.steps)}</div>"
        f'<div class="legend">{legend}<span>hatched: failure allowed</span>'
        f"<span>bracket: step set</span></div></section>"
    )

    if report.params:
        rows = "".join(
            f"<tr><td><code>{_e(k)}</code></td><td><code>{_e(v)}</code></td>"
            f"<td>{_e(report.param_sources.get(k, ''))}</td></tr>"
            for k, v in report.params.items()
        )
        parts.append(
            "<section><h2>Parameters</h2><div class=table-wrap><table><tr><th>Name</th>"
            f"<th>Value</th><th>From</th></tr>{rows}</table></div></section>"
        )

    if report.suites:
        blocks = []
        for suite in report.suites:
            rows = "".join(
                f"<tr><td>{_e(c.classname)}</td><td>{_e(c.name)}</td>"
                f'<td class="{_e(c.status)}">{_e(c.status)}</td><td>{c.time:.2f}s</td></tr>'
                for c in suite.cases
            )
            summary = f"{_e(suite.step)}: {_e(suite.name)} - {suite.count(PASSED)}/{len(suite.cases)} passed"
            open_attr = " open" if suite.count(FAILED) + suite.count(ERROR) else ""
            blocks.append(
                f"<details{open_attr}><summary>{summary}</summary>"
                + _cards(test_metrics(suite.cases), tones=TEST_CARD_TONES)
                + "<div class=table-wrap><table>"
                f"<tr><th>Class</th><th>Test</th><th>Result</th><th>Time</th></tr>{rows}"
                "</table></div></details>"
            )
        parts.append(
            "<section><h2>Tests</h2>"
            + _cards(
                test_metrics(c for suite in report.suites for c in suite.cases),
                tones=TEST_CARD_TONES,
            )
            + '<p class="meta">Executed excludes skipped tests. Failed includes errors.</p>'
            + "".join(blocks)
            + "</section>"
        )

    if report.findings:
        rows = "".join(
            f'<tr><td class="{"failed" if f.level == "error" else ""}">{_e(f.level)}</td>'
            f"<td>{_e(f.tool)}</td><td><code>{_e(f.rule)}</code></td>"
            f"<td>{_e(f.file)}{(':' + str(f.line)) if f.line else ''}</td><td>{_e(f.message)}</td></tr>"
            for f in report.findings[:1000]
        )
        more = (
            f"<p class=meta>{len(report.findings) - 1000} more not shown.</p>"
            if len(report.findings) > 1000
            else ""
        )
        parts.append(
            "<section><h2>Findings</h2><div class=table-wrap><table><tr><th>Level</th><th>Tool</th>"
            f"<th>Rule</th><th>Location</th><th>Message</th></tr>{rows}</table></div>{more}</section>"
        )

    parts.append(
        f"<footer>ptk {_e(report.ptk_version)} report, started {_e(report.started_at)}. "
        "Regenerate with <code>ptk report export</code>.</footer>"
    )
    title = f"Job - {report.job} {report.status} - {report.project}"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body><main>"
        f"{''.join(parts)}</main>{FILTER_SCRIPT}</body></html>"
    )
