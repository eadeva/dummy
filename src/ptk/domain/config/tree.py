"""Located configuration tree and merge rules (pure, no I/O).

Every value of a loaded configuration is a ``Node`` that remembers where it
came from. Combining fields keeps those locations, so any final value can be
traced to ``file:line`` (``ptk maintainer config show --sources``) and validation errors
point to the right place.

File composition uses merge_unique: mappings combine disjoint keys and any
repeated scalar or list is an error. Model defaults and explicit CLI overrides
use merge: mappings combine deeply and other values replace the base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..errors import ConfigError, Location, Problem

Path = tuple[str | int, ...]


@dataclass
class Node:
    value: Any  # dict[str, Node] | list[Node] | scalar
    loc: Location | None = None
    key_locs: dict[str, Location] = field(
        default_factory=dict
    )  # locations of mapping keys

    @property
    def is_map(self) -> bool:
        return isinstance(self.value, dict)

    @property
    def is_list(self) -> bool:
        return isinstance(self.value, list)


def from_plain(value: Any, loc: Location | None = None) -> Node:
    """Wrap plain Python data (e.g. from ``--set``) into nodes with one location."""
    if isinstance(value, dict):
        return Node(
            {str(k): from_plain(v, loc) for k, v in value.items()},
            loc,
            key_locs={str(k): loc for k in value} if loc else {},
        )
    if isinstance(value, list):
        return Node([from_plain(v, loc) for v in value], loc)
    return Node(value, loc)


def merge(base: Node | None, overlay: Node, _path: Path = ()) -> Node:
    if base is None:
        return _copy_node(overlay)
    requirement = (len(_path) == 2 and _path[0] == "requires_tools") or (
        len(_path) == 4 and _path[0] == "jobs" and _path[2] == "requires_tools"
    )
    if base.is_map and overlay.value is True and requirement:
        return _copy_node(base)
    if base.is_map and overlay.is_map:
        merged = dict(base.value)
        key_locs = dict(base.key_locs)
        for key, child in overlay.value.items():
            merged[key] = merge(base.value.get(key), child, (*_path, key))
            if key in overlay.key_locs:
                key_locs[key] = overlay.key_locs[key]
        return Node(merged, overlay.loc or base.loc, key_locs=key_locs)
    return _copy_node(overlay)


def merge_unique(base: Node, incoming: Node, path: Path = ()) -> Node:
    """Combine authored files without precedence, retaining every source location.

    Maps may contribute disjoint fields. Lists and scalar values have one owner,
    even when two definitions are identical. Explicit runtime overrides continue
    to use merge(), separately from file composition.
    """
    if base.is_map and incoming.is_map:
        values = dict(base.value)
        locations = dict(base.key_locs)
        for key, value in incoming.value.items():
            values[key] = (
                merge_unique(values[key], value, (*path, key))
                if key in values
                else value
            )
            if key not in locations and key in incoming.key_locs:
                locations[key] = incoming.key_locs[key]
        return Node(values, base.loc or incoming.loc, key_locs=locations)
    raise ConfigError(
        [
            Problem(
                f"configuration conflict: already defined at {base.loc}; overwriting is not allowed",
                format_path(path),
                incoming.loc,
            )
        ]
    )


def _copy_node(node: Node) -> Node:
    if node.is_map:
        return Node(
            {k: _copy_node(v) for k, v in node.value.items()},
            node.loc,
            key_locs=node.key_locs,
        )
    if node.is_list:
        return Node([_copy_node(v) for v in node.value], node.loc)
    return Node(node.value, node.loc)


def to_plain(node: Node) -> Any:
    if node.is_map:
        return {k: to_plain(v) for k, v in node.value.items()}
    if node.is_list:
        return [to_plain(v) for v in node.value]
    return node.value


def provenance(node: Node, path: Path = ()) -> dict[Path, Location]:
    """Location of every value (and mapping key) by path."""
    result: dict[Path, Location] = {}
    if node.loc:
        result[path] = node.loc
    if node.is_map:
        for key, child in node.value.items():
            if key in node.key_locs:
                result[path + (key,)] = node.key_locs[key]
            result.update(provenance(child, path + (key,)))
    elif node.is_list:
        for i, child in enumerate(node.value):
            result.update(provenance(child, path + (i,)))
    return result


def get(node: Node, path: Path) -> Node | None:
    current: Node | None = node
    for part in path:
        if current is None:
            return None
        if isinstance(part, int) and current.is_list and 0 <= part < len(current.value):
            current = current.value[part]
        elif isinstance(part, str) and current.is_map:
            current = current.value.get(part)
        else:
            return None
    return current


def parse_dotted(dotted: str) -> Path:
    """``jobs.build.steps.compile.run`` -> ('jobs', 'build', 'steps', 'compile', 'run')."""
    parts: list[str | int] = []
    for part in dotted.split("."):
        if not part:
            raise ValueError(f"invalid path {dotted!r}")
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def overlay_for(path: Path, value: Node) -> Node:
    """Build a sparse overlay tree that sets ``value`` at ``path``."""
    if any(isinstance(part, int) for part in path):
        raise ValueError(
            "list indices cannot be set with --set; set the whole list instead"
        )
    node = value
    for part in reversed(path):
        node = Node(
            {part: node}, value.loc, key_locs={part: value.loc} if value.loc else {}
        )
    return node


def format_path(path: Path) -> str:
    text = ""
    for part in path:
        text += (
            f"[{part}]"
            if isinstance(part, int)
            else (f".{part}" if text else str(part))
        )
    return text


def locate(root: Node, path: Path) -> Location | None:
    """Locate a field, using its nearest existing parent for missing fields."""
    current = root
    best = root.loc
    for part in path:
        nxt = get(current, (part,))
        if nxt is None:
            if isinstance(part, str) and current.is_map and part in current.key_locs:
                return current.key_locs[part]
            return best
        if isinstance(part, str) and current.is_map and part in current.key_locs:
            best = current.key_locs[part]
        current = nxt
        best = current.loc or best
    return best
