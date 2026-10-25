"""Apply shared action defaults while preserving their original source locations."""

from . import tree as t


def requirements(node: t.Node | None) -> t.Node | None:
    if node is not None and node.is_list:
        if not all(isinstance(item.value, str) for item in node.value):
            return node
        return t.Node(
            {item.value: t.Node(True, item.loc) for item in node.value}, node.loc
        )
    return node


def normalize_requirements(tree: t.Node) -> t.Node:
    """Normalize list shorthand before layer merges, so requirements merge per name."""
    result = tree
    paths = [("requires_tools",)]
    actions = t.get(tree, ("actions",))
    if actions is not None and actions.is_map:
        paths += [("actions", name, "requires_tools") for name in actions.value]
    for path in paths:
        node = t.get(tree, path)
        normalized = requirements(node)
        if normalized is not None and normalized is not node:
            result = t.merge(result, t.overlay_for(path, normalized))
    return result


def apply_defaults(tree: t.Node) -> t.Node:
    tree = normalize_requirements(tree)
    actions = t.get(tree, ("actions",))
    if actions is None or not actions.is_map:
        return tree
    tools = t.get(tree, ("requires_tools",))
    defaults = t.get(tree, ("param_defaults",))
    result = tree
    for name, action in actions.value.items():
        if not action.is_map:
            continue
        own_tools = action.value.get("requires_tools")
        if (
            tools is not None
            and tools.is_map
            and own_tools is not None
            and own_tools.is_map
        ):
            # True enables a tool without resetting its inherited settings.
            own_tools = t.Node(
                {
                    key: tools.value[key]
                    if value.value is True
                    and key in tools.value
                    and tools.value[key].is_map
                    else value
                    for key, value in own_tools.value.items()
                },
                own_tools.loc,
            )
        effective = t.merge(tools, own_tools) if own_tools is not None else tools
        if effective is not None:
            result = t.merge(
                result,
                t.overlay_for(
                    ("actions", name, "requires_tools"),
                    t.Node(effective.value, effective.loc, op="replace"),
                ),
            )
        params = action.value.get("params")
        if (
            params is None
            or not params.is_map
            or defaults is None
            or not defaults.is_map
        ):
            continue
        for param, spec in params.value.items():
            if not spec.is_map or "default" in spec.value:
                continue
            required = spec.value.get("required")
            if required is not None and required.value is True:
                continue
            if param in defaults.value:
                result = t.merge(
                    result,
                    t.overlay_for(
                        ("actions", name, "params", param, "default"),
                        defaults.value[param],
                    ),
                )
    return result
