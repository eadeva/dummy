"""Naming conventions for consumers of a resolved variant (pure).

* environment variables: ``VARIANT_<COMPONENT>_<FEATURE>``,
  ``VARIANT_COMPONENT_<NAME>``, ``VARIANT_NAME`` and ``VARIANT_COMPONENTS``.
* tags: ``variant_<v>``, ``component_<c>``, ``feature_<c>_<f>`` and
  ``feature_<c>_<f>_<value>`` (enum).
* substitutions: ``${vh.variant}``, ``${vh.features.core.FEATURE}``,
  ``${vh.components.core}``, ``${vh.data.<path>}``.
"""

from __future__ import annotations

import re
from typing import Any

from ..expressions import is_truthy
from .model import (
    FeatureType,
    ProductLineSpec,
    ResolvedVariant,
    feature_symbol,
    nested_values,
)


def identifier(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", text).lower()


def env_value(value: Any) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return "" if value is None else str(value)


def environment(line: ProductLineSpec, resolved: ResolvedVariant) -> dict[str, str]:
    env = {
        "VARIANT_NAME": resolved.name,
        "VARIANT_COMPONENTS": " ".join(resolved.components),
    }
    for comp in line.components:
        env[f"VARIANT_COMPONENT_{comp.upper()}"] = env_value(
            resolved.component_active(comp)
        )
    for name, feature in resolved.features.items():
        env[feature_symbol(name)] = env_value(feature.value)
    return env


def namespace(resolved: ResolvedVariant) -> dict[str, Any]:
    """Value of the ``vh`` substitution/expression namespace."""
    return {
        "variant": resolved.name,
        "aliases": list(resolved.aliases),
        "components": {
            c: resolved.component_active(c) for c in resolved.all_components
        },
        "component_list": list(resolved.components),
        "features": nested_values(resolved.values),
        "data": resolved.data,
    }


def tags(
    line: ProductLineSpec, resolved: ResolvedVariant
) -> tuple[list[str], list[str]]:
    on = [f"variant_{identifier(resolved.name)}"]
    off: list[str] = []
    for comp in line.components:
        (on if resolved.component_active(comp) else off).append(
            f"component_{identifier(comp)}"
        )
    for _comp, name, spec in line.iter_features():
        value = resolved.features[name].value
        base = f"feature_{identifier(name)}"
        if spec.type is FeatureType.ENUM:
            for option in spec.values or []:
                (on if value == option else off).append(f"{base}_{identifier(option)}")
        else:
            (on if is_truthy(value) else off).append(base)
    return on, off
