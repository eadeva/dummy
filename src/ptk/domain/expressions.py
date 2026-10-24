"""Safe expression language used for conditions everywhere in ptk.

Used by: variant rules (``depends_on``, ``requires``, ``conflicts``,
constraints) and step conditions (``when:``). A subset of Python syntax::

    COMPONENT_CAMERA and DISPLAY_SIZE >= 10
    MAP_REGION in ["US", "CA"] and not TOUCH
    variant == "customer_b_us" or os == "windows"
    params.dry_run and vars.channel != "release"

* names evaluate to their value; ``None`` means unset / switched off
* dotted names (``params.x``) read from namespaces (nested mappings)
* a bare value is *truthy* unless it is ``False`` or ``None``
  (``0`` and ``""`` are valid settings, not "off")
* no calls, arithmetic, subscripts, lambdas ... - parsed with ``ast`` against
  a whitelist; nothing is ever executed
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

_ALLOWED = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Name,
    ast.Attribute,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
)


class ExpressionError(ValueError):
    """Syntactically invalid or unsupported expression."""


def is_truthy(value: Any) -> bool:
    return value is not None and value is not False


@lru_cache(maxsize=4096)
def parse(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(str(expr).strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"invalid expression {expr!r}: {exc.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ExpressionError(
                f"unsupported syntax '{type(node).__name__}' in {expr!r}"
            )
        if isinstance(node, ast.Attribute) and not isinstance(
            node.value, (ast.Name, ast.Attribute)
        ):
            raise ExpressionError(
                f"attribute access is only allowed on names in {expr!r}"
            )
        if isinstance(node, ast.Constant) and not isinstance(
            node.value, (bool, int, float, str, type(None))
        ):
            raise ExpressionError(f"unsupported constant {node.value!r} in {expr!r}")
    return tree


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    assert isinstance(node, ast.Attribute)
    return f"{_dotted(node.value)}.{node.attr}"


def names(expr: str) -> set[str]:
    """All referenced names; dotted names are returned whole (``params.jobs``)."""
    found: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.Name, ast.Attribute)):
            found.add(_dotted(node))
            return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(parse(expr).body)
    return found


def lookup(symbols: Mapping[str, Any], dotted: str) -> Any:
    """Resolve ``a.b.c`` against nested mappings; missing parts give None."""
    head, *rest = dotted.split(".")
    value: Any = symbols.get(head)
    for part in rest:
        value = value.get(part) if isinstance(value, Mapping) else None
    return value


def evaluate(expr: str, symbols: Mapping[str, Any]) -> bool:
    return is_truthy(_eval(parse(expr).body, symbols))


_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _eval(node: ast.AST, symbols: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Name, ast.Attribute)):
        return lookup(symbols, _dotted(node))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, symbols) for e in node.elts]
    if isinstance(node, ast.UnaryOp):  # only Not is allowed
        return not is_truthy(_eval(node.operand, symbols))
    if isinstance(node, ast.BoolOp):
        values = (is_truthy(_eval(v, symbols)) for v in node.values)
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, symbols)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval(comparator, symbols)
            try:
                if not _COMPARE[type(op)](left, right):
                    return False
            except TypeError:  # e.g. None < 5: unset never satisfies an ordering
                return False
            left = right
        return True
    raise ExpressionError(f"unsupported node {type(node).__name__}")  # pragma: no cover
