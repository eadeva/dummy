"""Resolve workflow variants from the owning repository's variant configuration."""

from ...domain.errors import PtkError
from .variants import VariantService


class WorkflowVariants:
    def __init__(self, owner, selected):
        self.owner = owner
        self.selected = None
        self.mapping = {}
        if owner is None:
            if selected:
                raise PtkError("select a repository-owned workflow to use --variant")
            return
        service = VariantService(owner)
        if not service.has_variants:
            if selected:
                raise PtkError("workflow owner has no variants")
            return
        if selected and "," in selected:
            raise PtkError("select one owner variant per workflow invocation")
        resolved = service.resolve(selected)
        if resolved.abstract:
            raise PtkError(
                f"variant {resolved.name!r} is abstract; select a concrete variant"
            )
        if resolved.errors:
            raise PtkError(
                "invalid workflow owner variant: "
                + "; ".join(map(str, resolved.errors))
            )
        self.selected = resolved.name
        self.mapping = resolved.repo_variants

    def for_project(self, alias, project):
        if self.owner is not None and project.root == self.owner.root:
            return self.selected
        service = VariantService(project)
        if alias not in self.mapping:
            # A repository without a variant model has no variant to select.
            if not service.has_variants:
                return None
            raise PtkError(
                f"workflow owner variant {self.selected!r}: missing repo_variants mapping for repository {alias!r}"
            )
        selected = self.mapping[alias]
        if not service.has_variants:
            raise PtkError(
                f"repository {alias!r} has no variants but is mapped to {selected!r}"
            )
        try:
            resolved = service.resolve(selected)
        except PtkError as exc:
            raise PtkError(
                f"workflow owner variant {self.selected!r}, repository {alias!r}, "
                f"mapped variant {selected!r}: {exc}"
            ) from None
        if resolved.abstract:
            raise PtkError(
                f"variant {resolved.name!r} is abstract; select a concrete variant"
            )
        if resolved.errors:
            raise PtkError(
                f"repository {alias!r}: invalid mapped variant {selected!r}: "
                + "; ".join(map(str, resolved.errors))
            )
        return resolved.name
