"""Find unknown keys in a located tree, with suggestions (pure).

pydantic would also reject unknown keys, but walking the located tree gives
the exact line of the misspelled key and a "did you mean" hint.
"""

from __future__ import annotations

import inspect
import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from ..errors import Problem
from ..suggest import did_you_mean
from .tree import Node, Path, format_path

_STEP_MODEL = "StepSpec"


def _named(path: Path) -> Path:
    """Drop the list index in front of a step name: steps[1].compile -> steps.compile."""
    result: list[str | int] = []
    for i, part in enumerate(path):
        if (
            isinstance(part, int)
            and i + 1 < len(path)
            and isinstance(path[i + 1], str)
            and i > 0
            and path[i - 1] == "steps"
        ):
            continue
        result.append(part)
    return tuple(result)


def _allowed_keys(model: type[BaseModel]) -> dict[str, str]:
    keys: dict[str, str] = {}
    for name, field in model.model_fields.items():
        keys[field.alias or name] = name
        keys[name] = name
    return keys


def _is_model(tp: Any) -> bool:
    return inspect.isclass(tp) and issubclass(tp, BaseModel)


def _literal_keys(annotation: Any) -> set[str] | None:
    """The allowed keys of ``dict[Literal[...], X]`` (None for other dicts)."""
    args = get_args(annotation)
    if args and get_origin(args[0]) is Literal:
        return {str(v) for v in get_args(args[0])}
    return None


def unknown_keys(model: type[BaseModel], node: Node) -> list[Problem]:
    problems: list[Problem] = []
    _walk(model, node, (), problems)
    return problems


def _walk(
    annotation: Any, node: Node | None, path: Path, problems: list[Problem]
) -> None:
    if node is None or annotation is Any:
        return
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        options = [a for a in get_args(annotation) if a is not type(None)]
        if node.is_map:
            models = [a for a in options if _is_model(a)]
            dicts = [a for a in options if get_origin(a) is dict]
            keyed = [d for d in dicts if _literal_keys(d) is not None]
            for candidate in keyed:  # e.g. {windows: ..., linux: ...}
                keys = _literal_keys(candidate) or set()
                if node.value and set(node.value) <= keys:
                    _walk(candidate, node, path, problems)
                    return
            if len(models) == 1:
                _walk(models[0], node, path, problems)
            elif not models and dicts:
                _walk(dicts[0], node, path, problems)
        elif node.is_list:
            lists = [a for a in options if get_origin(a) is list]
            if lists:
                _walk(lists[0], node, path, problems)
        return
    if _is_model(annotation):
        if not node.is_map:
            return
        allowed = _allowed_keys(annotation)
        if (
            annotation.__name__ in {_STEP_MODEL, "WorkflowNode"}
            and (annotation.__name__ == "WorkflowNode" or "name" not in node.value)
            and len(node.value) == 1
        ):
            ((step_name, body),) = node.value.items()
            if not body.is_map:
                return  # short form: "- name: <command>"
            node, path = body, path + (step_name,)
        for key, child in node.value.items():
            if key not in allowed:
                visible = [k for k in allowed if k != "with_"]
                problems.append(
                    Problem(
                        f"unknown key '{key}'{did_you_mean(key, visible)}",
                        path=format_path(_named(path + (key,))),
                        location=node.key_locs.get(key) or child.loc,
                    )
                )
                continue
            field = annotation.model_fields[allowed[key]]
            _walk(field.annotation, child, path + (key,), problems)
        return
    if origin is dict and node.is_map:
        value_type = get_args(annotation)[1]
        for key, child in node.value.items():
            _walk(value_type, child, path + (key,), problems)
    elif origin is list and node.is_list:
        item_type = get_args(annotation)[0]
        for i, child in enumerate(node.value):
            _walk(item_type, child, path + (i,), problems)
