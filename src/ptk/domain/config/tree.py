"""Located configuration tree and merge rules (pure, no I/O).

Every value of a loaded configuration is a ``Node`` that remembers where it
came from. Merging layers keeps those locations, so any final value can be
traced to ``file:line`` (``ptk config show --sources``) and validation errors
point to the right place.

Merge rules
-----------
* mapping + mapping  -> merged key by key (deep)
* anything else      -> the overlay replaces the base (lists are replaced)
* ``!replace``       -> the overlay replaces the base even for mappings
* ``!append``        -> the overlay list is appended to the base list
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..errors import Location

Op = Literal["replace", "append"] | None
Path = tuple[str | int, ...]


@dataclass
class Node:
    value: Any  # dict[str, Node] | list[Node] | scalar
    loc: Location | None = None
    op: Op = None
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


def merge(base: Node | None, overlay: Node) -> Node:
    if base is None or overlay.op == "replace":
        return _strip_ops(overlay)
    if overlay.op == "append":
        if base.is_list and overlay.is_list:
            return Node(
                base.value + [_strip_ops(n) for n in overlay.value], overlay.loc
            )
        return _strip_ops(overlay)
    if base.is_map and overlay.is_map:
        merged = dict(base.value)
        key_locs = dict(base.key_locs)
        for key, child in overlay.value.items():
            merged[key] = merge(base.value.get(key), child)
            if key in overlay.key_locs:
                key_locs[key] = overlay.key_locs[key]
        return Node(merged, overlay.loc or base.loc, key_locs=key_locs)
    return _strip_ops(overlay)


def _strip_ops(node: Node) -> Node:
    if node.is_map:
        return Node(
            {k: _strip_ops(v) for k, v in node.value.items()},
            node.loc,
            key_locs=node.key_locs,
        )
    if node.is_list:
        return Node([_strip_ops(v) for v in node.value], node.loc)
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
    """``actions.build.steps.0.run`` -> ('actions', 'build', 'steps', 0, 'run')."""
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


def display_path(root: Node, path: Path) -> str:
    """Readable path: list items written as ``- name: {...}`` show their name
    (``steps.checks.steps.lint.run`` instead of ``steps[2].steps[0].run``)."""
    parts: list[str | int] = []
    current: Node | None = root
    for part in path:
        nxt = get(current, (part,)) if current is not None else None
        if (
            nxt is None
            and current is not None
            and current.is_map
            and len(current.value) == 1
        ):
            only = next(iter(current.value))
            if get(current.value[only], (part,)) is not None:
                current = current.value[only]
                nxt = get(current, (part,))
        if (
            isinstance(part, int)
            and nxt is not None
            and nxt.is_map
            and len(nxt.value) == 1
            and "name" not in nxt.value
        ):
            parts.append(next(iter(nxt.value)))
        elif (
            isinstance(part, str)
            and parts
            and parts[-1] == part
            and current is not None
            and not current.is_map
        ):
            continue
        else:
            parts.append(part)
        current = nxt
    return format_path(tuple(parts))


def locate(root: Node, path: Path) -> Location | None:
    """Best location for a validation error at ``path``.

    Steps are written as ``- name: {...}`` but validated as ``{name: ..., ...}``,
    so a path like ``steps[0].run`` is searched as ``steps[0].<name>.run`` too.
    Falls back to the closest parent that has a location.
    """
    current = root
    best = root.loc
    for part in path:
        nxt = get(current, (part,))
        if nxt is None and current.is_map and len(current.value) == 1:
            only_key = next(iter(current.value))
            wrapper = current.value[only_key]
            nxt = get(wrapper, (part,))
            if nxt is not None:
                current = wrapper
        if nxt is None:
            if isinstance(part, str) and current.is_map and part in current.key_locs:
                return current.key_locs[part]
            return best
        if isinstance(part, str) and current.is_map and part in current.key_locs:
            best = current.key_locs[part]
        current = nxt
        best = current.loc or best
    return best
