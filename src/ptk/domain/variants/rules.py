"""Variant business rules: validation, inheritance, resolution, explanation (pure)."""

from __future__ import annotations

import copy
from typing import Any

from .. import expressions
from ..errors import UnknownNameError
from ..suggest import did_you_mean
from .model import (
    FeatureValue,
    Issue,
    ProductLineSpec,
    ResolvedFeature,
    ResolvedVariant,
    Severity,
    VariantSpec,
    component_symbol,
)

# --------------------------------------------------------------------------- model checks


def validate(line: ProductLineSpec) -> list[tuple[str, str]]:
    """Structural problems as (path, message). Variant-internal problems are
    resolution issues instead, so a broken variant still loads."""
    problems: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    for comp, name, _ in line.iter_features():
        if name in seen:
            problems.append(
                (
                    f"variants.components.{comp}.features.{name}",
                    f"feature '{name}' is also declared by component '{seen[name]}'",
                )
            )
        seen[name] = comp
    symbols = line.symbols

    def check(expr: str, path: str) -> None:
        try:
            unknown = expressions.names(expr) - symbols
        except expressions.ExpressionError as exc:
            problems.append((path, str(exc)))
            return
        for name in sorted(unknown):
            problems.append(
                (path, f"unknown symbol '{name}'{did_you_mean(name, symbols)}")
            )

    for comp_name, comp in line.components.items():
        base = f"variants.components.{comp_name}"
        for req in comp.requires_components:
            if req not in line.components:
                problems.append(
                    (
                        f"{base}.requires_components",
                        f"unknown component '{req}'{did_you_mean(req, line.components)}",
                    )
                )
        for fname, spec in comp.features.items():
            fpath = f"{base}.features.{fname}"
            if spec.depends_on:
                check(spec.depends_on, f"{fpath}.depends_on")
            for i, expr in enumerate(spec.requires):
                check(expr, f"{fpath}.requires[{i}]")
            for i, expr in enumerate(spec.conflicts):
                check(expr, f"{fpath}.conflicts[{i}]")
    for i, constraint in enumerate(line.constraints):
        check(constraint.expr, f"variants.constraints[{i}].expr")

    aliases: dict[str, str] = {}
    for name, spec in line.variants.items():
        for alias in spec.aliases:
            if alias in line.variants and alias != name:
                problems.append(
                    (
                        f"variants.variants.{name}.aliases",
                        f"alias '{alias}' is also a variant name",
                    )
                )
            elif alias in aliases and aliases[alias] != name:
                problems.append(
                    (
                        f"variants.variants.{name}.aliases",
                        f"alias '{alias}' is already used by variant '{aliases[alias]}'",
                    )
                )
            aliases[alias] = name
    if line.default:
        try:
            find(line, line.default)
        except UnknownNameError as exc:
            problems.append(("variants.default", str(exc)))
    return problems


# --------------------------------------------------------------------------- lookup


def find(line: ProductLineSpec, name_or_alias: str) -> str:
    """Variant name for a name or alias (exact match first)."""
    if name_or_alias in line.variants:
        return name_or_alias
    alias = line.alias_index().get(name_or_alias)
    if alias:
        return alias
    candidates = list(line.variants) + list(line.alias_index())
    raise UnknownNameError(
        f"unknown variant '{name_or_alias}'{did_you_mean(name_or_alias, candidates)}"
    )


def default_variant(line: ProductLineSpec) -> str | None:
    if line.default:
        return find(line, line.default)
    buildable = line.buildable()
    return buildable[0] if buildable else None


# --------------------------------------------------------------------------- inheritance


def linearize(
    line: ProductLineSpec, name: str
) -> tuple[list[tuple[str, VariantSpec]], list[Issue]]:
    order: list[tuple[str, VariantSpec]] = []
    seen: set[str] = set()
    issues: list[Issue] = []

    def visit(current: str, stack: list[str]) -> None:
        if current in stack:
            issues.append(_err(f"inheritance cycle: {' -> '.join(stack + [current])}"))
            return
        if current in seen:
            return
        spec = line.variants.get(current)
        if spec is None:
            hint = f" (extended by '{stack[-1]}')" if stack else ""
            issues.append(
                _err(
                    f"unknown variant '{current}'{hint}{did_you_mean(current, line.variants)}"
                )
            )
            return
        for parent in spec.extends:
            visit(parent, stack + [current])
        seen.add(current)
        order.append((current, spec))

    visit(name, [])
    return order, issues


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# --------------------------------------------------------------------------- resolution


def _err(message: str, feature: str | None = None) -> Issue:
    return Issue(severity=Severity.ERROR, message=message, feature=feature)


def _warn(message: str, feature: str | None = None) -> Issue:
    return Issue(severity=Severity.WARNING, message=message, feature=feature)


def resolve(line: ProductLineSpec, name: str) -> ResolvedVariant:
    chain, issues = linearize(line, name)
    result = ResolvedVariant(name=name, all_components=list(line.components))
    if not chain or chain[-1][0] != name:
        result.issues = issues
        return result
    target = chain[-1][1]
    result.description = target.description
    result.abstract = target.abstract
    result.aliases = list(target.aliases)
    result.chain = [n for n, _ in chain]
    if target.abstract:
        issues.append(
            _warn(f"'{name}' is abstract (a template) and is not meant to be built")
        )

    # components
    active = list(line.components)
    for _, spec in chain:
        if spec.components is not None:
            active = list(spec.components)
    for comp in [c for c in active if c not in line.components]:
        issues.append(
            _err(f"unknown component '{comp}'{did_you_mean(comp, line.components)}")
        )
    active = [c for c in line.components if c in active]
    active_set = set(active)
    for comp in active:
        for req in line.components[comp].requires_components:
            if req not in active_set:
                issues.append(
                    _err(
                        f"component '{comp}' requires component '{req}', which is not in this variant"
                    )
                )
    result.components = active

    # assignments and data (parents first, later layers win)
    index = line.feature_index
    assigned: dict[str, tuple[Any, str]] = {}
    data: dict[str, Any] = {}
    for vname, spec in chain:
        result.repo_variants.update(spec.repo_variants)
        data = _deep_merge(data, spec.data)
        for feature, value in spec.features.items():
            if feature not in index:
                issues.append(
                    _err(
                        f"variant '{vname}' sets unknown feature '{feature}'{did_you_mean(feature, index)}",
                        feature,
                    )
                )
                continue
            try:
                line.feature(feature).validate_value(value)
            except ValueError as exc:
                issues.append(_err(f"variant '{vname}': {feature}: {exc}", feature))
                continue
            assigned[feature] = (value, vname)
    result.data = data
    for feature, (value, by) in assigned.items():
        comp = index[feature]
        if comp not in active_set and value != line.feature(feature).disabled_value:
            issues.append(
                _warn(
                    f"'{feature}' is set by '{by}' but component '{comp}' is not in this variant - ignored",
                    feature,
                )
            )

    # values to a fixpoint (depends_on may chain)
    symbols: dict[str, FeatureValue] = {
        component_symbol(c): (c in active_set) for c in line.components
    }
    for _, feature, spec in line.iter_features():
        symbols[feature] = spec.disabled_value
    active_features = [(c, f, s) for c, f, s in line.iter_features() if c in active_set]
    state: dict[str, tuple[FeatureValue, str, str | None]] = {}
    for _ in range(len(active_features) + 2):
        changed = False
        for _, feature, spec in active_features:
            if spec.depends_on and not expressions.evaluate(spec.depends_on, symbols):
                new = (spec.disabled_value, "depends_on", None)
            elif feature in assigned:
                new = (assigned[feature][0], "variant", assigned[feature][1])
            else:
                new = (spec.default, "default", None)
            if state.get(feature) != new:
                state[feature] = new
                symbols[feature] = new[0]
                changed = True
        if not changed:
            break
    else:
        issues.append(
            _err("depends_on rules do not settle - check for circular dependencies")
        )

    for _, feature, spec in active_features:
        if state[feature][1] == "depends_on" and feature in assigned:
            wanted, by = assigned[feature]
            if wanted != spec.disabled_value:
                issues.append(
                    _err(
                        f"'{feature}' is set to {wanted!r} by '{by}', but its dependency "
                        f"'{spec.depends_on}' is not satisfied",
                        feature,
                    )
                )
    for _, feature, spec in active_features:
        if not expressions.is_truthy(state[feature][0]):
            continue
        for expr in spec.requires:
            if not expressions.evaluate(expr, symbols):
                issues.append(_err(f"'{feature}' requires '{expr}'", feature))
        for expr in spec.conflicts:
            if expressions.evaluate(expr, symbols):
                issues.append(_err(f"'{feature}' conflicts with '{expr}'", feature))
    for constraint in line.constraints:
        if not expressions.evaluate(constraint.expr, symbols):
            issues.append(
                _err(constraint.message or f"constraint violated: {constraint.expr}")
            )

    for comp, feature, spec in line.iter_features():
        if comp in active_set:
            value, source, by = state[feature]
            result.features[feature] = ResolvedFeature(
                name=feature,
                component=comp,
                type=spec.type,
                value=value,
                source=source,
                set_by=by,
                help=spec.help,
            )  # type: ignore[arg-type]
        else:
            result.features[feature] = ResolvedFeature(
                name=feature,
                component=comp,
                type=spec.type,
                value=spec.disabled_value,
                source="inactive",
                active=False,
                help=spec.help,
            )
    result.issues = issues
    return result


def symbols_of(line: ProductLineSpec, resolved: ResolvedVariant) -> dict[str, Any]:
    """Symbol table of a resolved variant as seen by expressions."""
    symbols: dict[str, Any] = {
        component_symbol(c): resolved.component_active(c) for c in line.components
    }
    symbols.update(resolved.values)
    return symbols


def explain(line: ProductLineSpec, name: str, feature: str) -> list[str]:
    if feature not in line.feature_index:
        raise UnknownNameError(
            f"unknown feature '{feature}'{did_you_mean(feature, line.feature_index)}"
        )
    resolved = resolve(line, name)
    rf = resolved.features[feature]
    spec = line.feature(feature)
    symbols = symbols_of(line, resolved)
    reason = {
        "default": "feature default",
        "variant": f"set by variant '{rf.set_by}'",
        "depends_on": f"forced off: depends_on '{spec.depends_on}' is not satisfied",
        "inactive": f"component '{rf.component}' is not in this variant",
    }[rf.source]
    lines = [
        f"{feature} = {rf.value!r}   ({reason})",
        f"  component : {rf.component} ({'active' if rf.active else 'inactive'})",
        f"  type      : {spec.type.value}, default {spec.default!r}",
    ]
    if spec.help:
        lines.append(f"  help      : {spec.help}")
    if spec.depends_on:
        ok = expressions.evaluate(spec.depends_on, symbols)
        lines.append(
            f"  depends_on: {spec.depends_on}  -> {'satisfied' if ok else 'NOT satisfied'}"
        )
    chain, _ = linearize(line, name)
    layers = [(n, s.features[feature]) for n, s in chain if feature in s.features]
    if layers:
        lines.append("  assignments (parents first, last wins):")
        lines += [f"    {n}: {v!r}" for n, v in layers]
    for expr in spec.requires:
        lines.append(
            f"  requires  : {expr}  -> {'ok' if expressions.evaluate(expr, symbols) else 'VIOLATED'}"
        )
    for expr in spec.conflicts:
        lines.append(
            f"  conflicts : {expr}  -> {'VIOLATED' if expressions.evaluate(expr, symbols) else 'ok'}"
        )
    lines += [f"  {i}" for i in resolved.issues if i.feature == feature]
    return lines
