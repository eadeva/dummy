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
    """One node per ID; joins retain every incoming edge."""
    depths = {}
    for name in TopologicalSorter(
        {name: node.needs for name, node in nodes.items()}
    ).static_order():
        depths[name] = max(
            (depths[parent] + 1 for parent in nodes[name].needs), default=0
        )
    return {
        "nodes": [
            {"id": name, "needs": list(node.needs), "depth": depths[name]}
            for name, node in nodes.items()
        ]
    }
