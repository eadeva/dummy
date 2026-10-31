"""Shared offline dependency viewer for previews and recorded run reports."""

import json
from functools import cache
from html import escape
from importlib.resources import files


@cache
def assets():
    root = files("ptk.adapters").joinpath("graph_assets")
    css = root.joinpath("graph.css").read_text(encoding="utf-8")
    license_text = root.joinpath("dagre.min.js.LEGAL.txt").read_text(encoding="utf-8")
    engine = root.joinpath("dagre.min.js").read_text(encoding="utf-8")
    viewer = root.joinpath("graph.js").read_text(encoding="utf-8")
    return f"<style>{css}</style><script>{license_text}\n{engine}\n{viewer}</script>"


def section(graph, title, *, collapsed=True):
    """A native, keyboard-accessible disclosure; initialize layout when opened."""
    data = (
        json.dumps(graph, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    count = len(graph["nodes"])
    edges = sum(len(node["needs"]) for node in graph["nodes"])
    expandable = any(node.get("children", {}).get("nodes") for node in graph["nodes"])
    expansion = (
        (
            '<button type="button" data-graph-action="expand">Expand all jobs</button>'
            '<button type="button" data-graph-action="collapse">Collapse all jobs</button>'
        )
        if expandable
        else ""
    )
    hierarchy = (
        " Expand a job to inspect its recorded steps. Job dependencies connect whole jobs; internal arrows connect steps only."
        if expandable
        else ""
    )
    notice = (
        f'<p class="ptk-graph-notice">{escape(graph["notice"])}</p>'
        if graph.get("notice")
        else ""
    )
    caption = escape(
        graph.get(
            "caption",
            "Execution flows top to bottom: prerequisites → dependents. Joins wait for all prerequisites; branches can overlap. Shared nodes appear once.",
        )
    )
    return f"""<details class="ptk-graph"{" open" if not collapsed else ""}>
<summary><strong>Dependency graph</strong><span>{count} nodes · {edges} dependencies</span></summary>
<div class="ptk-graph-body">
<p class="ptk-graph-caption">{caption}{hierarchy}</p>{notice}
<div class="ptk-graph-toolbar" role="group" aria-label="Graph controls">
<button type="button" data-graph-action="in" aria-label="Zoom in">+</button>
<button type="button" data-graph-action="out" aria-label="Zoom out">−</button>
<button type="button" data-graph-action="fit">Fit to view</button>
{expansion}
<output aria-label="Graph zoom"></output><span>Drag to pan · select a node for details</span></div>
<div class="ptk-graph-viewport" tabindex="0" role="region" aria-label="{escape(title, quote=True)}">
<svg xmlns="http://www.w3.org/2000/svg" role="group" aria-label="Dependency diagram"></svg></div>
<div class="ptk-graph-inspector" aria-live="polite"><p>Select a node to inspect its dependencies and results.</p></div>
<script type="application/json" class="ptk-graph-data">{data}</script>
</div></details>"""


def render(graph, title):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;color:#18212f;background:#f3f5f8;margin:0;padding:24px}}main{{max-width:1180px;margin:auto}}h1{{font-size:26px}}@media(prefers-color-scheme:dark){{body{{color:#e6ebf2;background:#0f141b}}}}@media(max-width:500px){{body{{padding:12px}}}}</style></head>
<body><main><h1>{escape(title)}</h1>{section(graph, title, collapsed=False)}
<p>Configured dependencies, not a timeline. A step becomes ready after all prerequisites pass or their failures are explicitly allowed. Independent steps can overlap. Runtime conditions can skip steps and block their dependents.</p>
</main>{assets()}</body></html>"""
