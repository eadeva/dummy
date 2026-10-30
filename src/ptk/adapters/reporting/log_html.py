"""Offline log analysis view. Severity and disposition are independent filters."""

import contextlib
import os
from html import escape
from pathlib import Path
from urllib.parse import quote

CSS = """
.log-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.log-cards button{font:inherit;text-align:left;border:1px solid var(--line);border-left:4px solid currentColor;border-radius:8px;padding:14px;cursor:pointer}
.log-cards strong{display:block;font-size:24px}.log-errors{background:var(--card-fail);color:var(--card-fail-ink)}
.log-warnings{background:var(--card-warn);color:var(--card-warn-ink)}.log-justified{background:var(--card-info);color:var(--card-info-ink)}
.log-ignored{background:var(--card-skip);color:var(--card-skip-ink)}
.log-analysis select,.log-analysis input,.log-reset{font:inherit;padding:7px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink);max-width:100%}
.log-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
.log-analysis{min-width:0}.log-analysis>summary{font-weight:600}
.log-finding{border:1px solid var(--line);border-left:4px solid var(--fail);border-radius:6px;padding:12px;margin:10px 0;overflow-wrap:anywhere}
.log-finding[data-severity=warning]{border-left-color:var(--card-warn-ink)}
.log-finding[data-disposition=justified],.log-finding[data-disposition=ignored]{border-left-color:var(--line)}
.log-finding summary{white-space:pre-wrap}.log-finding .meta{margin:0 0 8px}
.log-analysis pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:8px;margin:0}.log-analysis mark{background:var(--card-warn);color:var(--card-warn-ink);display:block}
.log-details{padding:8px;font-size:12px}.log-details p{margin:5px 0}.log-analysis .warning{color:var(--card-warn-ink)}
"""

SCRIPT = """
<script>
for(const section of document.querySelectorAll('.log-analysis')) {
  const severity=section.querySelector('[name=severity]'), disposition=section.querySelector('[name=disposition]');
  const step=section.querySelector('[name=step]'), search=section.querySelector('[name=search]');
  const rows=[...section.querySelectorAll('.log-finding')];
  const apply=()=>{
    let count=0, groups=0;
    for(const row of rows){
      row.hidden=!!((severity.value && row.dataset.severity!==severity.value) || (disposition.value && row.dataset.disposition!==disposition.value) || (step.value && row.dataset.step!==step.value) || (search.value && !row.dataset.search.toLowerCase().includes(search.value.toLowerCase())));
      if(!row.hidden){ count+=Number(row.dataset.count); groups++; }
    }
    section.querySelector('.log-status').textContent=`${count} occurrences in ${groups} diagnostic groups shown`;
  };
  for(const input of [severity,disposition,step,search]){input.addEventListener('input',apply);input.addEventListener('change',apply);}
  for(const card of section.querySelectorAll('[data-card]'))card.addEventListener('click',()=>{
    const key=card.dataset.card; disposition.value=['error','warning'].includes(key)?'active':key; severity.value=['error','warning'].includes(key)?key:'';apply();
  });
  section.querySelector('.log-reset').addEventListener('click',()=>{severity.value='';disposition.value='active';step.value='';search.value='';apply();});
  apply();
}
</script>
"""


def render(report, root=None, *, problems=()):
    failures = "".join(problems)
    heading = "What failed" if problems else "Diagnostics"
    if not report.log_analysis_enabled:
        return f"<section><h2>{heading}</h2>{failures}</section>" if problems else ""
    e = lambda value: escape(str(value), quote=True)
    totals = {"error": 0, "warning": 0, "justified": 0, "ignored": 0}
    for finding in report.log_findings:
        totals[
            finding.level if finding.disposition == "active" else finding.disposition
        ] += finding.occurrences
    cards = "".join(
        f'<button type="button" class="log-{css}" data-card="{key}" aria-label="Show {label.lower()}">{label}<strong>{totals[key]}</strong></button>'
        for key, css, label in [
            ("error", "errors", "Active log errors"),
            ("warning", "warnings", "Active log warnings"),
            ("justified", "justified", "Justified log findings"),
            ("ignored", "ignored", "Ignored log findings"),
        ]
    )
    steps = "".join(
        f'<option value="{e(step)}">{e(step)}</option>'
        for step in dict.fromkeys(f.step for f in report.log_findings)
    )
    entries = []
    # Stable sort preserves execution/import order within each severity.
    for f in sorted(report.log_findings, key=lambda f: f.level != "error"):
        path = Path(f.source_log)
        href = path.as_uri() if path.is_absolute() else quote(path.as_posix(), safe="/")
        if root:
            with contextlib.suppress(ValueError):
                href = quote(os.path.relpath(path, root).replace(os.sep, "/"), safe="/")
        log = f'<a href="{e(href)}" title="{e(f.source_log)}">{e(path.name)}</a>'
        context = "\n".join(
            f"<mark>{e(line)}</mark>" if line.startswith(f"{f.log_line}:") else e(line)
            for line in f.context
        )
        rule = (
            f"<p>Suppression rule: <code>{e(f.suppression_rule)}</code></p><p>Reason: {e(f.reason)}</p>"
            if f.suppression_rule
            else ""
        )
        details = f'<details><summary>{e(f.message)}</summary><div class="log-details"><p>Source log: {e(f.source_log)}</p><p>Log lines: {e(", ".join(map(str, f.log_lines)))}{" (first 50)" if f.occurrences > 50 else ""}</p><p>Diagnostic code: {e(f.rule or "—")}</p>{rule}</div><pre>{context}</pre></details>'
        location = (
            f"{f.file}:{f.line}"
            if f.file and f.line
            else f.file or f"Log line {f.log_line}"
        )
        searchable = f"{f.level} {f.disposition} {f.step} {f.message} {f.source_log} {f.file} {f.rule} {f.suppression_rule} {f.reason}"
        hidden = " hidden" if f.disposition != "active" else ""
        entries.append(
            f'<article class="log-finding" data-severity="{e(f.level)}" data-disposition="{e(f.disposition)}" data-step="{e(f.step)}" data-count="{f.occurrences}" data-search="{e(searchable)}"{hidden}>'
            f'<p class="meta"><strong>{e(f.step)}</strong> · {e(f.level.title())} · {e(f.disposition.title())} · {f.occurrences} occurrence(s)</p>'
            f'{details}<p class="meta">{log} · {e(location)}</p></article>'
        )
    clean = (
        "<p>No recognized active log diagnostics. Execution and imported test results are shown separately above when present.</p>"
        if not totals["error"] and not totals["warning"] and not report.problems
        else ""
    )
    open_attr = "" if problems else " open"
    return f"""<section><h2>{heading}</h2>{failures}
<details class="log-analysis"{open_attr}><summary>Log analysis</summary><div class="log-cards">{cards}</div>{clean}
<p class="meta">Counts cover recognized log occurrences only. A test failure can also appear in its captured log; these are separate views of the evidence, not additional failed tests. Justified and ignored findings are hidden by default. Analysis does not change execution status.</p>
<div class="log-toolbar">
<label>Severity <select name="severity" aria-label="Severity"><option value="">All severities</option><option value="error">Error</option><option value="warning">Warning</option></select></label>
<label>Disposition <select name="disposition" aria-label="Disposition"><option value="">All dispositions</option><option value="active" selected>Active</option><option value="justified">Justified</option><option value="ignored">Ignored</option></select></label>
<label>Step <select name="step" aria-label="Step"><option value="">All steps</option>{steps}</select></label><label>Search <input type="search" name="search" placeholder="Message, file or reason"></label><button type="button" class="log-reset">Reset filters</button></div>
{"".join(entries)}<p class="log-status" aria-live="polite"></p></details></section>"""
