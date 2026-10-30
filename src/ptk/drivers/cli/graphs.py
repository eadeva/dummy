"""Present the configured graph without preparing commands or resolving secrets."""

from rich.markup import escape
from rich.table import Table

from ...adapters.graph_html import render
from ...domain.graphs import ancestors, describe_graph
from ...domain.layout import safe
from .state import console


def show_graph(root, name, kind, nodes, *, selected=None, variant=None, only_step=None):
    graph = describe_graph(nodes)
    for node in graph["nodes"]:
        if kind == "workflow":
            node["label"] = nodes[node["id"]].job
        if selected is not None:
            node["selected"] = node["id"] in selected
    title = f"{kind.title()} {name}: dependency graph" + (
        f" · {variant}" if variant else ""
    )
    console.print(f"[bold]{escape(title)}[/]", highlight=False, soft_wrap=True)
    if only_step:
        omitted = ", ".join(sorted(ancestors(nodes)[only_step])) or "none"
        graph["notice"] = (
            f"Only step {only_step}; prerequisites not run: {omitted}. Required outputs must already exist. The diagram retains all configured dependency edges."
        )
        console.print(
            escape(graph["notice"]), style="yellow", highlight=False, soft_wrap=True
        )
    table = Table()
    for column in ("ID", "Needs", "Selection"):
        table.add_column(column)
    for node in graph["nodes"]:
        table.add_row(
            node["id"],
            ", ".join(node["needs"]) or "ready",
            "selected" if node.get("selected", True) else "not selected",
        )
    console.print(table)
    suffix = f"-{safe(variant)}" if variant else ""
    target = root / ".ptk" / "graphs" / f"{kind}-{name.replace('/', '-')}{suffix}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(graph, title), encoding="utf-8")
    console.print(f"graph: {escape(str(target))}", highlight=False, soft_wrap=True)
    return target
