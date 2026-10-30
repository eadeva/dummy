"""Offline SVG dependency diagrams. Graph data is supplied by the domain."""

from html import escape
from math import ceil


def diagram(graph, title):
    nodes = graph["nodes"]
    levels = {}
    for node in nodes:
        levels.setdefault(node["depth"], []).append(node)
    columns = min(4, max((len(level) for level in levels.values()), default=1))
    width = columns * 250 + 40
    positions = {}
    y = 35
    for depth in sorted(levels):
        for index, node in enumerate(levels[depth]):
            row_start = index // columns * columns
            row_size = min(columns, len(levels[depth]) - row_start)
            positions[node["id"]] = (
                (width - (row_size * 250 - 40)) / 2 + index % columns * 250,
                y + index // columns * 110,
            )
        y += ceil(len(levels[depth]) / columns) * 110 + 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {y}" style="max-width:{width}px;margin:0 auto" role="img" aria-labelledby="graph-title"><title id="graph-title">{escape(title)}</title>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8z" fill="#6c7b91"/></marker></defs>',
    ]
    for node in nodes:
        x, bottom = positions[node["id"]]
        for parent in node["needs"]:
            px, top = positions[parent]
            middle = (top + 64 + bottom) / 2
            parts.append(
                f'<path d="M{px + 105} {top + 64} C{px + 105} {middle}, {x + 105} {middle}, {x + 105} {bottom - 7}" fill="none" stroke="#6c7b91" stroke-width="2" marker-end="url(#arrow)"/>'
            )
    for node in nodes:
        x, top = positions[node["id"]]
        selected = node.get("selected", True)
        fill, stroke = ("#e8f2ff", "#2767b1") if selected else ("#f1f3f5", "#8693a5")
        name = node["id"]
        label = name if len(name) <= 25 else name[:22] + "…"
        detail = node.get("label") or (
            "Needs " + ", ".join(node["needs"]) if node["needs"] else "Ready"
        )
        text = detail if len(detail) <= 29 else detail[:26] + "…"
        parts.append(
            f'<g><title>{escape(name + ": " + detail)}</title><rect x="{x}" y="{top}" width="210" height="64" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/><text x="{x + 12}" y="{top + 26}" fill="#183553" font-family="system-ui,sans-serif" font-size="14" font-weight="600">{escape(label)}</text><text x="{x + 12}" y="{top + 48}" fill="#425671" font-family="system-ui,sans-serif" font-size="12">{escape(text)}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render(graph, title):
    has_target = any(node.get("label") for node in graph["nodes"])
    target_header = "<th>Target</th>" if has_target else ""
    rows = "".join(
        f"<tr><td>{escape(n['id'])}</td><td>{escape(', '.join(n['needs']) or 'Ready')}</td>"
        + (f"<td>{escape(n.get('label', ''))}</td>" if has_target else "")
        + f"<td>{'Selected' if n.get('selected', True) else 'Not selected'}</td></tr>"
        for n in graph["nodes"]
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;color:#183553;background:#f6f8fc;margin:0;padding:24px}}main{{max-width:1100px;margin:auto}}h1{{font-size:26px}}.diagram{{background:white;border:1px solid #d5deea;border-radius:12px;padding:16px;overflow:auto}}svg{{display:block;width:100%;min-width:280px}}table{{border-collapse:collapse;width:100%;margin-top:24px;background:white}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #d5deea;overflow-wrap:anywhere}}th{{background:#e8f2ff}}@media(max-width:500px){{body{{padding:12px}}td,th{{padding:6px;font-size:12px}}}}</style>
<main><h1>{escape(title)}</h1><p>{escape(graph.get("notice", ""))}</p><p>Arrows point from prerequisites to dependents. A node becomes ready when all its prerequisites pass (or their failures are explicitly allowed). Independent nodes may overlap, up to the configured worker limit. Levels describe dependencies, not execution barriers.</p><div class="diagram">{diagram(graph, title)}</div><table><thead><tr><th>ID</th><th>Needs</th>{target_header}<th>Selection</th></tr></thead><tbody>{rows}</tbody></table><p>This is the configured graph. Runtime conditions can skip nodes; skipped prerequisites block their dependents. Graph inspection does not execute commands.</p></main></html>"""
