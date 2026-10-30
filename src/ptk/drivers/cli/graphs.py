"""Present the configured graph without preparing commands or resolving secrets."""

from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ...adapters.graph_html import render
from ...domain.graphs import ancestors, describe_graph
from ...domain.layout import safe
from .state import console


def show_graph(
    root,
    name,
    kind,
    nodes,
    *,
    selected=None,
    variant=None,
    only_step=None,
    skipped=None,
):
    graph = describe_graph(nodes)
    for node in graph["nodes"]:
        if selected is not None:
            node["selected"] = node["id"] in selected
        if skipped and node["id"] in skipped:
            node["status"] = "skipped"
            node["message"] = skipped[node["id"]]
    title = f"{kind.title()} {name}: dependency graph" + (
        f" · {variant}" if variant else ""
    )
    color = "magenta" if kind == "workflow" else "cyan"
    console.print(f"[bold {color}]{escape(title)}[/]", highlight=False, soft_wrap=True)
    if only_step:
        omitted = ", ".join(sorted(ancestors(nodes)[only_step])) or "none"
        graph["notice"] = (
            f"Only step {only_step}; prerequisites not run: {omitted}. Required outputs must already exist. The diagram retains all configured dependency edges."
        )
        console.print(
            escape(graph["notice"]), style="yellow", highlight=False, soft_wrap=True
        )
    tree = Tree(Text(f"{name} · prerequisites → dependents", style="bold"))
    metadata = {node["id"]: node for node in graph["nodes"]}
    branches = []
    for entry in graph["tree"]:
        node = metadata[entry["id"]]
        label = Text(
            node["id"], style="bold cyan" if kind == "workflow" else "bold blue"
        )
        if node.get("label") and node["label"] != node["id"]:
            label.append(f"  {node['label']}", style="dim")
        if node.get("message"):
            label.append(f"  skipped: {node['message']}", style="dim")
        elif not node.get("selected", True):
            label.append("  not selected", style="dim")
        elif selected is not None:
            label.append("  selected", style="green")
        if len(node["needs"]) > 1:
            label.append(f"  needs all: {', '.join(node['needs'])}", style="dim")
        if entry["shared"]:
            label.append("  ↩ shared — shown above", style="dim italic")
        parent = tree if entry["parent"] is None else branches[entry["parent"]]
        branches.append(parent.add(label))
    if not graph["nodes"]:
        tree.add(Text("No steps configured", style="dim"))
    console.print(tree)
    if any(len(node["needs"]) > 1 for node in graph["nodes"]):
        console.print(
            "Joins wait for all prerequisites; branches can overlap.", style="dim"
        )
    suffix = f"-{safe(variant)}" if variant else ""
    target = root / ".ptk" / "graphs" / f"{kind}-{name.replace('/', '-')}{suffix}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(graph, title), encoding="utf-8")
    console.print(f"graph: {escape(str(target))}", highlight=False, soft_wrap=True)
    return target
