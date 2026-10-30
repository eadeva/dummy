"""Pure dependency validation, selection and graph metadata."""

import re
from graphlib import CycleError, TopologicalSorter
from typing import Annotated

from pydantic import StringConstraints

IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
DependencyId = Annotated[str, StringConstraints(pattern=IDENTIFIER)]


def validate_graph(nodes, label):
    folders = {}
    for name, node in nodes.items():
        folder = name.rstrip(".").casefold()
        if folder in folders:
            raise ValueError(
                f"{label} IDs {folders[folder]!r} and {name!r} share an output folder on supported platforms"
            )
        folders[folder] = name
        if not re.fullmatch(IDENTIFIER, name):
            raise ValueError(f"invalid {label} ID {name!r}")
        if len(node.needs) != len(set(node.needs)):
            raise ValueError(f"{label} {name!r}: needs must not repeat an ID")
        for dependency in node.needs:
            if dependency == name:
                raise ValueError(f"{label} {name!r} cannot need itself")
            if dependency not in nodes:
                raise ValueError(
                    f"{label} {name!r} needs unknown invocation {dependency!r}"
                )
    try:
        tuple(
            TopologicalSorter(
                {name: node.needs for name, node in nodes.items()}
            ).static_order()
        )
    except CycleError as exc:
        raise ValueError(
            f"{label} dependency cycle: " + " -> ".join(exc.args[1])
        ) from None


def ancestors(nodes):
    result = {}
    for name in TopologicalSorter(
        {name: node.needs for name, node in nodes.items()}
    ).static_order():
        result[name] = set(nodes[name].needs)
        for dependency in nodes[name].needs:
            result[name].update(result[dependency])
    return result


def describe_graph(nodes):
    """One node per ID and a target-first tree projection, in authored order.

    Tree entries refer to an earlier parent index; repeated dependencies are
    leaves referencing their first occurrence. This keeps joins and disconnected
    targets without expanding exponentially or requiring recursive traversal.
    """
    dependencies = {need for node in nodes.values() for need in node.needs}
    pending = [(name, None) for name in reversed(nodes) if name not in dependencies]
    tree = []
    seen = set()
    while pending:
        name, parent = pending.pop()
        shared = name in seen
        index = len(tree)
        tree.append({"id": name, "parent": parent, "shared": shared})
        if not shared:
            seen.add(name)
            pending.extend((need, index) for need in reversed(nodes[name].needs))
    return {
        "nodes": [
            {"id": name, "needs": list(node.needs)}
            | ({"label": node.job} if hasattr(node, "job") else {})
            for name, node in nodes.items()
        ],
        "tree": tree,
    }
