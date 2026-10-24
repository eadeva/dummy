"""Semantic validation of a parsed configuration (pure).

Everything that can be checked without running anything is checked at load
time: references between sections, step conditions (``when:``) and
``${...}`` names. Problems are returned as (path, message); the application
layer maps paths to ``file:line``.
"""

from __future__ import annotations

import re
from typing import Any

from .. import expressions
from ..suggest import did_you_mean
from ..variants import rules as variant_rules
from ..variants.model import ProductLineSpec
from .model import ActionSpec, PtkConfig, StepSpec
from .substitution import iter_references, split_reference
from .tree import Path

PathProblem = tuple[Path, str]

WHEN_FLAT_NAMES = {"variant", "os", "ci"}
WHEN_NAMESPACES = {"params", "vars", "env", "vh"}
PROJECT_KEYS = {"name", "root", "description"}
RUN_KEYS = {"id", "action", "step", "build_dir", "bin_dir", "log_dir", "reports_dir"}
VH_KEYS = {"variant", "aliases", "components", "component_list", "features", "data"}


def parse_path(text: str) -> Path:
    """'variants.components.x.requires[0]' -> ('variants', 'components', 'x', 'requires', 0)."""
    parts: list[str | int] = []
    for segment in text.split("."):
        for name, index in re.findall(r"([^\[\]]+)|\[(\d+)\]", segment):
            parts.append(int(index) if index else name)
    return tuple(parts)


def validate(config: PtkConfig) -> list[PathProblem]:
    problems: list[PathProblem] = []
    line = config.variants

    if line is not None:
        problems += [(parse_path(p), m) for p, m in variant_rules.validate(line)]

    if (
        config.project.default_action
        and config.project.default_action not in config.actions
    ):
        problems.append(
            (
                ("project", "default_action"),
                (
                    f"unknown action '{config.project.default_action}'"
                    f"{did_you_mean(config.project.default_action, config.actions)}"
                ),
            )
        )

    default_action = config.actions.get(config.project.default_action or "")
    if default_action is not None and default_action.audience == "maintainer":
        problems.append(
            (
                ("project", "default_action"),
                (
                    "the default action must be available to everyone "
                    "(this one has audience: maintainer)"
                ),
            )
        )

    ruff = config.configs.get("ruff")
    if ruff is not None and ruff.overlay:
        problems.append(
            (
                ("configs", "ruff", "overlay"),
                "ruff needs no overlay: your ruff.toml extends ptk's ruff-base.toml",
            )
        )

    problems += _check_values(config.vars, ("vars",), config, None, allow_secret=False)

    for name, action in config.actions.items():
        base: Path = ("actions", name)
        for i, tool in enumerate(action.requires_tools):
            if tool not in config.tools:
                problems.append(
                    (
                        base + ("requires_tools", i),
                        f"unknown tool '{tool}'{did_you_mean(tool, config.tools)}",
                    )
                )
        problems += _check_values(
            action.env, base + ("env",), config, action, allow_secret=False
        )
        for pname, param in action.params.items():
            # defaults cannot depend on other parameters (action=None)
            problems += _check_values(
                param.default,
                base + ("params", pname, "default"),
                config,
                None,
                allow_secret=False,
            )
        for i, step in enumerate(action.steps):
            problems += _check_step(step, base + ("steps", i), config, action)
    return problems


def _check_step(
    step: StepSpec, path: Path, config: PtkConfig, action: ActionSpec
) -> list[PathProblem]:
    problems: list[PathProblem] = []
    if step.when:
        problems += _check_condition(step.when, path + ("when",), config, action)
    for key in ("run", "cwd", "uses"):
        problems += _check_values(
            getattr(step, key), path + (key,), config, action, allow_secret=False
        )
    problems += _check_values(
        step.with_, path + ("with",), config, action, allow_secret=False
    )
    problems += _check_values(
        step.env, path + ("env",), config, action, allow_secret=True
    )
    for env_name, ref in step.secrets.items():
        problems += _check_secret(ref, path + ("secrets", env_name), config)
    for i, child in enumerate(step.steps or []):
        problems += _check_step(child, path + ("steps", i), config, action)
    return problems


def _variant_symbols(line: ProductLineSpec | None) -> set[str]:
    return line.symbols if line is not None else set()


def _check_condition(
    expr: str, path: Path, config: PtkConfig, action: ActionSpec
) -> list[PathProblem]:
    try:
        used = expressions.names(expr)
    except expressions.ExpressionError as exc:
        return [(path, str(exc))]
    problems: list[PathProblem] = []
    flat_known = _variant_symbols(config.variants) | WHEN_FLAT_NAMES
    for name in sorted(used):
        head, _, rest = name.partition(".")
        if not rest:
            if name not in flat_known:
                problems.append(
                    (
                        path,
                        f"unknown name '{name}' in condition{did_you_mean(name, flat_known)}",
                    )
                )
            continue
        if head not in WHEN_NAMESPACES:
            problems.append(
                (
                    path,
                    f"unknown namespace '{head}' in condition{did_you_mean(head, WHEN_NAMESPACES)}",
                )
            )
            continue
        message = _check_dotted(head, rest, config, action)
        if message:
            problems.append((path, message))
    return problems


def _check_values(
    value: Any,
    path: Path,
    config: PtkConfig,
    action: ActionSpec | None,
    *,
    allow_secret: bool,
) -> list[PathProblem]:
    problems: list[PathProblem] = []
    for ref in iter_references(value):
        ns, rest = split_reference(ref)
        if ns == "secret":
            if not allow_secret:
                problems.append(
                    (
                        path,
                        (
                            f"${{secret:{rest}}} is only allowed in step 'env' "
                            "values or 'secrets' - never on command lines"
                        ),
                    )
                )
            else:
                problems += _check_secret(rest, path, config)
            continue
        if ns == "env":
            continue
        message = _check_dotted(ns, rest, config, action, in_substitution=True)
        if message:
            problems.append((path, message))
    return problems


def _check_dotted(
    ns: str,
    rest: str,
    config: PtkConfig,
    action: ActionSpec | None,
    *,
    in_substitution: bool = False,
) -> str | None:
    first, _, deeper = rest.partition(".")
    ref = f"{ns}.{rest}"
    if ns == "vars":
        if first not in config.vars:
            return f"unknown variable '{ref}'{did_you_mean(first, config.vars)}"
    elif ns == "params":
        params = action.params if action else {}
        if action is None:
            return f"'{ref}' can only be used inside an action"
        if first not in params:
            return f"unknown parameter '{ref}'{did_you_mean(first, params)}"
    elif ns == "vh":
        if config.variants is None:
            return f"'{ref}' needs a 'variants' section"
        if first not in VH_KEYS:
            return f"unknown name '{ref}'{did_you_mean(first, VH_KEYS)}"
        name = deeper.split(".")[0] if deeper else ""
        if first == "features" and name and name not in config.variants.feature_index:
            return f"unknown feature '{ref}'{did_you_mean(name, config.variants.feature_index)}"
        if first == "components" and name and name not in config.variants.components:
            return f"unknown component '{ref}'{did_you_mean(name, config.variants.components)}"
    elif ns == "env":
        return None
    elif in_substitution and ns == "project":
        if first not in PROJECT_KEYS:
            return f"unknown name '{ref}'{did_you_mean(first, PROJECT_KEYS)}"
    elif in_substitution and ns == "run":
        if first not in RUN_KEYS:
            return f"unknown name '{ref}'{did_you_mean(first, RUN_KEYS)}"
    else:
        known = ["env", "vars", "params", "vh", "project", "run", "secret"]
        return f"unknown namespace '{ns}'{did_you_mean(ns, known)}"
    return None


def _check_secret(ref: str, path: Path, config: PtkConfig) -> list[PathProblem]:
    name, _, field = ref.partition(".")
    cred = config.credentials.get(name)
    if cred is None:
        return [
            (
                path,
                f"unknown credential '{name}'{did_you_mean(name, config.credentials)}",
            )
        ]
    if not field:
        return [
            (
                path,
                f"secret reference '{ref}' needs a field: {name}.<{'|'.join(cred.fields)}>",
            )
        ]
    if field not in cred.fields:
        return [
            (
                path,
                f"credential '{name}' has no field '{field}'{did_you_mean(field, cred.fields)}",
            )
        ]
    return []
