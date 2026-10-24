"""Variant use cases."""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.errors import PtkError
from ...domain.variants import conventions
from ...domain.variants import rules as vr
from ...domain.variants.model import ProductLineSpec, ResolvedVariant
from .project import Project


@dataclass
class VariantSummary:
    name: str
    description: str
    abstract: bool
    aliases: list[str]
    extends: list[str]
    default: bool


class VariantService:
    def __init__(self, project: Project):
        self._project = project

    @property
    def line(self) -> ProductLineSpec:
        line = self._project.config.variants
        if line is None:
            raise PtkError("this project has no 'variants' section")
        return line

    @property
    def has_variants(self) -> bool:
        return self._project.config.variants is not None

    def list(self, include_abstract: bool = True) -> list[VariantSummary]:
        default = vr.default_variant(self.line)
        return [VariantSummary(n, s.description, s.abstract, s.aliases, s.extends, n == default)
                for n, s in self.line.variants.items() if include_abstract or not s.abstract]

    def name_of(self, name_or_alias: str | None) -> str:
        if name_or_alias is None:
            default = vr.default_variant(self.line)
            if default is None:
                raise PtkError("no variant selected and no default variant configured")
            return default
        return vr.find(self.line, name_or_alias)

    def resolve(self, name_or_alias: str | None = None) -> ResolvedVariant:
        return vr.resolve(self.line, self.name_of(name_or_alias))

    def check(self, names: list[str] | None = None) -> dict[str, ResolvedVariant]:
        selected = [self.name_of(n) for n in names] if names else self.line.buildable()
        return {n: vr.resolve(self.line, n) for n in selected}

    def explain(self, name_or_alias: str, feature: str) -> list[str]:
        return vr.explain(self.line, self.name_of(name_or_alias), feature)

    def environment(self, resolved: ResolvedVariant) -> dict[str, str]:
        return conventions.environment(self.line, resolved)

    def namespace(self, resolved: ResolvedVariant) -> dict:
        return conventions.namespace(resolved)

    def symbols(self, resolved: ResolvedVariant) -> dict:
        return vr.symbols_of(self.line, resolved)

    def tags(self, resolved: ResolvedVariant) -> tuple[list[str], list[str]]:
        return conventions.tags(self.line, resolved)
