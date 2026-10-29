"""Render the full help as one self-contained HTML page and open it in the browser.

No external resources (works offline and behind a VPN); light and dark theme;
a search box filters the sections.
"""

from __future__ import annotations

import webbrowser
from html import escape
from pathlib import Path

from ..application.use_cases.help import HelpCommand, HelpDocument, HelpJob, HelpStep

CSS = """
:root{--bg:#f3f5f8;--paper:#ffffff;--ink:#18212f;--muted:#5b6778;--line:#dce2ea;--rail:#0f7b8a;
--rail-soft:#e3f2f4;--cond:#9a6514;--cond-soft:#fbf1df;--code:#eef1f5;--warn:#b4441f}
@media (prefers-color-scheme:dark){:root{--bg:#0f141b;--paper:#161d27;--ink:#e6ebf2;--muted:#95a1b2;
--line:#273140;--rail:#4fc3cf;--rail-soft:#14313a;--cond:#e3b341;--cond-soft:#33290f;--code:#1d2531;--warn:#f08a64}}
*{box-sizing:border-box}html{scroll-padding-top:20px}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1,h2,h3{font-family:Charter,"Bitstream Charter","Sitka Text",Cambria,Georgia,serif;font-weight:700;
letter-spacing:-.01em;line-height:1.2}
code,pre,kbd{font-family:ui-monospace,"Cascadia Code","JetBrains Mono","SF Mono",Consolas,monospace;font-size:13px}
code{background:var(--code);padding:1px 6px;border-radius:4px}
kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;font-size:12px}
a{color:var(--rail)}a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid var(--rail);outline-offset:2px}
.layout{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}
nav{position:sticky;top:0;height:100vh;overflow-y:auto;padding:24px 18px 32px;border-right:1px solid var(--line)}
nav .brand{font-family:Charter,"Bitstream Charter",Cambria,Georgia,serif;font-size:22px;font-weight:700;margin:0}
nav .meta{color:var(--muted);font-size:12px;margin:2px 0 16px}
nav input{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--paper);
color:var(--ink);font:inherit}
nav .hint{color:var(--muted);font-size:12px;margin:6px 2px 8px}
nav details>summary{cursor:pointer;color:var(--muted);font-size:14px;margin:4px 0;list-style-position:inside}
nav details:not([open])>summary{margin-bottom:0}
nav h2{font-size:13px;color:var(--muted);margin:20px 0 4px;font-family:inherit;font-weight:600;letter-spacing:0}
nav a{display:block;padding:3px 10px;margin-left:-10px;border-left:2px solid transparent;color:var(--ink);
text-decoration:none;font-size:14px}
nav a:hover{border-left-color:var(--rail);color:var(--rail)}
nav a.maint::after{content:"maintainer";font-size:11px;color:var(--cond);margin-left:6px}
main{padding:40px 48px 24px;max-width:1080px}
.hero{padding:8px 0 28px;border-bottom:1px solid var(--line);margin-bottom:28px}
.hero h1{font-size:44px;margin:0 0 6px}
.hero .lead{font-size:18px;color:var(--muted);max-width:62ch;margin:0 0 18px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:4px 24px;margin:0 0 20px}
.facts dt{color:var(--muted);font-size:13px}.facts dd{margin:0 0 8px;overflow-wrap:anywhere}
.problem{border-left:3px solid var(--warn);padding:8px 12px;background:var(--paper);margin:0 0 16px}
section.block{margin:0 0 44px}
section.block>h2{font-size:28px;margin:0 0 4px}
section.block>.lead{color:var(--muted);max-width:70ch;margin:0 0 14px}
h3{font-size:17px;margin:22px 0 8px}
.cmd{position:relative;margin:10px 0}
.cmd pre{margin:0;background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--rail);
padding:10px 70px 10px 14px;border-radius:4px;overflow-x:auto;white-space:pre}
.cmd button{position:absolute;top:6px;right:6px;font:12px system-ui,sans-serif;padding:3px 9px;border-radius:4px;
border:1px solid var(--line);background:var(--bg);color:var(--muted);cursor:pointer}
.cmd button:hover{color:var(--ink)}
.table-wrap{overflow-x:auto;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--paper);border:1px solid var(--line)}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:13px;background:var(--bg)}
tr:last-child td{border-bottom:none}
.tag{display:inline-block;font-size:12px;padding:0 7px;border-radius:3px;margin:0 4px 2px 0;
background:var(--code);color:var(--muted);white-space:nowrap}
.tag.req{background:var(--cond-soft);color:var(--cond)}
.tag.maint{background:transparent;color:var(--cond);border:1px solid var(--cond)}
.tag.def{background:var(--rail-soft);color:var(--rail)}
/* the pipeline: sequential steps on a rail, parallel sets as lanes */
ol.rail{list-style:none;margin:8px 0 0;padding:0 0 0 26px;position:relative}
ol.rail::before{content:"";position:absolute;left:8px;top:10px;bottom:14px;width:2px;background:var(--rail);opacity:.35}
.node{position:relative;margin:0 0 14px}
ol.rail>.node::before{content:"";position:absolute;left:-23px;top:6px;width:12px;height:12px;border-radius:50%;
background:var(--paper);border:2px solid var(--rail)}
ol.rail>.node.set::before{border-radius:3px;background:var(--rail)}
.node-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.node-name{font-weight:650}.node-title{color:var(--muted)}
.mode{font-size:13px;color:var(--rail)}
.node pre{margin:4px 0 0;background:var(--code);padding:6px 10px;border-radius:4px;overflow-x:auto;
white-space:pre-wrap;overflow-wrap:anywhere}
.cond{display:inline-block;margin-top:4px;font-size:13px;color:var(--cond);background:var(--cond-soft);
padding:1px 8px;border-radius:3px}
.cond code{background:transparent;padding:0;color:inherit}
.chips{margin-top:4px}
.lanes{list-style:none;padding-left:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-top:8px;
padding-top:10px;border-top:2px solid var(--rail)}
.lane{background:var(--paper);border:1px solid var(--line);border-top:3px solid var(--rail);border-radius:0 0 4px 4px;
padding:8px 12px}
.node.lane{margin:0}
.notes{margin:10px 0 0;padding-left:18px;color:var(--muted)}.notes li{margin:2px 0}
.empty{color:var(--muted);font-style:italic}
.hidden{display:none!important}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px;margin-top:20px}
@media (max-width:820px){.layout{grid-template-columns:minmax(0,1fr)}nav{position:static;height:auto;border-right:none;
border-bottom:1px solid var(--line)}main{padding:24px 16px}.hero h1{font-size:34px}}
@media print{nav,.cmd button{display:none}.layout{display:block}main{max-width:none;padding:0}}
"""

JS = """
const q=document.getElementById('q');
function filter(){const t=q.value.toLowerCase().trim();
document.querySelectorAll('main section.block').forEach(s=>s.classList.toggle('hidden',!!t&&!s.textContent.toLowerCase().includes(t)));
document.querySelectorAll('nav a[href^="#"]').forEach(a=>{const s=document.querySelector(a.getAttribute('href'));
a.classList.toggle('hidden',!!(s&&s.classList.contains('hidden')))});}
q.addEventListener('input',()=>{filter();if(q.value)toc.open=true;});
const toc=document.querySelector('nav details');
if(window.matchMedia('(max-width:820px)').matches)toc.open=false;
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();q.select();}
else if(e.key==='Escape'&&document.activeElement===q){q.value='';filter();q.blur();}});
document.querySelectorAll('.cmd button').forEach(b=>b.addEventListener('click',()=>{
const text=b.parentElement.querySelector('pre').innerText;const done=()=>{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1500)};
if(navigator.clipboard){navigator.clipboard.writeText(text).then(done,()=>{})}else{const r=document.createRange();
r.selectNodeContents(b.parentElement.querySelector('pre'));const sel=getSelection();sel.removeAllRanges();sel.addRange(r);
document.execCommand('copy');sel.removeAllRanges();done();}}));
"""


def _e(text: object) -> str:
    return escape(str(text), quote=True)


def _anchor(prefix: str, name: str) -> str:
    return prefix + "-" + "".join(c if c.isalnum() else "-" for c in name.lower())


def _cmd(text: str) -> str:
    return f'<div class="cmd"><pre>{_e(text)}</pre><button type="button">Copy</button></div>'


def _tags(items: list[str], cls: str = "") -> str:
    return "".join(f'<span class="tag {cls}">{_e(i)}</span>' for i in items)


def _node(step: HelpStep, extra: str = "") -> str:
    title = f'<span class="node-title">{_e(step.title)}</span>' if step.title else ""
    head = (
        f'<div class="node-head"><span class="node-name">{_e(step.name)}</span>{title}'
    )
    cond = (
        f'<div class="cond">only if <code>{_e(step.when)}</code></div>'
        if step.when
        else ""
    )
    chips = f'<div class="chips">{_tags(step.flags)}</div>' if step.flags else ""
    if step.kind == "set":
        parallel = step.detail == "parallel"
        head += f'<span class="mode">{"runs in parallel" if parallel else "runs in order"}</span></div>'
        if parallel:
            inner = (
                '<ul class="lanes">'
                + "".join(_node(c, " lane") for c in step.children)
                + "</ul>"
            )
        else:
            inner = _rail(step.children)
        return f'<li class="node set{extra}">{head}{cond}{chips}{inner}</li>'
    return f'<li class="node{extra}">{head}</div><pre>{_e(step.detail)}</pre>{cond}{chips}</li>'


def _rail(steps: list[HelpStep]) -> str:
    return '<ol class="rail">' + "".join(_node(s) for s in steps) + "</ol>"


def _job(job: HelpJob) -> str:
    badge = (
        ' <span class="tag maint">maintainer only</span>'
        if job.audience == "maintainer"
        else ""
    )
    if job.is_default:
        badge += ' <span class="tag def">default job</span>'
    parts = [
        f'<section class="block" id="{_anchor("job", job.name)}"><h2>{_e(job.name)}{badge}</h2>',
        f'<p class="lead">{_e(job.help)}</p>'
        if job.help
        else '<p class="lead empty">No description.</p>',
        _cmd(job.usage),
    ]
    if job.params:
        rows = "".join(
            f"<tr><td><code>{_e(p.option)}</code>{' <span class="tag req">required</span>' if p.required else ''}</td>"
            f"<td>{_e(p.type)}{('<br>' + _tags(p.choices)) if p.choices else ''}</td>"
            f"<td>{('<code>' + _e(p.default) + '</code>') if p.default else '–'}</td>"
            f"<td>{('<code>' + _e(p.env) + '</code>') if p.env else '–'}</td><td>{_e(p.help)}</td></tr>"
            for p in job.params
        )
        parts.append(
            '<h3>Parameters</h3><div class="table-wrap"><table><tr><th>Option</th><th>Type</th>'
            f"<th>Default</th><th>From env</th><th>Description</th></tr>{rows}</table></div>"
        )
    parts.append(f"<h3>Steps</h3>{_rail(job.steps)}")
    notes = [
        "Start or stop at a top-level step with <code>--from</code> / <code>--to</code>: "
        + ", ".join(f"<code>{_e(p)}</code>" for p in job.phases)
    ]
    if job.passthrough:
        notes.append(
            "Arguments after <code>--</code> go to "
            + ", ".join(f"<code>{_e(p)}</code>" for p in job.passthrough)
        )
    if job.requires_tools:
        notes.append(
            "Needs the tools "
            + ", ".join(f"<code>{_e(t)}</code>" for t in job.requires_tools)
        )
    notes.append(
        f"Preview without running: <code>ptk {'maintainer ' if job.audience == 'maintainer' else ''}{_e(job.name)} --dry-run</code>"
    )
    if job.is_default:
        notes.append(
            "This is the default job: plain <code>ptk</code> or "
            "<code>ptk run</code> runs it"
        )
    parts.append(
        '<ul class="notes">'
        + "".join(f"<li>{n}</li>" for n in notes)
        + "</ul></section>"
    )
    return "".join(parts)


def _command(cmd: HelpCommand) -> str:
    rows = "".join(
        f"<tr><td><code>{_e(o.names)}</code></td><td>{_e(o.help)}"
        f"{(' <span class="tag">default ' + _e(o.default) + '</span>') if o.default else ''}</td></tr>"
        for o in cmd.options
    )
    table = f'<div class="table-wrap"><table>{rows}</table></div>' if rows else ""
    text = "".join(f"<p>{_e(par)}</p>" for par in cmd.help.split("\n\n") if par.strip())
    return (
        f'<section class="block" id="{_anchor("cmd", cmd.path or "ptk")}"><h2>ptk {_e(cmd.path)}</h2>'
        f"{_cmd(cmd.usage)}{text}{table}</section>"
    )


def _table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><tr>{th}</tr>{body}</table></div>'


def render(doc: HelpDocument) -> str:
    name = doc.project or "ptk"
    nav = [
        f'<p class="brand">{_e(name)}</p>',
        (
            f'<p class="meta">ptk {_e(doc.version)}, generated {_e(doc.generated)}'
            f"{', maintainer view' if doc.role == 'maintainer' else ''}</p>"
        ),
        '<input id="q" type="search" placeholder="Search" aria-label="Search the help">',
        '<p class="hint">Press <kbd>/</kbd> to search</p>',
        "<details open><summary>Contents</summary>",
        '<a href="#top">Overview</a>',
    ]
    body: list[str] = []

    hero = [f'<header class="hero" id="top"><h1>{_e(name)}</h1>']
    hero.append(
        f'<p class="lead">{_e(doc.description)}</p>'
        if doc.description
        else '<p class="lead">Everything this project can do with ptk: jobs, their parameters and steps, '
        "variants and commands.</p>"
    )
    if doc.error:
        hero.append(
            f'<p class="problem">The project configuration could not be loaded, so only the built-in '
            f"commands are listed. Fix it and run <code>ptk help</code> again.<br>{_e(doc.error)}</p>"
        )
    if doc.project:
        facts = [
            ("Project folder", doc.root),
            ("Default job", doc.default_job or "none"),
            ("Configuration", " → ".join(doc.layers)),
        ]
        hero.append(
            '<dl class="facts">'
            + "".join(f"<div><dt>{_e(k)}</dt><dd>{_e(v)}</dd></div>" for k, v in facts)
            + "</dl>"
        )
    hero.append(
        _cmd(
            "ptk                               # run the default job\n"
            "ptk JOB --dry-run                # see what would run\n"
            "ptk JOB --NAME VALUE           # run it with a parameter\n"
            "ptk JOB --from STEP -- ARGS\n"
            "ptk variant list"
        )
    )
    if doc.hidden_jobs:
        hero.append(
            f'<p class="meta">{doc.hidden_jobs} maintainer-only job(s) are not listed.</p>'
        )
    hero.append("</header>")
    body.append("".join(hero))

    if doc.jobs:
        nav.append("<h2>Jobs</h2>")
        for job in doc.jobs:
            cls = ' class="maint"' if job.audience == "maintainer" else ""
            nav.append(f'<a href="#{_anchor("job", job.name)}"{cls}>{_e(job.name)}</a>')
            body.append(_job(job))

    project_links = []
    if doc.variants:
        project_links.append('<a href="#variants">Variants</a>')
        rows = [
            [
                f"<code>{_e(v.name)}</code>"
                + (' <span class="tag def">default</span>' if v.default else "")
                + (' <span class="tag">abstract</span>' if v.abstract else ""),
                _tags(v.aliases) or "–",
                _e(", ".join(v.extends)) or "–",
                _e(v.description),
            ]
            for v in doc.variants
        ]
        body.append(
            '<section class="block" id="variants"><h2>Variants</h2><p class="lead">Choose one with '
            "<code>-V NAME</code> (a name or an alias). <code>ptk variant show NAME</code> shows every "
            "feature value.</p>"
            + _table(["Variant", "Aliases", "Based on", "Description"], rows)
            + "</section>"
        )
    if doc.credentials:
        project_links.append('<a href="#credentials">Credentials</a>')
        rows = [
            [
                f"<code>{_e(c.name)}</code>",
                _e(c.description) or "–",
                "<br>".join(f"{_e(f)}: <code>{_e(v)}</code>" for f, v in c.env.items()),
                _e(" → ".join(c.providers)),
            ]
            for c in doc.credentials
        ]
        body.append(
            '<section class="block" id="credentials"><h2>Credentials</h2><p class="lead">Values never '
            "appear here. Commands receive them only as environment variables, and they are masked in "
            "all output.</p>"
            + _table(
                ["Name", "Used for", "Environment variables", "Looked up in"], rows
            )
            + "</section>"
        )
    if doc.tools:
        project_links.append('<a href="#tools">Tools</a>')
        rows = [
            [
                f"<code>{_e(t.name)}</code>",
                _e(t.version) or "any",
                _e(", ".join(t.sources)) or "–",
                _e(t.description),
            ]
            for t in doc.tools
        ]
        body.append(
            '<section class="block" id="tools"><h2>Tools</h2>'
            + _table(["Tool", "Version", "Installed with", "Description"], rows)
            + "</section>"
        )
    if doc.files:
        project_links.append('<a href="#files">Configuration files</a>')
        body.append(
            '<section class="block" id="files"><h2>Configuration files</h2><p class="lead">Read in this '
            'order; later files override earlier ones.</p><ul class="notes">'
            + "".join(f"<li><code>{_e(f)}</code></li>" for f in doc.files)
            + "</ul></section>"
        )
    if project_links:
        nav.append("<h2>Project</h2>" + "".join(project_links))

    nav.append("<h2>Commands</h2>")
    for cmd in doc.commands:
        nav.append(
            f'<a href="#{_anchor("cmd", cmd.path or "ptk")}">{_e(cmd.path or "ptk")}</a>'
        )
        body.append(_command(cmd))
    nav.append("</details>")

    title = f"{name} help"
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>'
        f'<style>{CSS}</style></head><body><div class="layout"><nav aria-label="Contents">{"".join(nav)}</nav>'
        f"<main>{''.join(body)}<footer>Generated by ptk {_e(doc.version)} on {_e(doc.generated)}. "
        f"Run <code>ptk help</code> to refresh.</footer></main></div><script>{JS}</script></body></html>"
    )


def write_help(doc: HelpDocument, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(doc), encoding="utf-8")
    return target


def open_in_browser(path: Path) -> bool:
    """False when no browser is available (e.g. a Linux server without a desktop)."""
    try:
        return webbrowser.open(path.resolve().as_uri())
    except webbrowser.Error:
        return False
