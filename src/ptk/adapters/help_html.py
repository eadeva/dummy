"""Render the full help as one self-contained HTML page and open it in the browser.

No external resources (works offline and behind a VPN); light and dark theme;
a search box filters the sections.
"""

from __future__ import annotations

import webbrowser
from html import escape
from pathlib import Path

from ..application.use_cases.help import (
    HelpAssistant,
    HelpCommand,
    HelpDocument,
    HelpJob,
    HelpStep,
    HelpWorkflow,
    HelpWorkspace,
)
from . import graph_html

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
nav details.grp{margin:2px 0}
nav details.grp>summary{color:var(--ink);font-weight:600;font-size:14px;margin:6px 0 2px}
nav details.grp details.grp{margin-left:12px}
nav details.grp details.grp>summary{font-weight:500}
nav details.grp>a,nav details.grp>details{margin-left:4px}
nav .count{color:var(--muted);font-weight:400;font-size:12px}
nav details.repo-grp>summary{font-size:15px}
nav a[class*="ent-"]::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;
margin-right:7px;background:var(--muted);vertical-align:middle}
nav a.ent-job::before{background:#3b82f6}nav a.ent-gui::before{background:#06b6d4}
nav a.ent-workflow::before{background:#a855f7}nav a.ent-skill::before{background:#16a34a}
.group-head{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600;
margin:40px 0 14px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.repo-head{font-size:34px;margin:56px 0 8px;padding-top:16px;border-top:3px solid var(--rail)}
.repo-head .meta{font-size:16px;color:var(--muted);font-weight:400;margin-left:8px}
section.cmd-block.depth-1{margin-left:16px}section.cmd-block.depth-2{margin-left:32px}
section.cmd-block.depth-3{margin-left:48px}
main{padding:40px 48px 24px;min-width:0}
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
/* Named steps and their declared dependencies. */
ul.steps{list-style:none;margin:0;padding:0}
.node{margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:6px}
.node-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.node-name{font-weight:650}.node-title{color:var(--muted)}
.node pre{margin:4px 0 0;background:var(--code);padding:6px 10px;border-radius:4px;overflow-x:auto;
white-space:pre-wrap;overflow-wrap:anywhere}
.cond{display:inline-block;margin-top:4px;font-size:13px;color:var(--cond);background:var(--cond-soft);
padding:1px 8px;border-radius:3px}
.cond code{background:transparent;padding:0;color:inherit}
.chips{margin-top:4px}
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
const toc=document.querySelector('nav details.toc');
function openTo(el){for(let d=el&&el.parentElement;d;d=d.parentElement){if(d.tagName==='DETAILS')d.open=true;}}
function filter(){const t=q.value.toLowerCase().trim();
document.querySelectorAll('main section.block').forEach(s=>s.classList.toggle('hidden',!!t&&!s.textContent.toLowerCase().includes(t)));
document.querySelectorAll('nav a[href^="#"]').forEach(a=>{const s=document.getElementById(a.getAttribute('href').slice(1));
const hide=!!t&&!!(s&&s.classList.contains('hidden'))&&!a.textContent.toLowerCase().includes(t);a.classList.toggle('hidden',hide);
if(t&&!hide)openTo(a);});
document.querySelectorAll('nav details.grp').forEach(d=>d.classList.toggle('hidden',!!t&&!d.querySelector('a:not(.hidden)')));}
q.addEventListener('input',()=>{filter();if(q.value)toc.open=true;});
function follow(){const id=decodeURIComponent(location.hash.slice(1));if(!id)return;
openTo(document.querySelector(`nav a[href="#${CSS.escape(id)}"]`));}
window.addEventListener('hashchange',follow);follow();
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
    return prefix + "-" + _slug(name)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower())


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
    return f'<li class="node{extra}">{head}</div><pre>{_e(step.detail)}</pre>{cond}{chips}</li>'


def _steps(steps: list[HelpStep]) -> str:
    return '<ul class="steps">' + "".join(_node(s) for s in steps) + "</ul>"


def _with_prefix(text: str, prefix: str) -> str:
    """Insert the repository alias after ``ptk`` for VMR command lines."""
    if prefix and (text == "ptk" or text.startswith("ptk ")):
        return f"ptk {prefix}{text[3:]}"
    return text


def _job(job: HelpJob, ns: str = "", prefix: str = "") -> str:
    badge = (
        ' <span class="tag maint">maintainer only</span>'
        if job.audience == "maintainer"
        else ""
    )
    if job.gui:
        badge += ' <span class="tag">GUI</span>'
    if job.is_default:
        badge += ' <span class="tag def">default job</span>'
    parts = [
        f'<section class="block" id="{_anchor(ns + "job", job.name)}"><h2>{_e(job.name)}{badge}</h2>',
        f'<p class="lead">{_e(job.help)}</p>'
        if job.help
        else '<p class="lead empty">No description.</p>',
        _cmd(_with_prefix(job.usage, prefix)),
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
    parts.append(f"<h3>Steps</h3>{_steps(job.steps)}")
    if len(job.steps) > 1:
        parts.append(
            graph_html.section(
                {
                    "nodes": [
                        {
                            "id": s.name,
                            "label": s.title or s.name,
                            "needs": s.needs,
                            "message": s.detail,
                            "status": "configured",
                        }
                        for s in job.steps
                    ],
                    "tree": [],
                    "caption": "Configured step dependencies: prerequisites → dependents. Independent steps can overlap.",
                },
                f"Steps of job {job.name}",
            )
        )
    notes = [
        "Run a step and its prerequisites with <code>--to STEP</code>, or explicitly bypass prerequisites with <code>--only-step STEP</code>: "
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
        "Preview without running: <code>"
        + _e(
            _with_prefix(
                f"ptk {'maintainer ' if job.audience == 'maintainer' else ''}{job.name} --dry-run",
                prefix,
            )
        )
        + "</code>"
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


def _command(cmd: HelpCommand, ns: str = "", prefix: str = "") -> str:
    rows = "".join(
        f"<tr><td><code>{_e(o.names)}</code></td><td>{_e(o.help)}"
        f"{(' <span class="tag">default ' + _e(o.default) + '</span>') if o.default else ''}</td></tr>"
        for o in cmd.options
    )
    table = f'<div class="table-wrap"><table>{rows}</table></div>' if rows else ""
    text = "".join(f"<p>{_e(par)}</p>" for par in cmd.help.split("\n\n") if par.strip())
    depth = min(cmd.path.count(" "), 3) if cmd.path else 0
    title = _with_prefix(f"ptk {cmd.path}".rstrip(), prefix)
    return (
        f'<section class="block cmd-block depth-{depth}" id="{_anchor(ns + "cmd", cmd.path or "ptk")}">'
        f"<h2>{_e(title)}</h2>"
        f"{_cmd(_with_prefix(cmd.usage, prefix))}{text}{table}</section>"
    )


def _table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><tr>{th}</tr>{body}</table></div>'


def _link(target: str, label: str, cls: str = "") -> str:
    css = f' class="{cls}"' if cls else ""
    return f'<a href="#{target}"{css}>{_e(label)}</a>'


def _group(title: str, items: list[str], *, opened: bool, cls: str = "") -> str:
    if not items:
        return ""
    state = " open" if opened else ""
    return (
        f'<details class="grp {cls}"{state}><summary>{_e(title)} '
        f'<span class="count">{len(items)}</span></summary>{"".join(items)}</details>'
    )


def _command_tree(commands: list[HelpCommand], ns: str) -> list[str]:
    """Nest command paths like the extension: self-service > creds > set."""
    tree: dict = {}
    for cmd in commands:
        if not cmd.path:
            continue
        node = tree
        for part in cmd.path.split():
            node = node.setdefault(part, {})
    paths = {cmd.path for cmd in commands}

    def render_level(level: dict, path: list[str]) -> list[str]:
        items = []
        for name, children in level.items():
            full = " ".join([*path, name])
            target = _anchor(ns + "cmd", full)
            if children:
                own = [_link(target, "overview", "ent-cmd")] if full in paths else []
                items.append(
                    f'<details class="grp"><summary>{_e(name)}</summary>'
                    + "".join(own + render_level(children, [*path, name]))
                    + "</details>"
                )
            else:
                items.append(_link(target, name, "ent-cmd"))
        return items

    root = [_link(_anchor(ns + "cmd", "ptk"), "ptk (global options)", "ent-cmd")]
    return (root if "" in paths else []) + render_level(tree, [])


def _workflow(wf: HelpWorkflow, ns: str = "", prefix: str = "") -> str:
    badge = (
        ' <span class="tag maint">maintainer only</span>'
        if wf.audience == "maintainer"
        else ""
    )
    rows = [
        [f"<code>{_e(key)}</code>", _e(", ".join(needs)) or "–"]
        for key, needs in wf.jobs
    ]
    usage = wf.usage or (
        f"ptk {'maintainer ' if wf.audience == 'maintainer' else ''}workflow run {wf.name}"
    )
    return (
        f'<section class="block" id="{_anchor(ns + "wf", wf.name)}"><h2>{_e(wf.name)}{badge}</h2>'
        + (
            f'<p class="lead">{_e(wf.help)}</p>'
            if wf.help
            else '<p class="lead empty">No description.</p>'
        )
        + _cmd(_with_prefix(usage, prefix) + " [--dry-run]")
        + "<h3>Jobs</h3>"
        + _table(["Job", "Needs"], rows)
        + graph_html.section(
            {
                "nodes": [
                    {
                        "id": key,
                        "label": key,
                        "needs": needs,
                        "message": "needs " + ", ".join(needs) if needs else "ready",
                        "status": "configured",
                    }
                    for key, needs in wf.jobs
                ],
                "tree": [],
                "caption": "Configured job dependencies: prerequisites → dependents. Independent jobs can run in parallel up to max_workers.",
            },
            f"Workflow {wf.name}",
        )
        + "</section>"
    )


def _project_parts(doc: HelpDocument, ns: str = "") -> tuple[list[str], list[str]]:
    """Navigation groups and page sections of one repository, in extension order."""
    nav: list[str] = []
    body: list[str] = []
    prefix = doc.prefix
    for title, kind, jobs in (
        ("Jobs", "job", [j for j in doc.jobs if not j.gui]),
        ("GUIs", "gui", [j for j in doc.jobs if j.gui]),
    ):
        links = []
        if jobs:
            body.append(f'<p class="group-head" id="{ns}g-{kind}s">{title}</p>')
        for job in jobs:
            cls = f"ent-{kind}" + (" maint" if job.audience == "maintainer" else "")
            links.append(_link(_anchor(ns + "job", job.name), job.name, cls))
            body.append(_job(job, ns, prefix))
        nav.append(_group(title, links, opened=True))
    if doc.workflows:
        body.append(f'<p class="group-head" id="{ns}g-workflows">Workflows</p>')
    links = []
    for wf in doc.workflows:
        cls = "ent-workflow" + (" maint" if wf.audience == "maintainer" else "")
        links.append(_link(_anchor(ns + "wf", wf.name), wf.name, cls))
        body.append(_workflow(wf, ns, prefix))
    nav.append(_group("Workflows", links, opened=True))

    if doc.commands:
        body.append(f'<p class="group-head" id="{ns}g-commands">Built-in commands</p>')
        body.extend(_command(cmd, ns, prefix) for cmd in doc.commands)
        nav.append(
            _group("Built-in commands", _command_tree(doc.commands, ns), opened=False)
        )

    config_links = []
    config_body = []
    if doc.variants:
        config_links.append(_link(f"{ns}variants", "Variants"))
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
        config_body.append(
            f'<section class="block" id="{ns}variants"><h2>Variants</h2><p class="lead">Choose one with '
            "<code>-V NAME</code> (a name or an alias). <code>ptk variant show NAME</code> shows every "
            "feature value.</p>"
            + _table(["Variant", "Aliases", "Based on", "Description"], rows)
            + "</section>"
        )
    if doc.credentials:
        config_links.append(_link(f"{ns}credentials", "Credentials"))
        rows = [
            [
                f"<code>{_e(c.name)}</code>",
                _e(c.description) or "–",
                "<br>".join(f"{_e(f)}: <code>{_e(v)}</code>" for f, v in c.env.items()),
                _e(" → ".join(c.providers)),
            ]
            for c in doc.credentials
        ]
        config_body.append(
            f'<section class="block" id="{ns}credentials"><h2>Credentials</h2><p class="lead">Values never '
            "appear here. Commands receive them only as environment variables, and they are masked in "
            "all output.</p>"
            + _table(
                ["Name", "Used for", "Environment variables", "Looked up in"], rows
            )
            + "</section>"
        )
    if doc.tools:
        config_links.append(_link(f"{ns}tools", "Tools"))
        rows = [
            [
                f"<code>{_e(t.name)}</code>",
                _e(t.version) or "any",
                _e(", ".join(t.sources)) or "–",
                _e(t.description),
            ]
            for t in doc.tools
        ]
        config_body.append(
            f'<section class="block" id="{ns}tools"><h2>Tools</h2>'
            + _table(["Tool", "Version", "Installed with", "Description"], rows)
            + "</section>"
        )
    if doc.files:
        config_links.append(_link(f"{ns}files", "Configuration files"))
        config_body.append(
            f'<section class="block" id="{ns}files"><h2>Configuration files</h2><p class="lead">Read in this '
            'order; later files override earlier ones.</p><ul class="notes">'
            + "".join(f"<li><code>{_e(f)}</code></li>" for f in doc.files)
            + "</ul></section>"
        )
    if config_body:
        body.append(f'<p class="group-head" id="{ns}g-configuration">Configuration</p>')
        body.extend(config_body)
    nav.append(_group("Configuration", config_links, opened=False))
    return [n for n in nav if n], body


ASSISTANT_TASKS = (
    "Create and change jobs, steps, parameters, GUIs and workflows",
    "Set up variants, tools, credentials, Python environments and versioning",
    "Diagnose failed runs from logs and reports, and suggest narrowly scoped fixes",
    "Maintain shared configurations, Git hooks and VMR workspaces",
    "Prepare GitHub workflow templates and artifact handoff for CX",
)


def _assistant(info: HelpAssistant | None, ns: str = "") -> tuple[str, str]:
    if info is None:
        return "", ""
    if info.installed_repositories:
        status = (
            "Installed in "
            + ", ".join(f"<code>{_e(r)}</code>" for r in info.installed_repositories)
            + ". In VS Code, select the <code>ptk-expert</code> agent in Copilot Chat. "
            "Install or update it per repository with <code>ptk maintainer sync agent</code>."
        )
    elif info.installed_version:
        status = (
            f"Installed in this repository (PTk {_e(info.installed_version)}). In VS Code, "
            "select the <code>ptk-expert</code> agent in Copilot Chat or mention a skill. "
            "Update it with <code>ptk maintainer sync agent</code>."
        )
    else:
        status = (
            "Not installed in this repository yet. A maintainer installs the agent, its skills "
            "and offline docs into <code>.github</code> with <code>ptk maintainer sync agent</code>."
        )
    rows = [[f"<code>{_e(s.name)}</code>", _e(s.description)] for s in info.skills]
    body = (
        f'<p class="group-head" id="{ns}g-assistant">AI assistant</p>'
        f'<section class="block" id="{ns}assistant"><h2>PTk expert agent and skills</h2>'
        '<p class="lead">The <code>ptk-expert</code> agent knows this PTk version. It reads your '
        "configuration, picks the matching skill and uses the installed ptk commands, so its "
        "answers fit your project instead of generic examples.</p>"
        f'<p class="meta">{status}</p><h3>What it helps with</h3><ul class="notes">'
        + "".join(f"<li>{_e(t)}</li>" for t in ASSISTANT_TASKS)
        + "</ul><h3>Skills</h3>"
        + _table(["Skill", "Use it for"], rows)
        + "</section>"
    )
    nav = _group(
        "AI assistant",
        [_link(f"{ns}assistant", "Agent and skills")]
        + [_link(f"{ns}assistant", s.name, "ent-skill") for s in info.skills],
        opened=False,
    )
    return nav, body


def _page(
    title: str, brand: str, meta: str, nav: list[str], body: list[str], doc
) -> str:
    head = [
        f'<p class="brand">{_e(brand)}</p>',
        f'<p class="meta">{meta}</p>',
        '<input id="q" type="search" placeholder="Search" aria-label="Search the help">',
        '<p class="hint">Press <kbd>/</kbd> to search</p>',
        '<details open class="toc"><summary>Contents</summary>',
        '<a href="#top">Overview</a>',
    ]
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>'
        f'<style>{CSS}</style></head><body><div class="layout"><nav aria-label="Contents">'
        f"{''.join(head + nav)}</details></nav>"
        f"<main>{''.join(body)}<footer>Generated by ptk {_e(doc.version)} on {_e(doc.generated)}. "
        f"Run <code>ptk help</code> to refresh.</footer></main></div><script>{JS}</script>"
        f"{graph_html.assets()}</body></html>"
    )


def render(doc: HelpDocument) -> str:
    name = doc.project or "ptk"
    hero = [f'<header class="hero" id="top"><h1>{_e(name)}</h1>']
    hero.append(
        f'<p class="lead">{_e(doc.description)}</p>'
        if doc.description
        else '<p class="lead">Everything this project can do with ptk: jobs, workflows, their '
        "parameters and steps, variants and commands.</p>"
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
        ]
        hero.append(
            '<dl class="facts">'
            + "".join(f"<div><dt>{_e(k)}</dt><dd>{_e(v)}</dd></div>" for k, v in facts)
            + "</dl>"
        )
    hero.append(
        _cmd(
            _with_prefix(
                "ptk                               # run the default job\n", doc.prefix
            )
            + _with_prefix(
                "ptk JOB --dry-run                # see what would run\n", doc.prefix
            )
            + _with_prefix(
                "ptk JOB --NAME VALUE           # run it with a parameter\n", doc.prefix
            )
            + _with_prefix("ptk JOB --only-step STEP -- ARGS\n", doc.prefix)
            + _with_prefix("ptk variant list", doc.prefix)
        )
    )
    hidden = [
        f"{count} maintainer-only {kind}(s)"
        for count, kind in (
            (doc.hidden_jobs, "job"),
            (doc.hidden_workflows, "workflow"),
        )
        if count
    ]
    if hidden:
        hero.append(f'<p class="meta">{" and ".join(hidden)} are not listed.</p>')
    hero.append("</header>")
    nav, body = _project_parts(doc)
    assistant_nav, assistant_body = _assistant(doc.assistant)
    if assistant_nav:
        nav.append(assistant_nav)
        body.append(assistant_body)
    meta = (
        f"ptk {_e(doc.version)}, generated {_e(doc.generated)}"
        f"{', maintainer view' if doc.role == 'maintainer' else ''}"
    )
    return _page(f"{name} help", name, meta, nav, ["".join(hero), *body], doc)


def render_workspace(ws: HelpWorkspace) -> str:
    """One page for a VMR: VMR commands, workspace workflows and every repository."""
    hero = [
        '<header class="hero" id="top"><h1>VMR</h1>',
        (
            '<p class="lead">All PTk repositories of this workspace: their jobs, workflows, '
            "commands and configuration. Each repository applies its own maintainer list.</p>"
        ),
        f'<dl class="facts"><div><dt>Workspace folder</dt><dd>{_e(ws.root)}</dd></div></dl>',
        _table(
            ["Repository", "Project", "Folder"],
            [
                [
                    _link(f"repo-{_slug(r.alias)}", r.alias),
                    _e(r.project or "configuration error"),
                    _e(r.root),
                ]
                for r in ws.repositories
            ],
        ),
        _cmd(
            "ptk jobs                          # jobs of every repository\n"
            "ptk ALIAS JOB --dry-run          # see what a repository job would run\n"
            "ptk workflow list                 # workflows of every repository\n"
            "ptk --help                        # terminal help with the VMR commands"
        ),
        "</header>",
    ]
    nav: list[str] = []
    body: list[str] = ["".join(hero)]
    if ws.commands:
        body.append('<p class="group-head" id="g-vmr">VMR commands</p>')
        body.extend(_command(cmd, "vmr-") for cmd in ws.commands)
        nav.append(
            _group("VMR commands", _command_tree(ws.commands, "vmr-"), opened=False)
        )
    if ws.workflows:
        body.append('<p class="group-head" id="g-workflows">Workspace workflows</p>')
        links = []
        for wf in ws.workflows:
            cls = "ent-workflow" + (" maint" if wf.audience == "maintainer" else "")
            links.append(_link(_anchor("wf", wf.name), wf.name, cls))
            body.append(_workflow(wf))
        nav.append(_group("Workspace workflows", links, opened=True))
    assistant_nav, assistant_body = _assistant(ws.assistant)
    if assistant_nav:
        nav.append(assistant_nav)
        body.append(assistant_body)
    for repo in ws.repositories:
        ns = f"{_slug(repo.alias)}--"
        anchor = f"repo-{_slug(repo.alias)}"
        heading = (
            f'<h2 class="repo-head" id="{anchor}">{_e(repo.alias)}'
            f'<span class="meta"> {_e(repo.project or "")}</span></h2>'
        )
        if repo.error:
            heading += (
                f'<p class="problem">The configuration could not be loaded; run '
                f"<code>ptk {_e(repo.alias)} validate</code>.<br>{_e(repo.error)}</p>"
            )
        repo_nav, repo_body = _project_parts(repo, ns)
        body.append(f'<div class="repo">{heading}{"".join(repo_body)}</div>')
        nav.append(
            f'<details class="grp repo-grp"><summary>{_e(repo.alias)}</summary>'
            f"{_link(anchor, 'overview')}{''.join(repo_nav)}</details>"
        )
    meta = (
        f"ptk {_e(ws.version)}, generated {_e(ws.generated)}"
        f"{', maintainer view' if ws.role == 'maintainer' else ''}"
    )
    return _page("VMR help", "VMR", meta, nav, body, ws)


def write_help(doc: HelpDocument | HelpWorkspace, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    page = render_workspace(doc) if isinstance(doc, HelpWorkspace) else render(doc)
    target.write_text(page, encoding="utf-8")
    return target


def open_in_browser(path: Path) -> bool:
    """False when no browser is available (e.g. a Linux server without a desktop)."""
    try:
        return webbrowser.open(path.resolve().as_uri())
    except webbrowser.Error:
        return False
