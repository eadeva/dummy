"""Portable job eligibility shared by execution, discovery and workflow export."""

from ...domain import expressions
from ...domain.errors import PtkError
from .variants import VariantService


def job_enabled(project, spec, variant=None, *, resolved=None):
    if not spec.when:
        return True
    service = VariantService(project)
    symbols = {"cx": project.cx, "variant": "default", "vh": {}}
    if service.has_variants:
        resolved = resolved or service.resolve(variant)
        if resolved.errors:
            raise PtkError("invalid variant: " + "; ".join(map(str, resolved.errors)))
        symbols.update(service.symbols(resolved))
        symbols.update(variant=resolved.name, vh=service.namespace(resolved))
    return expressions.evaluate(spec.when, symbols)


def job_available(project, spec):
    """Keep jobs selectable if any concrete variant satisfies the condition."""
    service = VariantService(project)
    names = service.line.buildable() if service.has_variants else [None]
    return any(job_enabled(project, spec, name) for name in names)
