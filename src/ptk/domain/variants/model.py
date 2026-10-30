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
          features: {navigation.MAP_REGION: US}
          data: {toolchain: arm-gcc, flash: {address: "0x08000000"}}
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
RESERVED_COMPONENTS = {"params", "vars", "env", "vh", "variant", "os", "ci"}
RESERVED = {"VARIANT", "PROJECT", "OS", "CI"}

FeatureValue = bool | int | str | None


def component_symbol(name: str) -> str:
    return COMPONENT_PREFIX + name.upper()


def feature_symbol(name: str) -> str:
    """Canonical component.FEATURE identity exported to build tools."""
    return "VARIANT_" + name.replace(".", "_").upper()


def nested_values(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, value in values.items():
        component, feature = name.split(".", 1)
        result.setdefault(component, {})[feature] = value
    return result


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
    type: FeatureType = Field(
        default=FeatureType.BOOL,
        description="Feature value type: boolean, integer, string or enum.",
    )
    help: str = Field(
        default="", description="Explanation of the feature shown to users."
    )
    default: bool | int | str | None = Field(
        default=None,
        description="Feature value used when a variant does not override it.",
    )
    values: list[str] | None = Field(
        default=None,
        description="Allowed values for an enum feature. Required when type is enum.",
    )
    min: int | None = Field(
        default=None, description="Smallest allowed integer feature value."
    )
    max: int | None = Field(
        default=None, description="Largest allowed integer feature value."
    )
    depends_on: str | None = Field(
        default=None,
        description="Condition controlling whether this feature is active.",
    )
    requires: list[str] = Field(
        description="Feature expressions that must hold when this feature is enabled.",
        default_factory=list,
    )
    conflicts: list[str] = Field(
        description="Feature expressions that must not hold when this feature is enabled.",
        default_factory=list,
    )

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


class Constraint(_Strict):
    expr: str = Field(
        description="Boolean expression that must hold for a valid variant."
    )
    message: str = Field(
        default="", description="Explanation shown when the constraint fails."
    )

    @model_validator(mode="before")
    @classmethod
    def _from_str(cls, v: Any) -> Any:
        return {"expr": v} if isinstance(v, str) else v


class ComponentSpec(_Strict):
    description: str = Field(
        default="", description="Short explanation of this component."
    )
    requires_components: list[str] = Field(
        description="Other components that must be included whenever this component is selected.",
        default_factory=list,
    )
    constraints: list[Constraint] = Field(
        description="Validation expressions applied to this component’s feature selection.",
        default_factory=list,
    )
    features: dict[str, FeatureSpec] = Field(
        description="Feature definitions owned by this component. Use UPPER_SNAKE_CASE names.",
        default_factory=dict,
    )

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


class VariantSpec(_Strict):
    repo_variants: dict[str, str] = Field(
        description="Map repository aliases to the variants their workflow jobs must use when this owner variant is selected.",
        default_factory=dict,
    )
    description: str = Field(
        default="", description="Human-readable explanation shown in variant choices."
    )
    abstract: bool = Field(
        default=False,
        description="Use this variant only as an inheritance base; it cannot be selected for execution.",
    )
    extends: list[str] = Field(
        description="Parent variants inherited in order.", default_factory=list
    )
    aliases: list[str] = Field(
        description="Alternative names accepted when selecting this variant.",
        default_factory=list,
    )
    components: list[str] | None = Field(
        default=None,
        description="Components included in this variant. Omission inherits the parent selection; a root variant defaults to all components.",
    )  # None = inherit (root: all components)
    features: dict[str, bool | int | str] = Field(
        description="Feature values overriding defaults or inherited selections, keyed by component.FEATURE (for example power.DEBUG_LEVEL).",
        default_factory=dict,
    )
    data: dict[str, Any] = Field(
        description="Custom variant data available through ${vh.data.name}.",
        default_factory=dict,
    )

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

    @field_validator("features")
    @classmethod
    def _feature_ids(cls, values):
        for name in values:
            component, separator, feature = name.partition(".")
            if (
                not separator
                or not COMPONENT_RE.fullmatch(component)
                or not FEATURE_RE.fullmatch(feature)
            ):
                raise ValueError(
                    f"feature selection {name!r} must use component.FEATURE"
                )
        return values


class ProductLineSpec(_Strict):
    default: str | None = Field(
        default=None,
        description="Concrete variant used when no explicit selection is supplied.",
    )
    components: dict[str, ComponentSpec] = Field(
        description="Component feature models loaded from registered component directories.",
        default_factory=dict,
    )
    variants: dict[str, VariantSpec] = Field(
        description="Named variants with component selections, feature overrides and inheritance.",
        default_factory=dict,
    )
    constraints: list[Constraint] = Field(
        description="Validation expressions applied to all variants.",
        default_factory=list,
    )

    @field_validator("components")
    @classmethod
    def _component_names(cls, v: dict[str, ComponentSpec]) -> dict[str, ComponentSpec]:
        for name in v:
            if name in RESERVED_COMPONENTS:
                raise ValueError(
                    f"component name {name!r} is a reserved expression namespace"
                )
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
                yield comp_name, f"{comp_name}.{name}", spec

    @property
    def feature_index(self) -> dict[str, str]:
        return {name: comp for comp, name, _ in self.iter_features()}

    def feature(self, name: str) -> FeatureSpec:
        return self.components[self.feature_index[name]].features[name.split(".", 1)[1]]

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
    repo_variants: dict[str, str] = Field(default_factory=dict)
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
