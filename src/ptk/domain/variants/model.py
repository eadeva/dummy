"""Variant model (entities).

A product line has components (each declaring features) and variants
(selections of components and feature values, with inheritance)::

    variants:
      default: customer_a_high
      components:
        display:
          features:
            DISPLAY_SIZE: {type: int, min: 5, max: 15, default: 8}
            TOUCH: {type: bool}
        navigation:
          requires_components: [display]
          features:
            MAP_REGION: {type: enum, values: [EU, US]}
      variants:
        base: {abstract: true, components: [display]}
        customer_b_us:
          extends: base
          aliases: [b_us, "3"]
          components: [display, navigation]
          features: {MAP_REGION: US}
          data: {conan: {requires: {"zlib/1.3": {}}}}
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..expressions import is_truthy

FEATURE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
COMPONENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VARIANT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ENUM_VALUE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")
COMPONENT_PREFIX = "COMPONENT_"
RESERVED = {"VARIANT", "PROJECT", "OS", "CI"}

FeatureValue = bool | int | str | None


def component_symbol(name: str) -> str:
    return COMPONENT_PREFIX + name.upper()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _listify(value: Any) -> Any:
    if value is None:
        return []
    return [value] if isinstance(value, str) else value


class FeatureType(StrEnum):
    BOOL = "bool"
    INT = "int"
    STRING = "string"
    ENUM = "enum"


class FeatureSpec(_Strict):
    type: FeatureType = FeatureType.BOOL
    help: str = ""
    default: bool | int | str | None = None
    values: list[str] | None = None
    min: int | None = None
    max: int | None = None
    depends_on: str | None = None
    requires: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

    @field_validator("requires", "conflicts", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> Any:
        return _listify(v)

    @model_validator(mode="after")
    def _check(self) -> FeatureSpec:
        kind = self.type
        if kind is FeatureType.ENUM:
            if not self.values:
                raise ValueError("enum features need a non-empty 'values' list")
            bad = [v for v in self.values if not ENUM_VALUE_RE.match(v)]
            if bad:
                raise ValueError(f"invalid enum value(s) {bad}")
            if len(set(self.values)) != len(self.values):
                raise ValueError("enum 'values' contain duplicates")
        elif self.values is not None:
            raise ValueError("'values' is only allowed for enum features")
        if kind is not FeatureType.INT and (
            self.min is not None or self.max is not None
        ):
            raise ValueError("'min'/'max' are only allowed for int features")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("'min' is greater than 'max'")
        if self.default is None:
            self.default = {
                FeatureType.BOOL: False,
                FeatureType.INT: self.min if self.min is not None else 0,
                FeatureType.STRING: "",
                FeatureType.ENUM: (self.values or [None])[0],
            }[kind]
        self.default = self.validate_value(self.default)
        return self

    @property
    def disabled_value(self) -> FeatureValue:
        return False if self.type is FeatureType.BOOL else None

    def validate_value(self, value: Any) -> FeatureValue:
        kind = self.type
        if kind is FeatureType.BOOL:
            if not isinstance(value, bool):
                raise ValueError(f"expected true/false, got {value!r}")
        elif kind is FeatureType.INT:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"expected an integer, got {value!r}")
            if self.min is not None and value < self.min:
                raise ValueError(f"{value} is below the minimum {self.min}")
            if self.max is not None and value > self.max:
                raise ValueError(f"{value} is above the maximum {self.max}")
        elif kind is FeatureType.STRING:
            if not isinstance(value, str):
                raise ValueError(f"expected a string, got {value!r}")
        elif value not in (self.values or []):
            raise ValueError(
                f"expected one of {', '.join(self.values or [])}, got {value!r}"
            )
        return value

    def parse_text(self, text: str) -> FeatureValue:
        """Typed value from command-line text."""
        if self.type is FeatureType.BOOL:
            low = text.strip().lower()
            if low in {"y", "yes", "true", "on", "1"}:
                return True
            if low in {"n", "no", "false", "off", "0"}:
                return False
            raise ValueError(
                f"expected a boolean (y/n, true/false, on/off), got {text!r}"
            )
        if self.type is FeatureType.INT:
            try:
                return self.validate_value(int(text, 0))
            except ValueError:
                raise ValueError(f"expected an integer, got {text!r}") from None
        return self.validate_value(text)


class ComponentSpec(_Strict):
    description: str = ""
    requires_components: list[str] = Field(default_factory=list)
    features: dict[str, FeatureSpec] = Field(default_factory=dict)

    @field_validator("features", mode="before")
    @classmethod
    def _none(cls, v: Any) -> Any:
        return {} if v is None else v

    @field_validator("features")
    @classmethod
    def _names(cls, v: dict[str, FeatureSpec]) -> dict[str, FeatureSpec]:
        for name in v:
            if not FEATURE_RE.match(name):
                raise ValueError(f"feature name {name!r} must be UPPER_SNAKE_CASE")
            if name.startswith(COMPONENT_PREFIX) or name in RESERVED:
                raise ValueError(f"feature name {name!r} is reserved")
        return v


class Constraint(_Strict):
    expr: str
    message: str = ""

    @model_validator(mode="before")
    @classmethod
    def _from_str(cls, v: Any) -> Any:
        return {"expr": v} if isinstance(v, str) else v


class VariantSpec(_Strict):
    description: str = ""
    abstract: bool = False
    extends: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    components: list[str] | None = None  # None = inherit (root: all components)
    features: dict[str, bool | int | str] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extends", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> Any:
        return _listify(v)

    @field_validator("aliases", mode="before")
    @classmethod
    def _stringify(cls, v: Any) -> Any:
        return [str(a) for a in _listify(v)]

    @field_validator("features", "data", mode="before")
    @classmethod
    def _none(cls, v: Any) -> Any:
        return {} if v is None else v


class VariantEnvSpec(_Strict):
    prefix: str = "VH_"
    legacy_bo: bool = False  # also export BO_<FEATURE> like the previous tool


class ProductLineSpec(_Strict):
    default: str | None = None
    components: dict[str, ComponentSpec] = Field(default_factory=dict)
    variants: dict[str, VariantSpec] = Field(default_factory=dict)
    constraints: list[Constraint] = Field(default_factory=list)
    env: VariantEnvSpec = Field(default_factory=VariantEnvSpec)

    @field_validator("components")
    @classmethod
    def _component_names(cls, v: dict[str, ComponentSpec]) -> dict[str, ComponentSpec]:
        for name in v:
            if not COMPONENT_RE.match(name):
                raise ValueError(f"component name {name!r} must be lower_snake_case")
        return v

    @field_validator("variants")
    @classmethod
    def _variant_names(cls, v: dict[str, VariantSpec]) -> dict[str, VariantSpec]:
        for name, spec in v.items():
            if not VARIANT_RE.match(name):
                raise ValueError(
                    f"variant name {name!r} may only contain letters, digits, '_' and '-'"
                )
            for alias in spec.aliases:
                if not ALIAS_RE.match(alias):
                    raise ValueError(
                        f"alias {alias!r} of variant {name!r} is not valid"
                    )
        return v

    # -------------------------------------------------------------- helpers

    def iter_features(self):
        for comp_name, comp in self.components.items():
            for name, spec in comp.features.items():
                yield comp_name, name, spec

    @property
    def feature_index(self) -> dict[str, str]:
        return {name: comp for comp, name, _ in self.iter_features()}

    def feature(self, name: str) -> FeatureSpec:
        return self.components[self.feature_index[name]].features[name]

    @property
    def symbols(self) -> set[str]:
        result = {name for _, name, _ in self.iter_features()}
        result.update(component_symbol(c) for c in self.components)
        return result

    def alias_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for name, spec in self.variants.items():
            for alias in spec.aliases:
                index[alias] = name
        return index

    def buildable(self) -> list[str]:
        return [name for name, spec in self.variants.items() if not spec.abstract]


# --------------------------------------------------------------------------- results


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Issue(BaseModel):
    severity: Severity
    message: str
    feature: str | None = None

    def __str__(self) -> str:
        return f"{self.severity.value}: {self.message}"


ValueSource = Literal["default", "variant", "depends_on", "inactive"]


class ResolvedFeature(BaseModel):
    name: str
    component: str
    type: FeatureType
    value: FeatureValue
    source: ValueSource
    set_by: str | None = None
    active: bool = True
    help: str = ""

    @property
    def enabled(self) -> bool:
        return self.active and is_truthy(self.value)


class ResolvedVariant(BaseModel):
    name: str
    description: str = ""
    abstract: bool = False
    aliases: list[str] = Field(default_factory=list)
    chain: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    all_components: list[str] = Field(default_factory=list)
    features: dict[str, ResolvedFeature] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    issues: list[Issue] = Field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def values(self) -> dict[str, FeatureValue]:
        return {n: f.value for n, f in self.features.items()}

    def is_enabled(self, feature: str) -> bool:
        f = self.features.get(feature)
        return bool(f and f.enabled)

    def component_active(self, component: str) -> bool:
        return component in self.components
