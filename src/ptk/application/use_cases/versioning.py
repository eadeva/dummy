"""Resolve one version snapshot per run, including explicit VMR dependencies."""

from copy import deepcopy

from ...domain.errors import PtkError
from ...domain.versioning import VersionSource, identifier, variables
from ..ports import VersionDiscovery


class VersionService:
    def __init__(self, io: VersionDiscovery, dependency_loader):
        self.io, self.dependency_loader = io, dependency_loader

    def resolve(self, project, variant=None, job=None):
        if project.config.versioning is None:
            return {}
        projects, selected, visiting = {}, {}, set()

        def visit(member, chosen, dependencies=None):
            alias = (
                member.config.repository.alias
                if member.config.repository
                else member.config.project.name
            )
            identifier(alias)
            if alias in visiting:
                raise PtkError(f"version dependency cycle at {alias}")
            if alias in selected:
                if selected[alias] != chosen:
                    raise PtkError(f"conflicting version variants for {alias}")
                return
            spec = member.config.versioning
            if spec is None or spec.project is None:
                raise PtkError(f"repository {alias} needs a versioning.project source")
            known = member.config.variants.variants if member.config.variants else {}
            unknown = spec.variants.keys() - known.keys()
            if unknown:
                raise PtkError(f"unknown versioning variants: {sorted(unknown)}")
            override = spec.variants.get(chosen)
            source = override.project if override and override.project else spec.project
            value = self.io.discover(source, member.root)
            components = {
                name: VersionSource()
                for name in (
                    member.config.variants.components if member.config.variants else {}
                )
            }
            components.update(spec.components)
            if override:
                components.update(override.components)
            resolved_components = {}
            for name, config in components.items():
                identifier(name)
                if config.source == "inherit":
                    resolved_components[name] = {**deepcopy(value), "inherited": True}
                else:
                    resolved_components[name] = {
                        **self.io.discover(config, member.root),
                        "inherited": False,
                    }
            projects[alias] = {
                **value,
                "variant": chosen,
                "components": resolved_components,
            }
            selected[alias] = chosen
            visiting.add(alias)
            for dependency, settings in {
                **spec.dependencies,
                **(dependencies or {}),
            }.items():
                other = self.dependency_loader(member, dependency)
                dep_variant = settings.variant
                if other.config.variants:
                    if dep_variant is None:
                        raise PtkError(
                            f"version dependency {dependency} requires an explicit variant"
                        )
                    if dep_variant not in other.config.variants.variants:
                        raise PtkError(
                            f"unknown dependency variant {dependency}/{dep_variant}"
                        )
                elif dep_variant is not None:
                    raise PtkError(f"repository {dependency} has no variants")
                visit(other, dep_variant)
            visiting.remove(alias)

        dependencies = project.config.jobs[job].version_dependencies if job else {}
        visit(project, variant, dependencies)
        snapshot = {"schema_version": 1, "projects": projects}
        variables(snapshot)  # also checks normalized-name collisions
        return snapshot

    def write(self, path, snapshot):
        self.io.snapshot(path, snapshot)
